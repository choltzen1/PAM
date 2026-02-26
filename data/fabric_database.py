"""Microsoft Fabric Data Warehouse manager for ORBIT data.

Provides read access to ORBIT_Reporting_Table in Microsoft Fabric using 
Service Principal authentication. Designed to be a drop-in replacement for
orbit_database.py with the same interface.

Key Features:
- OAuth token-based authentication (Service Principal)
- Token caching (~1 hour validity)
- Thread-safe connection management
- Same query interface as OrbitDatabaseManager
- Query result caching (survives transient Fabric outages)
- Circuit breaker (avoids hammering a dead connection)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import struct
import time
import hashlib
import json
import logging
from datetime import datetime, timedelta
from threading import Lock
from dotenv import load_dotenv, find_dotenv
from functools import wraps

logger = logging.getLogger(__name__)


# ── Query result cache (module-level, survives across requests) ────────────
_query_cache: Dict[str, Dict] = {}        # key -> {"data": ..., "ts": datetime}
_query_cache_lock = Lock()
QUERY_CACHE_TTL_MINUTES = 30              # serve stale data up to 30 min

def _cache_key(method: str, *args) -> str:
    """Build a deterministic cache key from method name + arguments."""
    raw = f"{method}:" + "|".join(str(a) for a in args)
    return hashlib.md5(raw.encode()).hexdigest()

def _cache_get(key: str):
    """Return cached data if fresh enough, else None."""
    with _query_cache_lock:
        entry = _query_cache.get(key)
        if entry and datetime.now() < entry["ts"] + timedelta(minutes=QUERY_CACHE_TTL_MINUTES):
            return entry["data"]
    return None

def _cache_set(key: str, data):
    """Store data in the query cache."""
    with _query_cache_lock:
        _query_cache[key] = {"data": data, "ts": datetime.now()}


class FabricDatabaseManager:
    """Manages Microsoft Fabric Data Warehouse connections for ORBIT data.
    
    Resilience features:
    - Circuit breaker: if connection fails, skip retries for a cooldown period
    - Query cache: successful results are cached and served when Fabric is down
    - Short timeouts: web-friendly (15s connect, not 60s)
    - Retry with backoff: 2 retries with 2s, 5s delays
    """
    
    # Class-level token cache (shared across instances)
    _cached_token = None
    _token_expiry = None
    _token_lock = Lock()
    
    # Class-level persistent connection (shared across instances)
    _connection = None
    _connection_lock = Lock()
    _connection_last_used = None

    # ── Circuit breaker state (class-level) ─────────────────────────
    _circuit_open = False          # True = skip connection attempts
    _circuit_opened_at = None      # When the circuit was tripped
    _circuit_fail_count = 0        # Consecutive failures
    _circuit_lock = Lock()
    CIRCUIT_COOLDOWN_SECONDS = 120  # Wait 2 min before retrying after failure
    CIRCUIT_FAIL_THRESHOLD = 2     # Trip after 2 consecutive failures
    
    def __init__(self):
        """Initialize Fabric connection parameters from environment"""
        # Load environment variables
        try:
            env_path = find_dotenv()
            if env_path:
                load_dotenv(env_path)
        except Exception:
            pass
        
        # Service Principal credentials
        self.tenant_id = os.getenv('FABRIC_TENANT_ID')
        self.client_id = os.getenv('FABRIC_CLIENT_ID')
        self.client_secret = os.getenv('FABRIC_CLIENT_SECRET')
        
        # Fabric Data Warehouse connection details
        self.server = os.getenv('FABRIC_SERVER')
        self.database = os.getenv('FABRIC_DATABASE')
        self.port = '1433'
        self.driver = 'ODBC Driver 18 for SQL Server'
        
        # ORBIT table name in Fabric
        self.table = 'dbo.ORBIT_Reporting_Table'
        
        # Error tracking
        self._last_error = None
        self._used_connection_string = None
        
        # Validate required credentials
        if not all([self.tenant_id, self.client_id, self.client_secret, self.server, self.database]):
            missing = []
            if not self.tenant_id: missing.append('FABRIC_TENANT_ID')
            if not self.client_id: missing.append('FABRIC_CLIENT_ID')
            if not self.client_secret: missing.append('FABRIC_CLIENT_SECRET')
            if not self.server: missing.append('FABRIC_SERVER')
            if not self.database: missing.append('FABRIC_DATABASE')
            logger.warning(f"Fabric credentials incomplete. Missing: {', '.join(missing)}")
    
    def _get_access_token(self) -> Optional[bytes]:
        """Get OAuth access token for Fabric, with caching
        
        Supports multiple authentication methods:
        1. Managed Identity (preferred for Azure App Service)
        2. Service Principal with client secret (fallback for local dev)
        
        Returns:
            Token struct bytes for pyodbc, or None if authentication fails
        """
        with self._token_lock:
            # Check if cached token is still valid
            if self._cached_token and self._token_expiry:
                if datetime.now() < self._token_expiry:
                    logger.debug("Using cached Fabric access token")
                    return self._cached_token
            
            # Need to get a new token
            try:
                from azure.identity import DefaultAzureCredential, ClientSecretCredential, ManagedIdentityCredential
                
                # Disable SSL verification for corporate networks (local dev)
                os.environ['REQUESTS_CA_BUNDLE'] = ''
                os.environ['CURL_CA_BUNDLE'] = ''
                
                credential = None
                auth_method = "Unknown"
                
                # Check if running on Azure (WEBSITE_INSTANCE_ID is set on Azure App Service)
                is_azure = os.getenv('WEBSITE_INSTANCE_ID') is not None
                
                # Option 1: Use Managed Identity on Azure App Service (most reliable)
                if is_azure:
                    try:
                        logger.info("Detected Azure environment, trying Managed Identity...")
                        credential = ManagedIdentityCredential()
                        # Test the credential
                        credential.get_token("https://database.windows.net/.default")
                        auth_method = "Managed Identity"
                        logger.info("✅ Using Managed Identity authentication")
                    except Exception as mi_err:
                        logger.warning(f"Managed Identity failed: {mi_err}, falling back to Service Principal")
                        credential = None
                
                # Option 2: Use Service Principal if Managed Identity failed or not on Azure
                if credential is None and self.client_id and self.client_secret:
                    logger.info("Authenticating with Fabric using Service Principal...")
                    credential = ClientSecretCredential(
                        tenant_id=self.tenant_id,
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                        connection_verify=False
                    )
                    auth_method = "Service Principal"
                
                # Option 3: Try DefaultAzureCredential as last resort
                if credential is None:
                    logger.info("Trying DefaultAzureCredential...")
                    credential = DefaultAzureCredential(
                        exclude_interactive_browser_credential=True,
                        connection_verify=False
                    )
                    auth_method = "DefaultAzureCredential"
                
                # Get token for SQL Database scope
                token = credential.get_token("https://database.windows.net/.default")
                
                # Convert to pyodbc format
                token_bytes = token.token.encode('utf-16-le')
                token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
                
                # Cache the token (expires in ~1 hour, cache for 50 minutes to be safe)
                self._cached_token = token_struct
                self._token_expiry = datetime.now() + timedelta(minutes=50)
                
                logger.info(f"✅ Successfully obtained Fabric access token via {auth_method}")
                return token_struct
                
            except Exception as e:
                logger.error(f"Failed to obtain Fabric access token: {e}")
                self._last_error = str(e)
                return None
    
    def _get_connection(self, _retry_count=0):
        """Get or establish persistent connection to Fabric Data Warehouse.
        
        Includes circuit breaker + retry logic with exponential backoff.
        Timeouts are web-friendly (15s connect) so pages don't hang.
        
        Returns:
            pyodbc connection object or None
        """
        MAX_RETRIES = 2
        RETRY_DELAYS = [2, 5]  # seconds between retries

        # ── Circuit breaker check ──────────────────────────────────
        with self._circuit_lock:
            if self._circuit_open:
                elapsed = (datetime.now() - self._circuit_opened_at).total_seconds() if self._circuit_opened_at else 999
                if elapsed < self.CIRCUIT_COOLDOWN_SECONDS:
                    logger.warning(f"Circuit breaker OPEN – skipping Fabric connection ({int(self.CIRCUIT_COOLDOWN_SECONDS - elapsed)}s until retry)")
                    return None
                else:
                    logger.info("Circuit breaker cooldown expired – attempting reconnection")
                    self._circuit_open = False
                    self._circuit_fail_count = 0
        
        with self._connection_lock:
            # Check if connection exists and is alive
            if self._connection:
                try:
                    cursor = self._connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    self._connection_last_used = datetime.now()
                    # Reset circuit breaker on success
                    with self._circuit_lock:
                        self._circuit_fail_count = 0
                        self._circuit_open = False
                    return self._connection
                except Exception:
                    logger.warning("Existing Fabric connection is dead, recreating...")
                    try:
                        self._connection.close()
                    except:
                        pass
                    self._connection = None
            
            # Create new persistent connection with retries
            import pyodbc
            
            # Get access token (force refresh if this is a retry)
            if _retry_count > 0:
                self._cached_token = None
                self._token_expiry = None
            
            token_struct = self._get_access_token()
            if not token_struct:
                return None
            
            connection_string = (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.server},{self.port};"
                f"DATABASE={self.database};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=yes;"
                f"Connection Timeout=15;"
                f"Login Timeout=15;"
            )
            self._used_connection_string = connection_string
            
            attempt = _retry_count + 1
            logger.info(f"Connecting to Fabric (attempt {attempt}/{MAX_RETRIES + 1}): {self.server}")
            
            try:
                self._connection = pyodbc.connect(
                    connection_string,
                    attrs_before={1256: token_struct}  # SQL_COPT_SS_ACCESS_TOKEN
                )
                
                self._connection_last_used = datetime.now()
                logger.info("✅ Established persistent Fabric Data Warehouse connection")
                # Reset circuit breaker on success
                with self._circuit_lock:
                    self._circuit_fail_count = 0
                    self._circuit_open = False
                return self._connection
                
            except Exception as e:
                self._last_error = str(e)
                if _retry_count < MAX_RETRIES:
                    delay = RETRY_DELAYS[_retry_count]
                    logger.warning(f"Fabric connection attempt {attempt} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                    self._connection = None
                # Release lock before recursive retry
        
        # Retry outside the lock
        if _retry_count < MAX_RETRIES:
            return self._get_connection(_retry_count=_retry_count + 1)
        
        # All retries exhausted – trip the circuit breaker
        with self._circuit_lock:
            self._circuit_fail_count += 1
            if self._circuit_fail_count >= self.CIRCUIT_FAIL_THRESHOLD:
                self._circuit_open = True
                self._circuit_opened_at = datetime.now()
                logger.error(f"Circuit breaker TRIPPED – Fabric unreachable. Cooling down for {self.CIRCUIT_COOLDOWN_SECONDS}s")
        
        logger.error(f"Failed to connect to Fabric after {MAX_RETRIES + 1} attempts: {self._last_error}")
        return None
    
    def search_by_promo_code(self, promo_code: str) -> Optional[Dict[str, Any]]:
        """Search for a promotion by promo code (cached).
        
        Args:
            promo_code: The promotion code to search for
            
        Returns:
            Dictionary of promotion data or None if not found
        """
        key = _cache_key("search_by_promo_code", promo_code)
        cached = _cache_get(key)
        if cached is not None:
            logger.debug(f"Cache HIT for promo code {promo_code}")
            return cached

        conn = self._get_connection()
        if not conn:
            # Fabric is down – return stale cache if available
            with _query_cache_lock:
                entry = _query_cache.get(key)
                if entry:
                    logger.warning(f"Fabric down – serving STALE cache for promo code {promo_code}")
                    return entry["data"]
            return None
        
        try:
            cursor = conn.cursor()
            query = f"SELECT * FROM {self.table} WHERE crffc_promocodeid = ?"
            cursor.execute(query, (promo_code,))
            
            row = cursor.fetchone()
            if not row:
                cursor.close()
                _cache_set(key, None)
                return None
            
            # Convert row to dictionary
            columns = [column[0] for column in cursor.description]
            result = dict(zip(columns, row))
            
            cursor.close()
            _cache_set(key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error searching for promo code {promo_code}: {e}")
            self._last_error = str(e)
            return None
    
    def search_by_gtm_id(self, gtm_id: str) -> Optional[Dict[str, Any]]:
        """Search for a promotion by GTM Entry ID (GUID) or Legacy GTM ID (number). Cached.
        
        Args:
            gtm_id: The GTM Entry ID (GUID) or Legacy GTM ID (number) to search for
            
        Returns:
            Dictionary of promotion data or None if not found
        """
        key = _cache_key("search_by_gtm_id", gtm_id)
        cached = _cache_get(key)
        if cached is not None:
            logger.debug(f"Cache HIT for GTM ID {gtm_id}")
            return cached

        conn = self._get_connection()
        if not conn:
            with _query_cache_lock:
                entry = _query_cache.get(key)
                if entry:
                    logger.warning(f"Fabric down – serving STALE cache for GTM ID {gtm_id}")
                    return entry["data"]
            return None
        
        try:
            cursor = conn.cursor()
            
            # Try to determine if this is a legacy ID (numeric) or GUID
            # Legacy IDs are typically 5-6 digit numbers
            gtm_str = str(gtm_id).strip()
            
            # JOIN with Promotion_Details to get promo owner info
            # Use LEFT JOIN so we still get results even if no promo code assigned
            if gtm_str.isdigit():
                # Search by legacy GTM ID
                query = f"""
                    SELECT o.*, 
                           pd.crffc_promoowner, 
                           pd.crffc_promoowneremail
                    FROM {self.table} o
                    LEFT JOIN dbo.Promotion_Details pd ON o.cat_gtmentryid = pd.crffc_gtmentryrecord
                    WHERE o.cat_legacygtmentryid = ?
                """
                cursor.execute(query, (int(gtm_str),))
            else:
                # Search by GTM Entry ID (GUID)
                query = f"""
                    SELECT o.*, 
                           pd.crffc_promoowner, 
                           pd.crffc_promoowneremail
                    FROM {self.table} o
                    LEFT JOIN dbo.Promotion_Details pd ON o.cat_gtmentryid = pd.crffc_gtmentryrecord
                    WHERE o.cat_gtmentryid = ?
                """
                cursor.execute(query, (gtm_str,))
            
            row = cursor.fetchone()
            if not row:
                cursor.close()
                _cache_set(key, None)
                return None
            
            columns = [column[0] for column in cursor.description]
            result = dict(zip(columns, row))
            
            cursor.close()
            _cache_set(key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error searching for GTM ID {gtm_id}: {e}")
            self._last_error = str(e)
            return None
    
    def get_all_promotions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all promotions from Fabric (cached).
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of promotion dictionaries
        """
        key = _cache_key("get_all_promotions", limit)
        cached = _cache_get(key)
        if cached is not None:
            return cached

        conn = self._get_connection()
        if not conn:
            with _query_cache_lock:
                entry = _query_cache.get(key)
                if entry:
                    logger.warning("Fabric down – serving STALE cache for get_all_promotions")
                    return entry["data"]
            return []
        
        try:
            cursor = conn.cursor()
            
            if limit:
                query = f"SELECT TOP {limit} * FROM {self.table} ORDER BY modifiedon DESC"
            else:
                query = f"SELECT * FROM {self.table} ORDER BY modifiedon DESC"
            
            cursor.execute(query)
            
            columns = [column[0] for column in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            
            logger.info(f"Retrieved {len(results)} promotions from Fabric")
            _cache_set(key, results)
            return results
            
        except Exception as e:
            logger.error(f"Error getting all promotions: {e}")
            self._last_error = str(e)
            return []
    
    def search_promotions(self, 
                         search_term: Optional[str] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """Search promotions with optional filters (cached).
        
        Args:
            search_term: Search in initiative name or promo code
            start_date: Filter by start date (YYYY-MM-DD)
            end_date: Filter by end date (YYYY-MM-DD)
            limit: Maximum number of results
            
        Returns:
            List of matching promotion dictionaries
        """
        key = _cache_key("search_promotions", search_term, start_date, end_date, limit)
        cached = _cache_get(key)
        if cached is not None:
            return cached

        conn = self._get_connection()
        if not conn:
            with _query_cache_lock:
                entry = _query_cache.get(key)
                if entry:
                    logger.warning("Fabric down – serving STALE cache for search_promotions")
                    return entry["data"]
            return []
        
        try:
            cursor = conn.cursor()
            
            # Build query with filters
            where_clauses = []
            params = []
            
            if search_term:
                where_clauses.append("(cat_initiativename LIKE ? OR crffc_promocodeid LIKE ?)")
                search_pattern = f"%{search_term}%"
                params.extend([search_pattern, search_pattern])
            
            if start_date:
                where_clauses.append("cat_startdate >= ?")
                params.append(start_date)
            
            if end_date:
                where_clauses.append("cat_enddate <= ?")
                params.append(end_date)
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            query = f"SELECT TOP {limit} * FROM {self.table} WHERE {where_sql} ORDER BY modifiedon DESC"
            
            cursor.execute(query, params)
            
            columns = [column[0] for column in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            
            logger.info(f"Search returned {len(results)} promotions")
            _cache_set(key, results)
            return results
            
        except Exception as e:
            logger.error(f"Error searching promotions: {e}")
            self._last_error = str(e)
            return []
    
    def test_connection(self) -> bool:
        """Test the Fabric connection
        
        Returns:
            True if connection successful, False otherwise
        """
        conn = self._get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()
            logger.info(f"Fabric connection test successful: {version[0][:50]}...")
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Fabric connection test failed: {e}")
            self._last_error = str(e)
            return False
    
    def get_last_error(self) -> Optional[str]:
        """Get the last error message"""
        return self._last_error

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of connection health for debug endpoints."""
        with self._circuit_lock:
            circuit_info = {
                'circuit_open': self._circuit_open,
                'fail_count': self._circuit_fail_count,
                'opened_at': str(self._circuit_opened_at) if self._circuit_opened_at else None,
                'cooldown_remaining': None,
            }
            if self._circuit_open and self._circuit_opened_at:
                remaining = self.CIRCUIT_COOLDOWN_SECONDS - (datetime.now() - self._circuit_opened_at).total_seconds()
                circuit_info['cooldown_remaining'] = max(0, int(remaining))

        with _query_cache_lock:
            cache_info = {
                'cached_queries': len(_query_cache),
                'cache_ttl_minutes': QUERY_CACHE_TTL_MINUTES,
            }

        return {
            'connected': self._connection is not None,
            'last_used': str(self._connection_last_used) if self._connection_last_used else None,
            'last_error': self._last_error,
            'token_cached': self._cached_token is not None,
            'token_expires': str(self._token_expiry) if self._token_expiry else None,
            'circuit_breaker': circuit_info,
            'cache': cache_info,
        }


# Singleton instance for easy import
fabric_db = FabricDatabaseManager()
