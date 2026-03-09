"""Microsoft Fabric Data Warehouse manager for ORBIT data.

Provides read access to ORBIT_Reporting_Table in Microsoft Fabric using
Service Principal authentication (OAuth token).

Key design decisions:
- Persistent connection reused across queries (fast path: ~0s overhead)
- Connection auto-expires after 5 minutes to avoid Fabric going stale
- Health check uses a thread-based hard timeout (never hangs Flask)
- Token caching (~50 min, tokens valid ~60 min)
- Query result cache: serves stale data when Fabric is temporarily down
- Circuit breaker: stops retrying a dead connection for a cooldown period
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

# Connection max age in seconds — after this, close and re-establish.
# Fabric endpoints can go stale if idle too long.
_CONN_MAX_AGE = 300   # 5 minutes
_CONNECT_HARD_TIMEOUT = 12   # per-attempt timeout
_HEALTH_CHECK_TIMEOUT = 5    # seconds for SELECT 1
_MAX_CONNECT_ATTEMPTS = 3    # retry up to 3 times on connect failure

# ── Query result cache (module-level, survives across requests) ────────
_query_cache: Dict[str, Dict] = {}
_query_cache_lock = Lock()
_QUERY_CACHE_TTL = 30  # minutes — serve stale data up to this long


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
        _query_cache[key] = {"data": data, "ts": datetime.now()}


class FabricDatabaseManager:
    """Manages a persistent connection to Microsoft Fabric Data Warehouse.

    The connection is reused across queries for performance.  If it goes
    stale, times out, or is older than _CONN_MAX_AGE, it is transparently
    replaced.  All timeouts are enforced from Python (via daemon threads)
    so Flask never hangs — even if the ODBC driver ignores its own timeout
    settings.
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
        self._used_connection_string = None

        # Persistent connection state (protected by _conn_lock)
        self._connection = None
        self._conn_created_at = None
        self._conn_lock = Lock()

        # Cache the last IP that successfully connected to Fabric.
        # On reconnect, we try this IP FIRST (before the DNS race).
        self._last_good_ip = None

        if not all([self.tenant_id, self.client_id, self.client_secret,
                    self.server, self.database]):
            missing = [v for v, val in {
                'FABRIC_TENANT_ID': self.tenant_id,
                'FABRIC_CLIENT_ID': self.client_id,
                'FABRIC_CLIENT_SECRET': self.client_secret,
                'FABRIC_SERVER': self.server,
                'FABRIC_DATABASE': self.database,
            }.items() if not val]
            logger.warning(f"Fabric credentials incomplete. Missing: {', '.join(missing)}")

    # ── Token management ────────────────────────────────────────────

    def _get_access_token(self) -> Optional[bytes]:
        """Get OAuth access token for Fabric, with caching.

        Returns token struct bytes for pyodbc, or None on failure.
        Uses its own lock — never called while holding _conn_lock.
        """
        with self._token_lock:
            if (self._cached_token and self._token_expiry
                    and datetime.now() < self._token_expiry):
                return self._cached_token

            try:
                from azure.identity import ClientSecretCredential

                os.environ['REQUESTS_CA_BUNDLE'] = ''
                os.environ['CURL_CA_BUNDLE'] = ''

                logger.info("Authenticating with Fabric via Service Principal...")
                credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    connection_verify=False,
                )
                token = credential.get_token("https://database.windows.net/.default")

                token_bytes = token.token.encode('utf-16-le')
                token_struct = struct.pack(
                    f'<I{len(token_bytes)}s', len(token_bytes), token_bytes
                )

                self._cached_token = token_struct
                self._token_expiry = datetime.now() + timedelta(minutes=50)
                logger.info("Fabric access token obtained OK")
                return token_struct

            except Exception as e:
                logger.error(f"Fabric token acquisition failed: {e}")
                self._last_error = str(e)
                return None

    # ── Connection management ───────────────────────────────────────

    def _kill_connection(self):
        """Silently close the persistent connection (no lock needed by caller
        if already holding _conn_lock)."""
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
        """Run SELECT 1 on the persistent connection with a hard timeout.

        Returns True if healthy, False otherwise.  Never blocks longer than
        _HEALTH_CHECK_TIMEOUT seconds.
        """
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
        """Return True if we should attempt a connection (circuit closed or cooldown elapsed)."""
        with self._circuit_lock:
            if not self._circuit_open:
                return True
            elapsed = (datetime.now() - self._circuit_opened_at).total_seconds() if self._circuit_opened_at else 999
            if elapsed >= self._CIRCUIT_COOLDOWN:
                logger.info("Circuit breaker cooldown elapsed — retrying Fabric")
                self._circuit_open = False
                self._circuit_fail_count = 0
                return True
            logger.warning(f"Circuit breaker OPEN — skipping Fabric ({int(self._CIRCUIT_COOLDOWN - elapsed)}s until retry)")
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
                logger.warning(f"Circuit breaker TRIPPED after {self._circuit_fail_count} failures")

    def _open_connection(self):
        """Open a new pyodbc connection to Fabric with retry + hard timeout.

        Returns a connection or None.  Each attempt is capped at
        _CONNECT_HARD_TIMEOUT seconds via a daemon thread so we never block
        on a bad Traffic Manager IP.  Respects circuit breaker state.
        """
        if not self._circuit_check():
            return None

        import pyodbc

        # Get token *before* taking _conn_lock (avoids lock ordering issues)
        token_struct = self._get_access_token()
        if not token_struct:
            return None

        connection_string = (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.server},{self.port};"
            f"DATABASE={self.database};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=yes;"
            f"Connection Timeout={_CONNECT_HARD_TIMEOUT};"
            f"Login Timeout={_CONNECT_HARD_TIMEOUT};"
        )
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
                logger.info(f"Fabric connected in {elapsed:.1f}s (attempt {attempt})")
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

            if attempt < _MAX_CONNECT_ATTEMPTS:
                time.sleep(0.5)

        self._circuit_record_failure()
        return None

    def _get_connection(self):
        """Get a healthy persistent connection, creating one if needed.

        This is the ONLY method that touches _conn_lock.
        Lock is held briefly — just for the health check and swap.
        The expensive _open_connection() call happens OUTSIDE the lock.
        """
        with self._conn_lock:
            # Fast path: reuse existing healthy connection
            if self._is_connection_fresh():
                if self._health_check():
                    return self._connection
                # Health check failed — kill it
                logger.warning("Fabric persistent connection failed health check")
                self._kill_connection()
            elif self._connection:
                # Connection expired
                logger.info("Fabric persistent connection expired, reconnecting")
                self._kill_connection()

        # Slow path: open new connection (outside lock — can take up to 40s)
        new_conn = self._open_connection()

        with self._conn_lock:
            if new_conn:
                # If someone else reconnected while we were connecting,
                # close the extra and use theirs (unlikely but safe)
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

    # ── Query helpers ───────────────────────────────────────────────

    def _execute_query(self, query: str, params: tuple = (),
                       *, fetchone: bool = False, cache_tag: str = ""):
        """Execute a query on the persistent connection, return results.

        Returns:
          - If fetchone=True:  dict | None
          - If fetchone=False: list[dict]
        On any error, kills the connection so next call will reconnect.
        Results are cached — if Fabric is down, stale data is served.
        """
        ck = _cache_key(cache_tag or query, *params) if (cache_tag or params) else _cache_key(query)

        conn = self._get_connection()
        if not conn:
            # Fabric unavailable — try serving cached data
            cached = _cache_get(ck)
            if cached is not None:
                logger.info("Fabric down — serving cached result")
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

            # Cache successful results
            if result:
                _cache_set(ck, result)

            return result

        except Exception as e:
            logger.error(f"Fabric query failed: {e}")
            self._last_error = str(e)
            with self._conn_lock:
                self._kill_connection()
            # Try cached data before returning empty
            cached = _cache_get(ck)
            if cached is not None:
                logger.info("Fabric query failed — serving cached result")
                return cached
            return None if fetchone else []

    # ── Public API ──────────────────────────────────────────────────

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
        """Test the Fabric connection."""
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


# Singleton instance for easy import
fabric_db = FabricDatabaseManager()
