"""Microsoft Fabric Data Warehouse manager for ORBIT data.

Provides read access to ORBIT_Reporting_Table in Microsoft Fabric using 
Service Principal authentication. Designed to be a drop-in replacement for
orbit_database.py with the same interface.

Key Features:
- OAuth token-based authentication (Service Principal)
- Token caching (~1 hour validity)
- Thread-safe connection management
- Same query interface as OrbitDatabaseManager
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import struct
import time
import logging
from datetime import datetime, timedelta
from threading import Lock
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

class FabricDatabaseManager:
    """Manages Microsoft Fabric Data Warehouse connections for ORBIT data"""
    
    # Class-level token cache (shared across instances)
    _cached_token = None
    _token_expiry = None
    _token_lock = Lock()
    
    # Class-level persistent connection (shared across instances)
    _connection = None
    _connection_lock = Lock()
    _connection_last_used = None
    
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
    
    def _get_connection(self):
        """Get or establish persistent connection to Fabric Data Warehouse
        
        Returns:
            pyodbc connection object or None
        """
        with self._connection_lock:
            # Check if connection exists and is alive
            if self._connection:
                try:
                    # Test connection with a simple query
                    cursor = self._connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    self._connection_last_used = datetime.now()
                    return self._connection
                except Exception:
                    # Connection is dead, will recreate below
                    logger.warning("Existing Fabric connection is dead, recreating...")
                    try:
                        self._connection.close()
                    except:
                        pass
                    self._connection = None
            
            # Create new persistent connection
            try:
                import pyodbc
                
                # Get access token
                token_struct = self._get_access_token()
                if not token_struct:
                    return None
                
                # Build connection string (Fabric-specific requirements)
                # Note: Fabric Data Warehouse requires specific TLS settings
                # - HostNameInCertificate must match the datawarehouse subdomain
                # - TrustServerCertificate=yes may be needed for some corporate networks
                connection_string = (
                    f"DRIVER={{{self.driver}}};"
                    f"SERVER={self.server},{self.port};"
                    f"DATABASE={self.database};"
                    f"Encrypt=yes;"
                    f"TrustServerCertificate=yes;"
                    f"Connection Timeout=60;"
                    f"Login Timeout=60;"
                )
                
                self._used_connection_string = connection_string
                logger.info(f"Connecting to Fabric: {self.server}")
                
                # Connect with access token
                self._connection = pyodbc.connect(
                    connection_string,
                    attrs_before={1256: token_struct}  # SQL_COPT_SS_ACCESS_TOKEN
                )
                
                self._connection_last_used = datetime.now()
                logger.info("✅ Established persistent Fabric Data Warehouse connection")
                return self._connection
                
            except Exception as e:
                logger.error(f"Failed to connect to Fabric: {e}")
                self._last_error = str(e)
                return None
    
    def search_by_promo_code(self, promo_code: str) -> Optional[Dict[str, Any]]:
        """Search for a promotion by promo code
        
        Args:
            promo_code: The promotion code to search for
            
        Returns:
            Dictionary of promotion data or None if not found
        """
        conn = self._get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            query = f"SELECT * FROM {self.table} WHERE crffc_promocodeid = ?"
            cursor.execute(query, (promo_code,))
            
            row = cursor.fetchone()
            if not row:
                cursor.close()
                return None
            
            # Convert row to dictionary
            columns = [column[0] for column in cursor.description]
            result = dict(zip(columns, row))
            
            cursor.close()
            return result
            
        except Exception as e:
            logger.error(f"Error searching for promo code {promo_code}: {e}")
            self._last_error = str(e)
            return None
    
    def search_by_gtm_id(self, gtm_id: str) -> Optional[Dict[str, Any]]:
        """Search for a promotion by GTM Entry ID (GUID) or Legacy GTM ID (number)
        
        Args:
            gtm_id: The GTM Entry ID (GUID) or Legacy GTM ID (number) to search for
            
        Returns:
            Dictionary of promotion data or None if not found
        """
        conn = self._get_connection()
        if not conn:
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
                return None
            
            columns = [column[0] for column in cursor.description]
            result = dict(zip(columns, row))
            
            cursor.close()
            return result
            
        except Exception as e:
            logger.error(f"Error searching for GTM ID {gtm_id}: {e}")
            self._last_error = str(e)
            return None
    
    def get_all_promotions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all promotions from Fabric
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of promotion dictionaries
        """
        conn = self._get_connection()
        if not conn:
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
        """Search promotions with optional filters
        
        Args:
            search_term: Search in initiative name or promo code
            start_date: Filter by start date (YYYY-MM-DD)
            end_date: Filter by end date (YYYY-MM-DD)
            limit: Maximum number of results
            
        Returns:
            List of matching promotion dictionaries
        """
        conn = self._get_connection()
        if not conn:
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


# Singleton instance for easy import
fabric_db = FabricDatabaseManager()
