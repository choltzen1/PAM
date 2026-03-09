"""Microsoft Fabric Data Warehouse manager for ORBIT data.

Provides read access to ORBIT_Reporting_Table in Microsoft Fabric using
dual authentication:
  - Managed Identity (Azure App Service) — preferred in production
  - Service Principal (local development) — fallback

Resilience features:
  - Persistent connection reused across queries (fast path: ~0s overhead)
  - Connection auto-expires after 5 minutes to avoid Fabric staleness
  - Health check uses a thread-based hard timeout (never hangs Flask)
  - Token caching (~50 min, tokens valid ~60 min)
  - Query result cache: serves stale data when Fabric is temporarily down
  - Circuit breaker: stops retrying a dead connection for a cooldown period
  - Automatic retry with backoff on transient connection failures
  - All timeouts enforced via daemon threads (ODBC driver can never block)
  - No nested locks — token lock, connection lock, cache lock are independent
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import hashlib
import struct
import time
import logging
from datetime import datetime, timedelta
from threading import Lock, Thread
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

# ── Tuning constants ───────────────────────────────────────────────────
_CONN_MAX_AGE = 300              # seconds before forcing reconnect
_CONNECT_HARD_TIMEOUT = 15       # per-attempt timeout (seconds)
_HEALTH_CHECK_TIMEOUT = 5        # SELECT 1 timeout (seconds)
_MAX_CONNECT_ATTEMPTS = 3        # retries per connection cycle
_RETRY_BACKOFF = [0.5, 1.0]     # sleep between retries (seconds)

# ── Query result cache (module-level, survives across requests) ────────
_query_cache: Dict[str, Dict] = {}
_query_cache_lock = Lock()
_QUERY_CACHE_TTL = 30            # minutes — serve stale data up to this long
_QUERY_CACHE_MAX_ENTRIES = 500   # cap cache size to prevent memory bloat


def _cache_key(method: str, *args) -> str:
    raw = f"{method}:" + "|".join(str(a) for a in args)
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str):
    with _query_cache_lock:
        entry = _query_cache.get(key)
        if entry and datetime.now() < entry["ts"] + timedelta(minutes=_QUERY_CACHE_TTL):
            return entry["data"]
    return None


def _cache_set(key: str, data):
    with _query_cache_lock:
        # Evict oldest entries if cache is too large
        if len(_query_cache) >= _QUERY_CACHE_MAX_ENTRIES:
            oldest_key = min(_query_cache, key=lambda k: _query_cache[k]["ts"])
            del _query_cache[oldest_key]
        _query_cache[key] = {"data": data, "ts": datetime.now()}


def _is_azure() -> bool:
    """Detect if running on Azure App Service."""
    return os.getenv('WEBSITE_INSTANCE_ID') is not None


class FabricDatabaseManager:
    """Manages a persistent connection to Microsoft Fabric Data Warehouse.

    Authentication strategy (automatic):
      1. Azure App Service → Managed Identity (zero-secret, auto-rotated)
      2. Local development → Service Principal (from .env)
      3. Fallback → DefaultAzureCredential (covers edge cases)

    The connection is reused across queries for performance.  If it goes
    stale, times out, or is older than _CONN_MAX_AGE, it is transparently
    replaced.  All timeouts are enforced from Python (via daemon threads)
    so Flask never hangs.
    """

    # Class-level token cache (shared across instances / threads)
    _cached_token = None
    _token_expiry = None
    _token_lock = Lock()

    # Circuit breaker — avoid hammering Fabric when it's down
    _circuit_open = False
    _circuit_opened_at = None
    _circuit_fail_count = 0
    _circuit_lock = Lock()
    _CIRCUIT_COOLDOWN = 120   # seconds before retrying after trip
    _CIRCUIT_THRESHOLD = 2    # consecutive failures to trip

    def __init__(self):
        """Initialize Fabric connection parameters from environment."""
        try:
            env_path = find_dotenv()
            if env_path:
                load_dotenv(env_path)
        except Exception:
            pass

        self.tenant_id = os.getenv('FABRIC_TENANT_ID')
        self.client_id = os.getenv('FABRIC_CLIENT_ID')
        self.client_secret = os.getenv('FABRIC_CLIENT_SECRET')
        self.server = os.getenv('FABRIC_SERVER')
        self.database = os.getenv('FABRIC_DATABASE')
        self.port = '1433'
        self.driver = 'ODBC Driver 18 for SQL Server'
        self.table = 'dbo.ORBIT_Reporting_Table'

        self._last_error = None
        self._last_auth_method = None
        self._used_connection_string = None

        # Persistent connection state (protected by _conn_lock)
        self._connection = None
        self._conn_created_at = None
        self._conn_lock = Lock()

        # Log configuration state
        if not self.server or not self.database:
            missing = [v for v, val in {
                'FABRIC_SERVER': self.server,
                'FABRIC_DATABASE': self.database,
            }.items() if not val]
            logger.warning(f"Fabric config incomplete. Missing: {', '.join(missing)}")
        else:
            logger.info(f"FabricDatabaseManager initialized "
                        f"(azure={_is_azure()}, server={self.server[:30]}...)")

    # ── Authentication ───────────────────────────────────────────────

    def _get_access_token(self) -> Optional[bytes]:
        """Get OAuth access token for Fabric, with caching.

        Auth priority:
          1. Managed Identity (on Azure App Service — no secrets needed)
          2. Service Principal (local dev — uses .env credentials)
          3. DefaultAzureCredential (covers Azure CLI, VS Code, etc.)

        Returns token struct bytes for pyodbc, or None on failure.
        Uses its own lock — never called while holding _conn_lock.
        """
        with self._token_lock:
            if (self._cached_token and self._token_expiry
                    and datetime.now() < self._token_expiry):
                return self._cached_token

            try:
                # Disable SSL verification for corporate proxy environments
                os.environ.setdefault('REQUESTS_CA_BUNDLE', '')
                os.environ.setdefault('CURL_CA_BUNDLE', '')

                credential = None
                auth_method = "unknown"
                scope = "https://database.windows.net/.default"

                # Strategy 1: Managed Identity (Azure App Service)
                if _is_azure():
                    try:
                        from azure.identity import ManagedIdentityCredential
                        logger.info("Azure detected — trying Managed Identity...")
                        mi_cred = ManagedIdentityCredential()
                        mi_cred.get_token(scope)  # validate it works
                        credential = mi_cred
                        auth_method = "Managed Identity"
                        logger.info("Managed Identity authentication OK")
                    except Exception as mi_err:
                        logger.warning(f"Managed Identity failed: {mi_err}")

                # Strategy 2: Service Principal (local dev or MI fallback)
                if credential is None and self.client_id and self.client_secret:
                    try:
                        from azure.identity import ClientSecretCredential
                        logger.info("Authenticating via Service Principal...")
                        credential = ClientSecretCredential(
                            tenant_id=self.tenant_id,
                            client_id=self.client_id,
                            client_secret=self.client_secret,
                            connection_verify=False,
                        )
                        auth_method = "Service Principal"
                    except Exception as sp_err:
                        logger.warning(f"Service Principal init failed: {sp_err}")

                # Strategy 3: DefaultAzureCredential (covers CLI, VS Code, etc.)
                if credential is None:
                    try:
                        from azure.identity import DefaultAzureCredential
                        logger.info("Trying DefaultAzureCredential...")
                        credential = DefaultAzureCredential(
                            exclude_interactive_browser_credential=True,
                            connection_verify=False,
                        )
                        auth_method = "DefaultAzureCredential"
                    except Exception as dac_err:
                        logger.error(f"All auth methods exhausted: {dac_err}")
                        self._last_error = f"No viable auth method: {dac_err}"
                        return None

                # Acquire the token
                token = credential.get_token(scope)

                # Pack into pyodbc format (SQL_COPT_SS_ACCESS_TOKEN)
                token_bytes = token.token.encode('utf-16-le')
                token_struct = struct.pack(
                    f'<I{len(token_bytes)}s', len(token_bytes), token_bytes
                )

                self._cached_token = token_struct
                self._token_expiry = datetime.now() + timedelta(minutes=50)
                self._last_auth_method = auth_method
                logger.info(f"Fabric token acquired via {auth_method}")
                return token_struct

            except Exception as e:
                logger.error(f"Fabric token acquisition failed: {e}")
                self._last_error = str(e)
                return None

    # ── Connection management ───────────────────────────────────────

    def _kill_connection(self):
        """Silently close the persistent connection.
        Caller must already hold _conn_lock or be in a safe context."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
        self._connection = None
        self._conn_created_at = None

    def _is_connection_fresh(self) -> bool:
        """True if the persistent connection exists and is not expired."""
        if not self._connection or not self._conn_created_at:
            return False
        age = (datetime.now() - self._conn_created_at).total_seconds()
        return age < _CONN_MAX_AGE

    def _health_check(self) -> bool:
        """Run SELECT 1 with a hard timeout via daemon thread.
        Never blocks longer than _HEALTH_CHECK_TIMEOUT seconds."""
        if not self._connection:
            return False

        ok = [False]

        def _ping():
            try:
                cursor = self._connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                ok[0] = True
            except Exception:
                pass

        t = Thread(target=_ping, daemon=True)
        t.start()
        t.join(timeout=_HEALTH_CHECK_TIMEOUT)
        return ok[0]

    def _circuit_check(self) -> bool:
        """Return True if we should attempt a connection."""
        with self._circuit_lock:
            if not self._circuit_open:
                return True
            elapsed = (datetime.now() - self._circuit_opened_at).total_seconds() \
                if self._circuit_opened_at else 999
            if elapsed >= self._CIRCUIT_COOLDOWN:
                logger.info("Circuit breaker cooldown elapsed — retrying Fabric")
                self._circuit_open = False
                self._circuit_fail_count = 0
                return True
            logger.warning(
                f"Circuit breaker OPEN — skipping Fabric "
                f"({int(self._CIRCUIT_COOLDOWN - elapsed)}s until retry)"
            )
            return False

    def _circuit_record_success(self):
        with self._circuit_lock:
            self._circuit_fail_count = 0
            self._circuit_open = False

    def _circuit_record_failure(self):
        with self._circuit_lock:
            self._circuit_fail_count += 1
            if self._circuit_fail_count >= self._CIRCUIT_THRESHOLD:
                self._circuit_open = True
                self._circuit_opened_at = datetime.now()
                logger.error(
                    f"Circuit breaker TRIPPED after "
                    f"{self._circuit_fail_count} consecutive failures"
                )

    def _build_connection_string(self) -> str:
        """Build the ODBC connection string.
        Uses TrustServerCertificate=no on Azure (proper CA certs available),
        TrustServerCertificate=yes locally (corporate proxy may intercept TLS).
        """
        trust_cert = "no" if _is_azure() else "yes"
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.server},{self.port};"
            f"DATABASE={self.database};"
            f"Encrypt=yes;"
            f"TrustServerCertificate={trust_cert};"
            f"Connection Timeout={_CONNECT_HARD_TIMEOUT};"
            f"Login Timeout={_CONNECT_HARD_TIMEOUT};"
        )

    def _open_connection(self):
        """Open a new pyodbc connection to Fabric with retry + hard timeout.

        Each attempt is capped at _CONNECT_HARD_TIMEOUT seconds via a daemon
        thread so we never block Flask.  Respects circuit breaker state.
        On success, resets the circuit breaker.
        On total failure, trips the circuit breaker.
        """
        if not self._circuit_check():
            return None

        import pyodbc

        token_struct = self._get_access_token()
        if not token_struct:
            self._circuit_record_failure()
            return None

        connection_string = self._build_connection_string()
        self._used_connection_string = connection_string

        for attempt in range(1, _MAX_CONNECT_ATTEMPTS + 1):
            result = [None]
            error = [None]

            def _try_connect():
                try:
                    result[0] = pyodbc.connect(
                        connection_string,
                        attrs_before={1256: token_struct},
                        timeout=_CONNECT_HARD_TIMEOUT,
                    )
                except Exception as e:
                    error[0] = e

            start = time.time()
            t = Thread(target=_try_connect, daemon=True)
            t.start()
            t.join(timeout=_CONNECT_HARD_TIMEOUT)
            elapsed = time.time() - start

            if result[0] is not None:
                logger.info(
                    f"Fabric connected in {elapsed:.1f}s "
                    f"(attempt {attempt}, auth={self._last_auth_method})"
                )
                self._circuit_record_success()
                return result[0]

            if t.is_alive():
                logger.warning(
                    f"Fabric connect attempt {attempt}/{_MAX_CONNECT_ATTEMPTS} "
                    f"hard-timed-out after {elapsed:.1f}s"
                )
                self._last_error = "Connection timed out (hard limit)"
            else:
                logger.warning(
                    f"Fabric connect attempt {attempt}/{_MAX_CONNECT_ATTEMPTS} "
                    f"failed after {elapsed:.1f}s: {error[0]}"
                )
                self._last_error = str(error[0])

            # Backoff before retry
            if attempt < _MAX_CONNECT_ATTEMPTS:
                backoff = _RETRY_BACKOFF[min(attempt - 1, len(_RETRY_BACKOFF) - 1)]
                time.sleep(backoff)

        # All attempts exhausted — on second failure cycle, trip the breaker
        self._circuit_record_failure()
        return None

    def _get_connection(self):
        """Get a healthy persistent connection, creating one if needed.

        This is the ONLY method that touches _conn_lock.
        Lock is held briefly — just for the health check and swap.
        The expensive _open_connection() call happens OUTSIDE the lock.
        """
        with self._conn_lock:
            if self._is_connection_fresh():
                if self._health_check():
                    return self._connection
                logger.warning("Fabric persistent connection failed health check")
                self._kill_connection()
            elif self._connection:
                logger.info("Fabric persistent connection expired, reconnecting")
                self._kill_connection()

        # Slow path: open new connection (outside lock)
        new_conn = self._open_connection()

        with self._conn_lock:
            if new_conn:
                # Race condition guard: if another thread reconnected, use theirs
                if self._connection and self._is_connection_fresh():
                    try:
                        new_conn.close()
                    except Exception:
                        pass
                    return self._connection

                self._kill_connection()
                self._connection = new_conn
                self._conn_created_at = datetime.now()
                return self._connection
            else:
                return None

    # ── Query execution ────────────────────────────────────────────

    def _execute_query(self, query: str, params: tuple = (),
                       *, fetchone: bool = False, cache_tag: str = ""):
        """Execute a query on the persistent connection, return results.

        Returns:
          - If fetchone=True:  dict | None
          - If fetchone=False: list[dict]
        On any error, kills the connection so next call will reconnect.
        Results are cached — if Fabric is down, stale data is served.
        """
        ck = _cache_key(cache_tag or query, *params) \
            if (cache_tag or params) else _cache_key(query)

        conn = self._get_connection()
        if not conn:
            cached = _cache_get(ck)
            if cached is not None:
                logger.info("Fabric unavailable — serving cached result")
                return cached
            return None if fetchone else []

        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]

            if fetchone:
                row = cursor.fetchone()
                result = dict(zip(columns, row)) if row else None
            else:
                result = [dict(zip(columns, r)) for r in cursor.fetchall()]

            cursor.close()

            if result:
                _cache_set(ck, result)

            return result

        except Exception as e:
            logger.error(f"Fabric query failed: {e}")
            self._last_error = str(e)
            with self._conn_lock:
                self._kill_connection()
            cached = _cache_get(ck)
            if cached is not None:
                logger.info("Fabric query failed — serving cached result")
                return cached
            return None if fetchone else []

    # ── Public API ─────────────────────────────────────────────────

    def search_by_gtm_id(self, gtm_id: str) -> Optional[Dict[str, Any]]:
        """Search by GTM Entry ID (GUID) or Legacy GTM ID (number).
        JOINs Promotion_Details to get promo owner name & email.
        """
        gtm_str = str(gtm_id).strip()

        if gtm_str.isdigit():
            query = f"""
                SELECT o.*,
                       pd.crffc_promoowner,
                       pd.crffc_promoowneremail
                FROM {self.table} o
                LEFT JOIN dbo.Promotion_Details pd
                    ON o.cat_gtmentryid = pd.crffc_gtmentryrecord
                WHERE o.cat_legacygtmentryid = ?
            """
            params = (int(gtm_str),)
        else:
            query = f"""
                SELECT o.*,
                       pd.crffc_promoowner,
                       pd.crffc_promoowneremail
                FROM {self.table} o
                LEFT JOIN dbo.Promotion_Details pd
                    ON o.cat_gtmentryid = pd.crffc_gtmentryrecord
                WHERE o.cat_gtmentryid = ?
            """
            params = (gtm_str,)

        return self._execute_query(query, params, fetchone=True)

    def search_by_promo_code(self, promo_code: str) -> Optional[Dict[str, Any]]:
        """Search for a promotion by promo code."""
        query = f"SELECT * FROM {self.table} WHERE crffc_promocodeid = ?"
        return self._execute_query(query, (promo_code,), fetchone=True)

    def get_all_promotions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all promotions from Fabric."""
        if limit:
            query = f"SELECT TOP {int(limit)} * FROM {self.table} ORDER BY modifiedon DESC"
        else:
            query = f"SELECT * FROM {self.table} ORDER BY modifiedon DESC"
        return self._execute_query(query)

    def search_promotions(self,
                          search_term: Optional[str] = None,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Search promotions with optional filters."""
        where_clauses: list = []
        params: list = []

        if search_term:
            where_clauses.append(
                "(cat_initiativename LIKE ? OR crffc_promocodeid LIKE ?)"
            )
            pat = f"%{search_term}%"
            params.extend([pat, pat])
        if start_date:
            where_clauses.append("cat_startdate >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("cat_enddate <= ?")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        query = (
            f"SELECT TOP {int(limit)} * FROM {self.table} "
            f"WHERE {where_sql} ORDER BY modifiedon DESC"
        )
        return self._execute_query(query, tuple(params))

    def test_connection(self) -> bool:
        """Test the Fabric connection end-to-end."""
        conn = self._get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()
            logger.info(f"Fabric connection OK: {version[0][:60]}...")
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Fabric connection test failed: {e}")
            self._last_error = str(e)
            with self._conn_lock:
                self._kill_connection()
            return False

    def get_last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of connection health for monitoring/debug."""
        with self._circuit_lock:
            circuit_info = {
                'open': self._circuit_open,
                'fail_count': self._circuit_fail_count,
                'cooldown_remaining': None,
            }
            if self._circuit_open and self._circuit_opened_at:
                remaining = self._CIRCUIT_COOLDOWN - \
                    (datetime.now() - self._circuit_opened_at).total_seconds()
                circuit_info['cooldown_remaining'] = max(0, int(remaining))

        with _query_cache_lock:
            cache_info = {
                'entries': len(_query_cache),
                'max_entries': _QUERY_CACHE_MAX_ENTRIES,
                'ttl_minutes': _QUERY_CACHE_TTL,
            }

        return {
            'connected': self._connection is not None,
            'connection_age_s': int(
                (datetime.now() - self._conn_created_at).total_seconds()
            ) if self._conn_created_at else None,
            'auth_method': self._last_auth_method,
            'is_azure': _is_azure(),
            'last_error': self._last_error,
            'token_cached': self._cached_token is not None,
            'token_expires': str(self._token_expiry) if self._token_expiry else None,
            'circuit_breaker': circuit_info,
            'cache': cache_info,
        }


# Singleton instance for easy import
fabric_db = FabricDatabaseManager()
