import pandas as pd
from sqlalchemy import create_engine, text
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import logging
import os
import json

logger = logging.getLogger(__name__)

from .field_map import FIELD_DB_MAP, canonical_to_physical, quote_identifier, EDITABLE_CANONICAL_FIELDS

class DatabaseManager:
    """Manages SQL Server database connections and queries for live promo data"""
    
    def __init__(self):
        # Load connection parameters from environment for security
        self.server = os.getenv('PAM_DB_SERVER', 'localhost')
        self.database = os.getenv('PAM_DB_DATABASE', 'PromoQuality')
        self.username = os.getenv('PAM_DB_USERNAME', '')
        self.password = os.getenv('PAM_DB_PASSWORD', '')
        self.driver = os.getenv('PAM_DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        self.encrypt = os.getenv('PAM_DB_ENCRYPT', 'no').lower()  # yes/no
        self.trust_cert = os.getenv('PAM_DB_TRUST_CERT', 'yes').lower()  # yes/no
        self.timeout = int(os.getenv('PAM_DB_LOGIN_TIMEOUT', '15'))
        # PAM promotions table (where generated promos are stored)
        self.source_table = os.getenv('PAM_SOURCE_TABLE', '[PAM].[PAM_Orbit_Data_Updated]')
        # Note: Orbit data now comes from OrbitDatabaseManager (Fabric or fallback to local SQL)
        self._engine = None
        # Diagnostics persistence moved to SQL Server `PAM.date_diagnostics_history`.
        # Local SQLite has been deprecated and removed.
        self._diag_db_path = None
        # Threshold from environment
        self.invalid_ratio_threshold = float(os.environ.get('INVALID_DATE_RATIO_WARN_THRESHOLD', '0.10'))

    def _ensure_diag_tables(self):
        """
        Previously diagnostics were persisted locally during early development.
        Diagnostics persistence is now hosted in SQL Server and should be
        created by applying the appropriate DDL to your SQL Server instance.

        This method intentionally does not perform any local SQLite writes and
        only logs guidance. If SQL Server is available and the `get_engine`
        connection succeeds, the caller may run the relevant DDL from `sql/`.
        """
        # No-op: SQL Server should host diagnostic tables. See sql/create_promo_history_denormalized.sql
        logger.debug("_ensure_diag_tables: local SQLite deprecated; ensure SQL Server tables exist instead")
    
    def reset_engine(self):
        """Dispose existing engine and force fresh connection on next use.
        
        Use this when you suspect stale/broken connections (common with Azure Hybrid Connection).
        """
        if self._engine:
            try:
                self._engine.dispose()
                logger.info("Database engine disposed, connection pool cleared")
            except Exception as e:
                logger.warning(f"Error disposing engine: {e}")
            self._engine = None
    
    def get_engine(self, retry_count: int = 3, retry_delay: float = 2.0):
        """Create and return SQLAlchemy engine with retry logic for Azure resilience.
        
        Args:
            retry_count: Number of connection attempts (default 3)
            retry_delay: Seconds between retries (default 2.0)
        """
        if self._engine is None:
            import time
            last_error: Optional[Exception] = None
            
            for attempt in range(1, retry_count + 1):
                try:
                    server_part = self.server  # Port (if any) is already embedded in server value
                    # Build raw ODBC string
                    odbc_elems = [
                        f'DRIVER={{{self.driver}}}',
                        f'SERVER={server_part}',
                        f'DATABASE={self.database}'
                    ]
                    if self.username:
                        odbc_elems.append(f'UID={self.username}')
                        odbc_elems.append(f'PWD={self.password}')
                    else:
                        # Integrated security fallback (Windows auth)
                        odbc_elems.append('Trusted_Connection=yes')
                    if self.encrypt in ('yes','true','1'):
                        odbc_elems.append('Encrypt=yes')
                    else:
                        odbc_elems.append('Encrypt=no')
                    if self.trust_cert in ('yes','true','1'):
                        odbc_elems.append('TrustServerCertificate=yes')
                    odbc_elems.append(f'LoginTimeout={self.timeout}')
                    odbc_str = ';'.join(odbc_elems)
                    masked = odbc_str.replace(self.password, '***') if self.password else odbc_str
                    
                    if attempt == 1:
                        logger.info(f"Attempting DB connect with: {masked}")
                    else:
                        logger.info(f"DB connection retry attempt {attempt}/{retry_count}")
                    
                    params = urllib.parse.quote_plus(odbc_str)
                    # Tune connection pooling: adjust via env if needed
                    pool_size = int(os.getenv('SQLALCHEMY_POOL_SIZE', '10'))
                    max_overflow = int(os.getenv('SQLALCHEMY_MAX_OVERFLOW', '10'))
                    recycle = int(os.getenv('SQLALCHEMY_POOL_RECYCLE', '1800'))  # seconds
                    
                    if attempt == 1:
                        logger.info(f"SQLAlchemy pool configured: pool_size={pool_size} max_overflow={max_overflow} recycle={recycle}s pre_ping=True")
                    
                    self._engine = create_engine(
                        f'mssql+pyodbc:///?odbc_connect={params}',
                        pool_pre_ping=True,
                        pool_recycle=recycle,
                        pool_size=pool_size,
                        max_overflow=max_overflow
                    )
                    # Test connection
                    with self._engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    logger.info("Database connection established ✅")
                    return self._engine
                    
                except Exception as e:
                    last_error = e
                    self._engine = None  # Reset on failure
                    
                    # Check if error is retryable (network/timeout issues)
                    error_str = str(e).lower()
                    is_retryable = any(hint in error_str for hint in [
                        'timeout', 'timed out', 'network', 'connection', 
                        'tcp', 'communication link', 'server is not found',
                        'cannot open database', 'login timeout'
                    ])
                    
                    if attempt < retry_count and is_retryable:
                        logger.warning(f"Connection attempt {attempt} failed (retryable): {e}")
                        logger.info(f"Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                    else:
                        logger.error(f"Failed to connect to database (attempt {attempt}): {e}")
                        if not is_retryable:
                            logger.error("Error is not retryable (likely credentials or config issue)")
                        break
            
            # All retries exhausted
            logger.error("Troubleshooting tips: 1) Verify server/port reachable (ping / Test-NetConnection) 2) Confirm ODBC driver installed 3) Check firewall/VPN 4) Validate credentials.")
            logger.error("For Azure App Service: Check Hybrid Connection Manager status in Azure Portal > Networking")
            if last_error is not None:
                raise last_error
            raise ConnectionError("Failed to connect to database: no exception details were captured during retries.")
        
        return self._engine
    
    def _is_transient_error(self, error: Exception) -> bool:
        """Check if an error is transient and worth retrying."""
        error_str = str(error).lower()
        return any(hint in error_str for hint in [
            'timeout', 'timed out', 'network', 'communication link',
            'tcp', 'server is not found', 'connection', 'link failure',
            'cannot open database', 'login timeout', 'transport-level error',
            'a network-related or instance-specific error'
        ])
    
    def get_dataframe(self, sql: str, params: Optional[dict] = None, retry_on_failure: bool = True) -> pd.DataFrame:
        """Execute SQL query and return DataFrame with transient error retry.
        
        Args:
            sql: SQL query to execute
            params: Optional query parameters
            retry_on_failure: If True, retry once with fresh connection on transient errors
        """
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except Exception as e:
            if retry_on_failure and self._is_transient_error(e):
                logger.warning(f"Query failed with transient error, retrying with fresh connection: {e}")
                self.reset_engine()
                try:
                    engine = self.get_engine()
                    with engine.connect() as conn:
                        return pd.read_sql(text(sql), conn, params=params or {})
                except Exception as retry_error:
                    logger.error(f"Query retry also failed: {retry_error}")
                    raise retry_error
            logger.error(f"Query execution failed: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    def get_all_promos(self) -> List[Dict[str, Any]]:
        """Fetch all promotions from PAM_Orbit_Data table"""
        return self.get_promos_by_execution_type("RDC")

    def get_promo_extras(self, code: str) -> Dict[str, Any]:
        """Compatibility shim for legacy extras API.

        Extras are no longer persisted separately in the DB-backed model,
        so this returns an empty mapping by default.
        """
        return {}

    def upsert_promo_extras(self, code: str, extras: Dict[str, Any], user: str = "System") -> bool:
        """Compatibility shim for legacy extras API.

        Callers may still invoke this method; extras are now modeled through
        base promo fields, so this is a safe no-op.
        """
        return True

    # (Duplicate get_highest_sequential_promo_code removed)

    def get_highest_sequential_promo_code(self) -> Optional[str]:
        """Return the highest promo code matching pattern ^[A-Z][0-9]{1,4}$ (one letter + digits).

        We rely on DB ordering but also perform regex parsing to ensure correctness.
        Returns None if no matching codes found or on error.
        """
        try:
            # Efficient: pull only code column; ordering DESC to hit highest early
            sql = f"SELECT TOP 200 code FROM {self.source_table} WITH (NOLOCK) WHERE code IS NOT NULL ORDER BY code DESC"
            df = self.get_dataframe(sql)
            import re
            pat = re.compile(r'^[A-Z]([0-9]{1,4})$')
            best = None
            best_letter = ''
            best_num = -1
            for raw in df['code'].dropna().tolist():
                code = str(raw).strip().upper()
                m = pat.match(code)
                if not m:
                    continue
                letter = code[0]
                num = int(m.group(1))
                # Order by letter then numeric; primary expectation is single active letter (e.g., R)
                if best is None:
                    best = code; best_letter = letter; best_num = num; continue
                if letter > best_letter or (letter == best_letter and num > best_num):
                    best = code; best_letter = letter; best_num = num
            return best
        except Exception:
            return None
    
    def get_promos_by_execution_type(self, execution_type: str) -> List[Dict[str, Any]]:
        """Fetch promotions filtered by Desired_Execution type (RDC, SPE, Rebate)."""
        # NOTE: Some legacy environments used a misspelled column 'promo_srart_date'. The current
        # table uses 'promo_start_date'. We select the correct name and alias for downstream code.
        sql = f"""
            SELECT 
                code,
                Owner,
                [bill facing name] as bill_facing_name,
                orbit_id,
                description,
                promo_notes,
                discount,
                amount,
                nseip_drop,
                dcd_web_cart,
                product_type,
                bogo,
                fpd_display_promo,
                on_menu,
                market_group,
                store_group,
                promo_start_date AS promo_start_date,
                promo_end_date,
                comm_end_date,
                promo_duration,
                delay_time,
                application_grace_period,
                device_sales_type,
                activation_type,
                active_line_required,
                maintain_soc,
                crffc_maintainactivelinedev,
                limit_per_ban,
                soc_grouping,
                account_type,
                sales_application,
                operator_id,
                sku_group_id,
                device_status_group_id,
                clawback_indicator,
                Broken_Trade,
                Anticipated_volume_take_rates_total,
                Desired_Execution,
                Status,
                crffc_eligibletradeindevices,
                cat_lobchannelhorizontalname,
                cat_additionaleligibilityrequirementsname,
                cat_eligibledevices,
                cat_channelsname,
                cat_description
            FROM {self.source_table} WITH (NOLOCK)
            WHERE Desired_Execution = :execution_type
            ORDER BY code DESC
        """
        try:
            df = self.get_dataframe(sql, {'execution_type': execution_type})
            return [self._sanitize_record(r) for r in df.to_dict('records')]
        except Exception as e:
            logger.error(f"Failed to fetch {execution_type} promotions: {str(e)}")
            return []

    # --- Optimized paginated query (limited columns, server-side filter & pagination) ---
    def get_paginated_execution_type(
        self,
        execution_type: str,
        page: int,
        per_page: int,
        search: str = "",
        owner_filter: str = "all",
        upcoming_only_when_no_query: bool = False,
        force_upcoming: bool = False,
    ) -> Dict[str, Any]:
        """Return paginated promos with optional search/owner filter.

        Behavior per requirements:
          - Initial (no search & owner_filter=='all'): show ONLY upcoming (start date > today OR NULL)
          - If search or owner filter applied: include launched (and expired) records matching search.
        """
        page = max(page, 1)
        per_page = max(1, min(per_page, 200))
        offset = (page - 1) * per_page
        params: Dict[str, Any] = {
            'execution_type': execution_type,
            'limit': per_page,
            'offset': offset,
        }
        where_clauses = ["Desired_Execution = :execution_type"]

        base_query_mode = not search and (owner_filter == 'all')
        # Apply upcoming filter if explicitly forced OR (no query & upcoming_only_when_no_query)
        if force_upcoming or (base_query_mode and upcoming_only_when_no_query):
            where_clauses.append("(promo_start_date IS NULL OR promo_start_date > CAST(GETUTCDATE() AS DATE))")

        if owner_filter and owner_filter != 'all':
            where_clauses.append("Owner = :owner")
            params['owner'] = owner_filter

        # Search logic
        if search:
            s = search.strip()
            if s and s.isalnum() and len(s) <= 8:  # treat as possible code prefix
                # Use case-insensitive collation to avoid LOWER() on indexed cols
                where_clauses.append("(code COLLATE Latin1_General_CI_AS LIKE :code_prefix OR Owner COLLATE Latin1_General_CI_AS LIKE :wild OR [bill facing name] COLLATE Latin1_General_CI_AS LIKE :wild)")
                params['code_prefix'] = s + '%'
            else:
                where_clauses.append("(code COLLATE Latin1_General_CI_AS LIKE :wild OR Owner COLLATE Latin1_General_CI_AS LIKE :wild OR [bill facing name] COLLATE Latin1_General_CI_AS LIKE :wild)")
            params['wild'] = f"%{s}%"

        where_sql = " AND ".join(where_clauses)

        # Count query
        count_sql = f"SELECT COUNT(1) as cnt FROM {self.source_table} WITH (NOLOCK) WHERE {where_sql}"
        # Data query (order: earliest upcoming first when filtering upcoming, else code desc)
        # Align ordering to index (Desired_Execution, Code DESC) to avoid sorts
        if force_upcoming or (base_query_mode and upcoming_only_when_no_query):
            # Keep code DESC primary ordering; if needed, secondary by promo_start_date is okay but may introduce sort
            order_clause = "ORDER BY code DESC"
        else:
            order_clause = "ORDER BY code DESC"
        data_sql = f"""
            SELECT code, Owner, [bill facing name] as bill_facing_name, orbit_id,
                   promo_start_date, promo_end_date
            FROM {self.source_table} WITH (NOLOCK)
            WHERE {where_sql}
            {order_clause}
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """
        try:
            cnt_df = self.get_dataframe(count_sql, params)
            total_items = int(cnt_df['cnt'].iloc[0]) if not cnt_df.empty else 0
            data_df = self.get_dataframe(data_sql, params)
            rows = [self._sanitize_record(r) for r in data_df.to_dict('records')]
        except Exception as e:
            logger.error(f"Optimized pagination failed for {execution_type}: {e}")
            return {
                'promotions': [],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_items': 0,
                    'total_pages': 0,
                    'has_prev': False,
                    'has_next': False,
                    'prev_num': None,
                    'next_num': None
                },
                'owners': []
            }

        total_pages = (total_items + per_page - 1) // per_page if per_page else 0

        # Distinct owners for dropdown (based on upcoming set for base mode; else from filtered dataset)
        owners: List[str] = []
        try:
            owner_where = "Desired_Execution = :execution_type"
            owner_params = {'execution_type': execution_type}
            if force_upcoming or (base_query_mode and upcoming_only_when_no_query):
                owner_where += " AND (promo_start_date IS NULL OR promo_start_date > CAST(GETUTCDATE() AS DATE))"
            # Try owners cache for base mode; else query
            owner_df = None
            use_cache = base_query_mode
            cached_owners = None
            try:
                # Access admin owners cache if module is loaded
                from admin import routes as admin_routes
                cached = getattr(admin_routes, '_OWNERS_CACHE', {'ts': 0, 'data': []})
                from time import time
                if cached and cached.get('data') and (time() - cached.get('ts', 0) < 600) and use_cache:
                    cached_owners = cached.get('data')
            except Exception:
                cached_owners = None
            if cached_owners:
                import pandas as pd
                owner_df = pd.DataFrame({'Owner': cached_owners})
            else:
                owner_sql = f"SELECT DISTINCT Owner FROM {self.source_table} WITH (NOLOCK) WHERE {owner_where} AND Owner IS NOT NULL ORDER BY Owner"
                owner_df = self.get_dataframe(owner_sql, owner_params)
            # Strip all quote types from owner values using sanitization
            strip_chars = '"\'"`'
            trans_table = str.maketrans('', '', strip_chars)
            owners = [str(o).translate(trans_table).strip() for o in owner_df['Owner'].dropna().tolist() if str(o).strip()]
            # Update owners cache for base mode
            try:
                if use_cache and owners:
                    from admin import routes as admin_routes
                    from time import time
                    admin_routes._OWNERS_CACHE = {'ts': time(), 'data': owners}
            except Exception:
                pass
        except Exception:
            pass

        return {
            'promotions': rows,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1 if page > 1 else None,
                'next_num': page + 1 if page < total_pages else None
            },
            'owners': owners
        }
    
    def get_all_spe_promos(self) -> List[Dict[str, Any]]:
        """Fetch all SPE promotions from database"""
        return self.get_promos_by_execution_type("SPE")
    
    def get_all_rebates(self) -> List[Dict[str, Any]]:
        """Fetch all rebate promotions from database"""
        return self.get_promos_by_execution_type("Rebate")
    
    def get_all_promotions_unified(self) -> List[Dict[str, Any]]:
        """Fetch ALL promotions regardless of Desired_Execution."""
        sql = f"""
            SELECT 
                code,
                Owner,
                [bill facing name] as bill_facing_name,
                orbit_id,
                description,
                promo_notes,
                discount,
                amount,
                nseip_drop,
                dcd_web_cart,
                product_type,
                bogo,
                fpd_display_promo,
                on_menu,
                market_group,
                store_group,
                promo_srart_date AS promo_start_date,
                promo_end_date,
                comm_end_date,
                promo_duration,
                delay_time,
                application_grace_period,
                device_sales_type,
                activation_type,
                active_line_required,
                maintain_soc,
                crffc_maintainactivelinedev,
                limit_per_ban,
                soc_grouping,
                account_type,
                sales_application,
                operator_id,
                sku_group_id,
                device_status_group_id,
                clawback_indicator,
                Broken_Trade,
                Anticipated_volume_take_rates_total,
                Desired_Execution,
                cat_description
            FROM {self.source_table}
            ORDER BY code DESC
        """
        try:
            df = self.get_dataframe(sql)
            return [self._sanitize_record(r) for r in df.to_dict('records')]
        except Exception as e:
            logger.error(f"Failed to fetch all promotions: {str(e)}")
            return []
    
    def get_promo_by_code(self, promo_code: str) -> Optional[Dict[str, Any]]:
        """Fetch specific promotion by code."""
        # Pull ALL columns so downstream generator can map any newly added field without code change.
        # Rationale: we have a broad SQL generation mapping that may evolve; selecting * avoids drifting lists.
        sql = f"SELECT * FROM {self.source_table} WITH (NOLOCK) WHERE code = :promo_code"
        
        try:
            df = self.get_dataframe(sql, {'promo_code': promo_code})
            if not df.empty:
                return self._sanitize_record(df.iloc[0].to_dict())
            return None
        except Exception as e:
            logger.error(f"Failed to fetch promo {promo_code}: {str(e)}")
            return None

    def get_promo_core_by_code(self, promo_code: str) -> Optional[Dict[str, Any]]:
        """Fetch minimal fields for fast first-paint on edit pages."""
        sql = f"""
            SELECT 
                code,
                Owner,
                [bill facing name] AS bill_facing_name,
                Desired_Execution,
                orbit_id,
                Status,
                promo_start_date,
                promo_end_date,
                description
            FROM {self.source_table} WITH (NOLOCK)
            WHERE code = :promo_code
        """
        try:
            df = self.get_dataframe(sql, {'promo_code': promo_code})
            if not df.empty:
                return self._sanitize_record(df.iloc[0].to_dict())
            return None
        except Exception as e:
            logger.error(f"Failed to fetch core promo {promo_code}: {str(e)}")
            return None

    def get_recent_promos(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch promotions created/updated in the last N days"""
        # Some rows have non-date / malformed values in promo_start_date (stored as text).
        # Direct comparison causes implicit conversion and raises: Conversion failed when converting date and/or time from character string.
        # Use TRY_CONVERT to safely skip bad rows.
        sql = f"""
            SELECT 
            code,
            Owner,
            description,
            promo_start_date,
            promo_end_date,
            amount,
            operator_id,
            orbit_id
            FROM {self.source_table}
        WHERE TRY_CONVERT(date, promo_start_date) IS NOT NULL
    AND cast(promo_start_date as date)  >= DATEADD(day, -:days, GETDATE())
        ORDER BY TRY_CONVERT(date, promo_start_date) DESC
        """
        
        try:
            df = self.get_dataframe(sql, {'days': days})
            records = df.to_dict('records')
            # Diagnostic: count invalid date rows skipped
            try:
                # Pull a lightweight set of raw date values to count invalids
                raw_sql = f"SELECT promo_start_date FROM {self.source_table} WITH (NOLOCK) WHERE promo_start_date IS NOT NULL"
                raw_df = self.get_dataframe(raw_sql)
                total_with_value = len(raw_df)
                valid_mask = raw_df['promo_start_date'].apply(lambda v: self._is_valid_date_string(v))
                valid_count = int(valid_mask.sum())
                invalid_count = total_with_value - valid_count
                ratio = (invalid_count / total_with_value) if total_with_value else 0.0
                if total_with_value and ratio > self.invalid_ratio_threshold:
                    logger.warning(f"High invalid promo_start_date ratio: {invalid_count}/{total_with_value} (>{self.invalid_ratio_threshold*100:.0f}%)")
                # Persist snapshot
                try:
                    engine = self.get_engine()
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO PAM.date_diagnostics_history (captured_at, window_days, total_with_value, valid_dates, invalid_dates, invalid_ratio) VALUES (:captured_at, :window_days, :total_with_value, :valid_dates, :invalid_dates, :invalid_ratio)"), {
                            'captured_at': datetime.now(timezone.utc).isoformat(),
                            'window_days': days,
                            'total_with_value': total_with_value,
                            'valid_dates': valid_count,
                            'invalid_dates': invalid_count,
                            'invalid_ratio': ratio
                        })
                except Exception as pe:
                    logger.warning(f"Failed to persist diagnostics snapshot to SQL Server: {pe}")
                # Attach diagnostics to first record if any; or create synthetic diagnostic record
                if records:
                    records[0]['_date_diagnostics'] = {
                        'total_with_value': total_with_value,
                        'valid_dates': valid_count,
                        'invalid_dates': invalid_count,
                        'days_window': days
                    }
                else:
                    records.append({
                        '_date_diagnostics': {
                            'total_with_value': total_with_value,
                            'valid_dates': valid_count,
                            'invalid_dates': invalid_count,
                            'days_window': days
                        }
                    })
            except Exception as diag_err:
                logger.warning(f"Date diagnostics failed: {diag_err}")
            return [self._sanitize_record(r) for r in records]
        except Exception as e:
            logger.error(f"Failed to fetch recent promos: {str(e)}")
            return []

    def _is_valid_date_string(self, value: Any) -> bool:
        """Heuristic to decide if a string can be parsed as date (M/D/YYYY or ISO)."""
        if value is None:
            return False
        s = str(value).strip()
        if not s:
            return False
        from datetime import datetime
        # Try M/D/YYYY
        for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%y'):
            try:
                datetime.strptime(s, fmt)
                return True
            except Exception:
                continue
        return False

    def get_latest_date_diagnostics(self) -> Optional[Dict[str, Any]]:
        """Return the most recent date diagnostics snapshot if available in SQL Server.

        This is a best-effort method: it will attempt to read from [PAM].[date_diagnostics_history]
        if present; otherwise returns None.
        """
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                res = conn.execute(text("SELECT TOP 1 captured_at, window_days, total_with_value, valid_dates, invalid_dates, invalid_ratio FROM PAM.date_diagnostics_history ORDER BY id DESC")).fetchone()
                if not res:
                    return None
                return {
                    'captured_at': str(res[0]),
                    'window_days': int(res[1]) if res[1] is not None else None,
                    'total_with_value': int(res[2]) if res[2] is not None else None,
                    'valid_dates': int(res[3]) if res[3] is not None else None,
                    'invalid_dates': int(res[4]) if res[4] is not None else None,
                    'invalid_ratio': float(res[5]) if res[5] is not None else None
                }
        except Exception:
            return None
    
    def get_active_promos(self) -> List[Dict[str, Any]]:
        """Fetch currently active promotions (today between start and end dates)."""
        sql = f"""
            SELECT 
                code,
                Owner,
                description,
                promo_srart_date AS promo_start_date,
                promo_end_date,
                amount,
                operator_id,
                orbit_id
            FROM {self.source_table} WITH (NOLOCK)
            WHERE TRY_CONVERT(date, promo_start_date) IS NOT NULL
              AND TRY_CONVERT(date, promo_end_date) IS NOT NULL
              AND CONVERT(date, GETDATE()) BETWEEN TRY_CONVERT(date, promo_start_date) AND TRY_CONVERT(date, promo_end_date)
            ORDER BY TRY_CONVERT(date, promo_start_date) DESC
        """
        try:
            df = self.get_dataframe(sql)
            return [self._sanitize_record(r) for r in df.to_dict('records')]
        except Exception as e:
            logger.error(f"Failed to fetch active promos: {e}")
            return []

    # ---------------- Sanitization -----------------
    @staticmethod
    def _sanitize_record(rec: Dict[Any, Any]) -> Dict[str, Any]:
        if not rec:
            return rec
        strip_chars = '"\'"`'
        trans = str.maketrans('', '', strip_chars)
        cleaned = {}
        for k, v in rec.items():
            # Normalize Owner to lowercase owner for template consistency
            key = 'owner' if k == 'Owner' else k
            if isinstance(v, str):
                # Strip quotes and then strip whitespace
                sanitized = v.translate(trans).strip()
                cleaned[key] = sanitized
            else:
                cleaned[key] = v
        return cleaned
    
    def search_promos(self, search_term: str) -> List[Dict[str, Any]]:
        """Search promotions by code, description, or bill facing name (case-insensitive)."""
        sql = f"""
            SELECT 
                code,
                Owner,
                [bill facing name] AS bill_facing_name,
                orbit_id,
                description,
                promo_notes,
                discount,
                amount,
                nseip_drop,
                dcd_web_cart,
                product_type,
                bogo,
                fpd_display_promo,
                on_menu,
                market_group,
                store_group,
                promo_start_date,
                promo_end_date,
                comm_end_date,
                promo_duration,
                delay_time,
                application_grace_period,
                device_sales_type,
                activation_type,
                active_line_required,
                maintain_soc,
                crffc_maintainactivelinedev,
                limit_per_ban,
                soc_grouping,
                account_type,
                sales_application,
                operator_id,
                sku_group_id,
                device_status_group_id,
                clawback_indicator,
                Broken_Trade,
                Anticipated_volume_take_rates_total,
                Desired_Execution,
                Status,
                crffc_eligibletradeindevices,
                cat_lobchannelhorizontalname,
                cat_additionaleligibilityrequirementsname,
                cat_eligibledevices,
                cat_channelsname,
                cat_description
            FROM {self.source_table} WITH (NOLOCK)
            WHERE (
                code LIKE :search_term
                OR description LIKE :search_term
                OR [bill facing name] LIKE :search_term
            )
              AND TRY_CONVERT(date, promo_start_date) IS NOT NULL
            ORDER BY TRY_CONVERT(date, promo_start_date) DESC
        """
        try:
            pattern = f"%{search_term}%"
            df = self.get_dataframe(sql, {'search_term': pattern})
            return [self._sanitize_record(r) for r in df.to_dict('records')]
        except Exception as e:
            logger.error(f"Failed to search promos: {e}")
            return []

    # ==================== ORBIT DATA METHODS (Delegate to OrbitDatabaseManager) ====================
    # These methods provide a unified interface for legacy code.
    # They delegate to OrbitDatabaseManager which ALWAYS uses Microsoft Fabric.
    # 
    # NOTE: New code should use OrbitDatabaseManager directly for orbit data reads.
    #       DatabaseManager should only be used for PAM database writes/reads.
    # 
    # IMPORTANT: If Fabric is down, these methods will FAIL - no fallback to fake data!
    # ================================================================================================
    
    def get_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Return minimal orbit record (bill facing name, dates).
        
        DELEGATES to OrbitDatabaseManager which uses Microsoft Fabric ONLY.
        If Fabric is unavailable, this will fail (no fallback).
        """
        from .orbit_database import OrbitDatabaseManager
        orbit_mgr = OrbitDatabaseManager()
        result = orbit_mgr.get_orbit_record(orbit_id)
        
        # Handle error responses from orbit manager
        if result and result.get('_error'):
            return None
        
        return result

    def get_orbit_dates_map(self, orbit_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return mapping of orbit_id -> { 'orbit_start_date': ..., 'orbit_end_date': ... }

        DELEGATES to OrbitDatabaseManager which uses Microsoft Fabric ONLY.
        """
        from .orbit_database import OrbitDatabaseManager
        orbit_mgr = OrbitDatabaseManager()
        if not orbit_ids:
            return {}

        try:
            return orbit_mgr.get_orbit_dates_map(orbit_ids)
        except Exception as e:
            logger.warning(f"Bulk orbit date fetch failed, falling back to per-record lookup: {e}")

        out: Dict[str, Dict[str, Any]] = {}
        for oid in orbit_ids:
            if not oid:
                continue
            try:
                result = orbit_mgr.get_orbit_record(oid)
                if result and not result.get('_error'):
                    out[oid] = {
                        'orbit_start_date': result.get('promo_start_date', ''),
                        'orbit_end_date': result.get('promo_end_date', '')
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch orbit dates for {oid}: {e}")
                continue

        return out

    def get_full_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Return full orbit record (all relevant columns).
        
        DELEGATES to OrbitDatabaseManager which uses Microsoft Fabric ONLY.
        """
        from .orbit_database import OrbitDatabaseManager
        orbit_mgr = OrbitDatabaseManager()
        result = orbit_mgr.get_orbit_record(orbit_id)
        
        # Handle error responses from orbit manager
        if result and result.get('_error'):
            return None
        
        return result
    
    def _extract_mpss_lookback(self, description: str) -> str:
        """
        Extract MPSS Lookback value from description text.
        Format expected: "MPSS: X Days" or "MPSS: X"
        Returns the number as a string, or empty string if not found.
        """
        if not description:
            return ""
        
        import re
        
        # Pattern to find "MPSS: X" or "MPSS: X Days"
        pattern = r"MPSS:\s*(\d+)"
        match = re.search(pattern, description)
        
        if match:
            return match.group(1)
        return ""
    
    def _strip_quotes(self, text: str) -> str:
        """
        Strip surrounding quotes from a text string if they exist and clean special characters.
        Handles both single and double quotes, and cleans invisible unicode characters.
        Also removes question marks from device listings.
        """
        if not text or not isinstance(text, str):
            return ""
            
        # Strip double quotes
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
            
        # Strip single quotes
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]
            
        # Clean invisible or special characters that might render as '?'
        import re
        
        # This regex matches various zero-width characters, non-breaking spaces, etc.
        invisible_chars_pattern = r'[\u200B-\u200F\uFEFF\u00A0]'
        text = re.sub(invisible_chars_pattern, '', text)
        
        # Special handling for device lists - check if this looks like a device listing
        if ('Samsung Galaxy:' in text or 'Apple:' in text or 'OnePlus:' in text or 'Google Pixel:' in text):
            # Remove question marks that are used for uncertainty in device listings
            text = text.replace('?', '')
            # Clean up multiple spaces that might result from removed characters
            text = re.sub(r'\s+', ' ', text)
            # Clean up spaces before commas
            text = re.sub(r'\s+,', ',', text)
        
        return text
    
    def convert_db_record_to_json_format(self, db_record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database record to JSON storage format"""

        key_lookup = {str(k).lower(): k for k in (db_record or {}).keys()}

        def _get(*keys, default=""):
            for key in keys:
                if key in db_record:
                    return db_record.get(key)
                lk = str(key).lower()
                if lk in key_lookup:
                    return db_record.get(key_lookup[lk])
            return default

        def _yn_or_passthrough(value):
            if value is None:
                return ""
            if isinstance(value, str):
                up = value.strip().upper()
                if up in {"Y", "YES", "TRUE", "1"}:
                    return "Y"
                if up in {"N", "NO", "FALSE", "0"}:
                    return "N"
                return value
            if isinstance(value, bool):
                return "Y" if value else "N"
            return value
        
        def format_date_for_html(date_value):
            """Convert M/D/YYYY to YYYY-MM-DD for HTML date inputs"""
            if not date_value:
                return ""
            date_str = str(date_value).strip()
            if not date_str:
                return ""
            
            # Handle M/D/YYYY format from SQL Server
            try:
                from datetime import datetime
                if '/' in date_str:
                    # Parse M/D/YYYY format
                    dt = datetime.strptime(date_str, '%m/%d/%Y')
                    return dt.strftime('%Y-%m-%d')
                return date_str
            except:
                return date_str
        
        # Map database columns to JSON format
        # Sanitize owner field to strip all quote types
        owner_raw = _get("Owner", "owner", default="")
        strip_chars = '"\'"`'
        trans_table = str.maketrans('', '', strip_chars)
        owner_clean = str(owner_raw).translate(trans_table).strip() if owner_raw else ""
        
        json_record = {
            "code": _get("code", "Code", "CODE", default=""),
            "description": _get("description", "Description", default=""),
            "bill_facing_name": _get("bill_facing_name", "bill facing name", "Bill_Facing_Name", default=""),
            "owner": owner_clean,
            "orbit_id": _get("orbit_id", default=""),
            "promo_notes": _get("promo_notes", default=""),
            "promo_start_date": format_date_for_html(_get("promo_start_date", "promo_srart_date")),
            "promo_end_date": format_date_for_html(_get("promo_end_date")),
            "amount": str(_get("amount", default="")),
            "discount": str(_get("discount", default="")),
            "operator_id": str(_get("operator_id", default="")),
            "bptcr": str(_get("bptcr", "orbit_id", default="")),
            "sku_group_id": _get("sku_group_id", default=""),
            "soc_grouping": _get("soc_grouping", default=""),
            "trade_in_group_id": _get("trade_in_group_id", "trade_in_grp_id", default=""),
            "product_type": _get("product_type", default=""),
            "bogo": _yn_or_passthrough(_get("bogo", default="")),
            "on_menu": _yn_or_passthrough(_get("on_menu", default="")),
            "active_line_required": _yn_or_passthrough(_get("active_line_required", default="")),
            "maintain_soc": _yn_or_passthrough(_get("maintain_soc", default="")),
            "maintain_active_line": _yn_or_passthrough(_get("maintain_active_line", "crffc_maintainactivelinedev", default="")),
            "market_group": _get("market_group", default="*"),
            "store_group": _get("store_group", default="*"),
            "limit_per_ban": str(_get("limit_per_ban", default="")),
            "min_gsm_count": str(_get("min_gsm_count", default="")),
            "max_gsm_count": str(_get("max_gsm_count", default="")),
            "port_in_group_id": _get("port_in_group_id", default=""),
            "fpd_display_promo": _yn_or_passthrough(_get("fpd_display_promo", default="")),
            "nseip_drop": _yn_or_passthrough(_get("nseip_drop", default="")),
            "dcd_web_cart": _yn_or_passthrough(_get("dcd_web_cart", default="")),
            "promo_duration": str(_get("promo_duration", default="")),
            "delay_time": str(_get("delay_time", default="")),
            "application_grace_period": str(_get("application_grace_period", default="")),
            "device_sales_type": _get("device_sales_type", default=""),
            "activation_type": _get("activation_type", default=""),
            "account_type": _get("account_type", default=""),
            "sales_application": _get("sales_application", default=""),
            "device_status_group_id": _get("device_status_group_id", default=""),
            "clawback_indicator": _yn_or_passthrough(_get("clawback_indicator", default="")),
            # Bill Facing Name (physical column may be 'bill facing name')
            "bill_facing_name": _get("bill_facing_name", "bill facing name", "Bill_Facing_Name", default=""),
            
            # Prefer direct DB column value for MPSS lookback; fall back to extraction from cat_description only if column absent/empty
            "mpss_lookback": _get("mpss_lookback", default="") or self._extract_mpss_lookback(str(_get("cat_description", default="") or "")),
            
            # Add metadata
            "data_source": "database",
            "last_sync": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            
            # Execution type for tab separation
            "Desired_Execution": _get("Desired_Execution", default="RDC"),
            
            # Default values for fields not in database (PAM-only workflow fields)
            "pj_code": "",
            "sku_link": _get("sku_link", default=""),
            "tradein_link": _get("tradein_link", default=""),
            "comm_end_date": format_date_for_html(_get("comm_end_date")),
            "promo_grace": _get("promo_grace", "promo_grace_period", default=""),
            "trade_in_grace": _get("trade_in_grace", "trade_in_grace_period", default=""),
            "segment_name": _get("segment_name", default=""),
            "sub_segment": _get("sub_segment", default=""),
            "segment_group_id": _get("segment_group_id", "segment_grp_id", default=""),
            "segment_level": _get("segment_level", default=""),
            "flow_indicator": "NULL",
            "uploaded_files": {},
            "generated_sql": "",
            "sql_file": {},
            "last_changes": None,
            "jira_ticket": "",
            # Initiative name from its own column; do not fall back to description to avoid overwriting user edits
            "initiative_name": _get("initiative_name", default=""),
            # Additional fields from database sample
            "crffc_maintainactivelinedev": _yn_or_passthrough(_get("crffc_maintainactivelinedev", default="")),
            "Broken_Trade": _get("Broken_Trade", default=""),
            "Anticipated_volume_take_rates_total": _get("Anticipated_volume_take_rates_total", default=""),
            
            # NEW FIELDS - Added from database analysis
            "Status": _get("Status", default=""),
            # Strip quotes from device fields if they exist
            "crffc_eligibletradeindevices": self._strip_quotes(str(_get("crffc_eligibletradeindevices", default="") or "")),
            "cat_lobchannelhorizontalname": _get("cat_lobchannelhorizontalname", default=""),
            "cat_additionaleligibilityrequirementsname": _get("cat_additionaleligibilityrequirementsname", default=""),
            "cat_eligibledevices": self._strip_quotes(str(_get("cat_eligibledevices", default="") or "")),
            "cat_channelsname": _get("cat_channelsname", default=""),
            "cat_description": _get("cat_description", default="")
        }

        json_record['Owner'] = owner_clean

        # Pass-through: include any generator-relevant fields that are present in the DB record but not yet mapped above.
        generator_field_candidates = {
            'promo_start_date','promo_end_date','finance_type','application_grace_period',
            'promo_grace','trade_in_grace','trade_in_group_id','trade_in_grp_id','promo_grace_period','trade_in_grace_period',
            'tiered_group_id','tiered_grp_id','segment_group_id','segment_grp_id','segment_name','sub_segment','segment_level',
            'flow_indicator','flow_ind','bolt_trade_in_grp_id','port_in_group_id','min_gsm_count','max_gsm_count',
            'maintain_soc','maintain_active_line','activation_type','device_sales_type','sku_group_id','account_type','sales_application',
            'soc_grouping','limit_per_ban','delay_time','nseip_drop','discount','amount','operator_id','device_status_group_id',
            'clawback_indicator','bptcr','mpss_lookback','promo_tier_1_amount','promo_tier_1_sku_group_id','promo_tier_1_devices',
            'promo_tier_2_amount','promo_tier_2_sku_group_id','promo_tier_2_devices','promo_tier_3_amount','promo_tier_3_sku_group_id',
            'promo_tier_3_devices','mk_mdl_grp_tier_1','mk_mdl_grp_tier_1_amount','mk_mdl_grp_tier_1_condition_id','mk_mdl_grp_tier_1_min_fmv',
            'mk_mdl_grp_tier_1_max_fmv','mk_mdl_grp_tier_2','mk_mdl_grp_tier_2_amount','mk_mdl_grp_tier_2_condition_id','mk_mdl_grp_tier_2_min_fmv',
            'mk_mdl_grp_tier_2_max_fmv','mk_mdl_grp_tier_3','mk_mdl_grp_tier_3_amount','mk_mdl_grp_tier_3_condition_id','mk_mdl_grp_tier_3_min_fmv',
            'mk_mdl_grp_tier_3_max_fmv','mk_mdl_grp_tier_4','mk_mdl_grp_tier_4_amount','mk_mdl_grp_tier_4_condition_id','mk_mdl_grp_tier_4_min_fmv',
            'mk_mdl_grp_tier_4_max_fmv','tradein_link','sku_link','initiative_name','dcd_jira','orbit_link','legal_link','c2_link'
        }
        for k,v in db_record.items():
            lk = str(k)
            if lk in generator_field_candidates and lk not in json_record:
                json_record[lk] = v
            if lk.lower() in {'bill facing name'}:
                continue
            if lk not in json_record:
                json_record[lk] = v
        # Normalize common synonyms / variant column names into expected keys used by generator
        if 'promo_start_date' in json_record and not json_record.get('promo_start_date'):
            json_record['promo_start_date'] = json_record['promo_start_date']
        if 'trade_in_grp_id' in json_record and not json_record.get('trade_in_group_id'):
            json_record['trade_in_group_id'] = json_record['trade_in_grp_id']
        if 'tiered_grp_id' in json_record and not json_record.get('tiered_group_id'):
            json_record['tiered_group_id'] = json_record['tiered_grp_id']
        if 'segment_grp_id' in json_record and not json_record.get('segment_group_id'):
            json_record['segment_group_id'] = json_record['segment_grp_id']
        if 'promo_grace_period' in json_record and not json_record.get('promo_grace'):
            json_record['promo_grace'] = json_record['promo_grace_period']
        if 'trade_in_grace_period' in json_record and not json_record.get('trade_in_grace'):
            json_record['trade_in_grace'] = json_record['trade_in_grace_period']
        
        return json_record

    # (Duplicate write helper methods removed)

    # --- Write helpers for PAM table & SQLite overlays ---
    def update_promo_fields(self, code: str, field_map: Dict[str, Any]) -> bool:
        """Update mutable fields via canonical->physical mapping (FIELD_DB_MAP).

        field_map: canonical field name -> value (already synonym-normalized upstream).
        Returns True on success (even if some fields skipped). Logs diagnostics.
        """
        if not field_map:
            return True
        # Load existing columns (cached) to validate physical names
        existing_cols = self.get_existing_columns()
        assignments: List[str] = []
        params: Dict[str, Any] = {'code': code}
        skipped: Dict[str, Any] = {}
        remapped: Dict[str, str] = {}
        for idx, (canonical, value) in enumerate(field_map.items()):
            physical = canonical_to_physical(canonical)
            # Strip quotes from Owner field before writing to database
            if canonical == 'owner' or physical == 'Owner':
                if isinstance(value, str):
                    strip_chars = '"\'"`'
                    trans = str.maketrans('', '', strip_chars)
                    value = value.translate(trans).strip()
            # 'bill facing name' came from mapping; ensure not overwritten by canonical key itself
            if existing_cols and physical not in existing_cols:
                # Allow fallback: if canonical itself (without mapping) exists physically
                if canonical in existing_cols:
                    physical = canonical
                    remapped[canonical] = physical
                else:
                    skipped[canonical] = value
                    continue
            col_sql = quote_identifier(physical)
            param_name = f"p{idx}"
            assignments.append(f"{col_sql} = :{param_name}")
            params[param_name] = value
        if not assignments:
            logger.warning(f"No valid columns to update for {code}; skipped={list(skipped.keys())}")
            return True
        sql = f"UPDATE {self.source_table} SET {', '.join(assignments)} WHERE code = :code"
        try:
            engine = self.get_engine()
            with engine.begin() as conn:
                conn.execute(text(sql), params)
            if remapped:
                logger.info(f"Remapped canonical columns for {code}: {remapped}")
            if skipped:
                logger.warning(f"Skipped unknown/unavailable columns for {code}: {list(skipped.keys())}")
            logger.debug(f"Updated {code} columns: {assignments}")
            return True
        except Exception as e:
            logger.error(f"Failed to update promo {code}: {e}")
            return False

    def get_existing_columns(self) -> set:
        """Return a set of physical column names for the source table (cached per instance)."""
        if hasattr(self, '_cached_existing_columns') and isinstance(getattr(self, '_cached_existing_columns'), set):
            return getattr(self, '_cached_existing_columns')
        try:
            parts = self.source_table.strip('[]').split('.')
            if len(parts) == 2:
                schema, table = [p.strip('[]') for p in parts]
            else:
                schema, table = 'dbo', parts[-1].strip('[]')
            df = self.get_dataframe(
                """
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table
                """,
                {'schema': schema, 'table': table}
            )
            cols = {r['COLUMN_NAME'] for _, r in df.iterrows()} if not df.empty else set()
            setattr(self, '_cached_existing_columns', cols)
            return cols
        except Exception:
            return set()

    # --- Minimal creation helper (test/admin use) ---
    def insert_minimal_promo(self, field_map: Dict[str, Any], user: str = 'System') -> bool:
        """Insert a minimal promo row if code not present.

        field_map MUST include 'code'. Only a safe subset of columns will be inserted.
        Returns True if inserted, False if already exists or failure.
        """
        code = field_map.get('code')
        if not code:
            return False
        # Quick existence check
        try:
            if self.get_promo_by_code(code):
                return False
        except Exception:
            pass
        safe_cols = ['code','description','Owner','promo_start_date','promo_end_date','Desired_Execution']
        insert_cols = []
        params = {}
        for c in safe_cols:
            if c in field_map and field_map[c] is not None:
                insert_cols.append(c)
                params[c] = field_map[c]
        if 'code' not in insert_cols:
            return False
        col_list = ', '.join(insert_cols)
        val_list = ', '.join([f":{c}" for c in insert_cols])
        sql = f"INSERT INTO {self.source_table} ({col_list}) VALUES ({val_list})"
        try:
            engine = self.get_engine()
            with engine.begin() as conn:
                conn.execute(text(sql), params)
            # Version history removed: no creation event recorded
            return True
        except Exception as e:
            logger.error(f"Failed minimal insert for {code}: {e}")
            return False

    # --- SKU Group ID helpers ---
    def get_all_sku_group_ids(self) -> list[str]:
        """Return list of distinct sku_group_id values present in the source table (uppercase, pattern-like)."""
        sql = f"SELECT DISTINCT sku_group_id FROM {self.source_table} WITH (NOLOCK) WHERE sku_group_id IS NOT NULL AND LEN(sku_group_id)=3"
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                rows = conn.execute(text(sql)).fetchall()
            vals: list[str] = []
            for r in rows:
                val = (r[0] or '').strip().upper()
                if val:
                    vals.append(val)
            return vals
        except Exception as e:
            logger.error(f"Failed to fetch sku_group_ids: {e}")
            return []

    # Version-history and promo_history persistence removed per project reset.
    # All functions that previously wrote to or read from `PAM.promo_history` have been deleted.
    # If you need to reintroduce history, implement a new module under `data/` and wire callers explicitly.

    def insert_promo_record(self, field_map: Dict[str, Any]) -> bool:
        """Insert a brand new promotion row into the PAM source table.

        field_map: column->value. Columns must exist in the target table. Dynamic SQL is built safely using
        named parameters. Returns True on success.
        """
        if not field_map:
            return False
        # Ensure required keys
        if 'code' not in field_map:
            raise ValueError('insert_promo_record requires a code key')
        cols = []
        params = {}
        values_clause = []
        # Physical column name normalization mapping
        col_alias_map = {
            'bill_facing_name': '[bill facing name]'
        }
        for i, (col, val) in enumerate(field_map.items()):
            col = col_alias_map.get(col, col)
            param = f"p{i}"
            cols.append(col)
            params[param] = val
            values_clause.append(f":{param}")
        col_sql = ",".join(cols)
        val_sql = ",".join(values_clause)
        sql = f"INSERT INTO {self.source_table} ({col_sql}) VALUES ({val_sql})"
        try:
            engine = self.get_engine()
            with engine.begin() as conn:
                conn.execute(text(sql), params)
            return True
        except Exception as e:
            logger.error(f"Failed to insert promo record {field_map.get('code')}: {e}")
            logger.debug(f"Insert SQL: {sql}")
            logger.debug(f"Params: {params}")
            return False
