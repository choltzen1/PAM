import pandas as pd
from sqlalchemy import create_engine, text
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import os
import sqlite3
import json
import os
import sqlite3
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
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
        self.source_table = os.getenv('PAM_SOURCE_TABLE', '[PAM].[PAM_Orbit_Data_Updated]')
        # Raw intake Orbit table (no promo code yet). Always query this FIRST for orbit lookups.
        self.orbit_source_table = os.getenv('PAM_ORBIT_SOURCE_TABLE', '[RDC].[PAM_Orbit_Data]')
        # Load connection parameters from environment for security
        self.server = os.getenv('PAM_DB_SERVER', 'localhost')
        self.database = os.getenv('PAM_DB_DATABASE', 'PromoQuality')
        self.username = os.getenv('PAM_DB_USERNAME', '')
        self.password = os.getenv('PAM_DB_PASSWORD', '')
        self.driver = os.getenv('PAM_DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        self.encrypt = os.getenv('PAM_DB_ENCRYPT', 'no').lower()  # yes/no
        self.trust_cert = os.getenv('PAM_DB_TRUST_CERT', 'yes').lower()  # yes/no
        self.timeout = int(os.getenv('PAM_DB_LOGIN_TIMEOUT', '15'))
        self.source_table = os.getenv('PAM_SOURCE_TABLE', '[PAM].[PAM_Orbit_Data_Updated]')
        # Raw intake Orbit table (no promo code yet). Always query this FIRST for orbit lookups.
        self.orbit_source_table = os.getenv('PAM_ORBIT_SOURCE_TABLE', '[RDC].[PAM_Orbit_Data]')
        self._engine = None
        # (Duplicate _ensure_diag_tables block removed)
        # Diagnostics persistence (SQLite co-located with version history)
        self._diag_db_path = os.path.join('data', 'version_history.db')
        self._ensure_diag_tables()
        # Threshold from environment
        self.invalid_ratio_threshold = float(os.environ.get('INVALID_DATE_RATIO_WARN_THRESHOLD', '0.10'))

    def _ensure_diag_tables(self):
        try:
            os.makedirs('data', exist_ok=True)
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS date_diagnostics_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        captured_at TEXT NOT NULL,
                        window_days INTEGER NOT NULL,
                        total_with_value INTEGER,
                        valid_dates INTEGER,
                        invalid_dates INTEGER,
                        invalid_ratio REAL
                    )
                """)
                # Version history augment (diff_json,user_name) + promo_extras + promo_files
                # (Version history table intentionally removed - reset state)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS promo_extras (
                        promo_code TEXT PRIMARY KEY,
                        jira_ticket TEXT,
                        initiative_name TEXT,
                        sku_link TEXT,
                        tradein_link TEXT,
                        promo_grace TEXT,
                        trade_in_grace TEXT,
                        segment_name TEXT,
                        sub_segment TEXT,
                        segment_group_id TEXT,
                        segment_level TEXT,
                        flow_indicator TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        updated_by TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS promo_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        promo_code TEXT NOT NULL,
                        original_filename TEXT NOT NULL,
                        stored_filename TEXT NOT NULL,
                        file_type TEXT,
                        size_bytes INTEGER,
                        checksum TEXT,
                        uploaded_by TEXT NOT NULL,
                        uploaded_at TEXT NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_promo_files_code ON promo_files(promo_code)")
                # Lightweight schema migration: ensure user_name column exists (older DBs lacked it)
                try:
                    cur = conn.execute("PRAGMA table_info(version_history)")
                    cols = [r[1] for r in cur.fetchall()]
                    # version_history migration skipped (table deprecated/reset)
                    # New minimal history table (start-over implementation)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS promo_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            promo_code TEXT NOT NULL,
                            timestamp TEXT NOT NULL,
                            event_type TEXT NOT NULL,
                            user_name TEXT,
                            diff_json TEXT
                        )
                    """)
                    try:
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_promo_history_code_ts ON promo_history(promo_code, timestamp)")
                    except Exception:
                        pass
                except Exception as mig_e:
                    logger.warning(f"Version history migration check failed: {mig_e}")
        except Exception as e:
            logger.warning(f"Failed to ensure diagnostics tables: {e}")
        # Post-creation column augmentation for promo_extras (add test_status, zlab_status if missing)
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                cur = conn.execute("PRAGMA table_info(promo_extras)")
                existing_cols = {r[1] for r in cur.fetchall()}
                for col in ('test_status','zlab_status'):
                    if col not in existing_cols:
                        try:
                            conn.execute(f"ALTER TABLE promo_extras ADD COLUMN {col} TEXT")
                        except Exception as ce:
                            logger.warning(f"Failed adding column {col} to promo_extras: {ce}")
        except Exception as e:
            logger.warning(f"Promo extras column migration failed: {e}")
    
    def get_engine(self):
        """Create and return SQLAlchemy engine"""
        if self._engine is None:
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
                logger.info(f"Attempting DB connect with: {masked}")
                params = urllib.parse.quote_plus(odbc_str)
                self._engine = create_engine(f'mssql+pyodbc:///?odbc_connect={params}', pool_pre_ping=True, pool_recycle=1800)
                # Test connection (duplicate code removed)
                with self._engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("Database connection established ✅")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                logger.error("Troubleshooting tips: 1) Verify server/port reachable (ping / Test-NetConnection) 2) Confirm ODBC driver installed 3) Check firewall/VPN 4) Validate credentials.")
                raise
        
        return self._engine
    
    def get_dataframe(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """Execute SQL query and return DataFrame"""
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except Exception as e:
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

    # (Duplicate get_highest_sequential_promo_code removed)

    def get_highest_sequential_promo_code(self) -> Optional[str]:
        """Return the highest promo code matching pattern ^[A-Z][0-9]{1,4}$ (one letter + digits).

        We rely on DB ordering but also perform regex parsing to ensure correctness.
        Returns None if no matching codes found or on error.
        """
        try:
            # Efficient: pull only code column; ordering DESC to hit highest early
            sql = f"SELECT TOP 200 code FROM {self.source_table} WHERE code IS NOT NULL ORDER BY code DESC"
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
            FROM {self.source_table}
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
            s = search.strip().lower()
            if s and s.isalnum() and len(s) <= 8:  # treat as possible code prefix
                where_clauses.append("(LOWER(code) LIKE :code_prefix OR LOWER(Owner) LIKE :wild OR LOWER([bill facing name]) LIKE :wild)")
                params['code_prefix'] = s + '%'
            else:
                where_clauses.append("(LOWER(code) LIKE :wild OR LOWER(Owner) LIKE :wild OR LOWER([bill facing name]) LIKE :wild)")
            params['wild'] = f"%{s}%"

        where_sql = " AND ".join(where_clauses)

        # Count query
        count_sql = f"SELECT COUNT(1) as cnt FROM {self.source_table} WHERE {where_sql}"
        # Data query (order: earliest upcoming first when filtering upcoming, else code desc)
        if force_upcoming or (base_query_mode and upcoming_only_when_no_query):
            order_clause = "ORDER BY promo_start_date ASC, code DESC"
        else:
            order_clause = "ORDER BY code DESC"
        data_sql = f"""
            SELECT code, Owner, [bill facing name] as bill_facing_name, orbit_id,
                   promo_start_date, promo_end_date
            FROM {self.source_table}
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
            owner_sql = f"SELECT DISTINCT Owner FROM {self.source_table} WHERE {owner_where} AND Owner IS NOT NULL ORDER BY Owner"
            owner_df = self.get_dataframe(owner_sql, owner_params)
            owners = [o for o in owner_df['Owner'].dropna().tolist() if str(o).strip()]
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
                Desired_Execution
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
        sql = f"SELECT * FROM {self.source_table} WHERE code = :promo_code"
        
        try:
            df = self.get_dataframe(sql, {'promo_code': promo_code})
            if not df.empty:
                return self._sanitize_record(df.iloc[0].to_dict())
            return None
        except Exception as e:
            logger.error(f"Failed to fetch promo {promo_code}: {str(e)}")
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
                raw_sql = f"SELECT promo_start_date FROM {self.source_table} WHERE promo_start_date IS NOT NULL"
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
                    with sqlite3.connect(self._diag_db_path) as c2:
                        c2.execute(
                            "INSERT INTO date_diagnostics_history (captured_at, window_days, total_with_value, valid_dates, invalid_dates, invalid_ratio) VALUES (?,?,?,?,?,?)",
                            (
                                datetime.utcnow().isoformat(),
                                days,
                                total_with_value,
                                valid_count,
                                invalid_count,
                                ratio
                            )
                        )
                except Exception as pe:
                    logger.warning(f"Failed to persist diagnostics snapshot: {pe}")
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
    
    def get_active_promos(self) -> List[Dict[str, Any]]:
        """Fetch currently active promotions (today between start and end dates)."""
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
        strip_chars = '"\'“”‘’`'
        trans = str.maketrans('', '', strip_chars)
        cleaned = {}
        for k, v in rec.items():
            if isinstance(v, str):
                cleaned[k] = v.translate(trans)
            else:
                cleaned[k] = v
        return cleaned

        # ---------------- Sanitization -----------------
        @staticmethod
        def _sanitize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
            if not rec:
                return rec
            cleaned = {}
            # Characters to strip entirely from text fields (quotes/backticks/curly quotes)
            strip_chars = '"\'“”‘’`'
            trans_table = str.maketrans('', '', strip_chars)
            for k, v in rec.items():
                if isinstance(v, str):
                    # Normalize whitespace and remove undesirable quote characters
                    nv = v.translate(trans_table)
                    cleaned[k] = nv
                else:
                    cleaned[k] = v
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
            FROM {self.source_table}
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

    def get_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Return minimal orbit record (bill facing name, dates) preferring orbit source table."""
        query_tpl = """
            SELECT orbit_id, [bill facing name] AS bill_facing_name, description, Owner, promo_start_date, promo_end_date
            FROM {table}
            WHERE orbit_id = :orbit_id
        """
        def _fetch(table: str):
            try:
                sql_local = query_tpl.format(table=table)
                df_l = self.get_dataframe(sql_local, {'orbit_id': orbit_id})
                if df_l.empty:
                    return None
                rec = df_l.iloc[0].to_dict()
                rec.setdefault('bill_facing_name', rec.get('description',''))
                rec['_table'] = table
                return rec
            except Exception as ex:
                logger.warning(f"Orbit lookup failed on {table}: {ex}")
                return None
        rec = _fetch(self.orbit_source_table)
        if rec:
            return rec
        if self.orbit_source_table != self.source_table:
            return _fetch(self.source_table)
        return None

    def get_orbit_dates_map(self, orbit_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return mapping of orbit_id -> { 'orbit_start_date': ..., 'orbit_end_date': ... }

        Performs a single set-based query against the orbit source table. Falls back
        to the primary source table if the orbit table is empty/unavailable.
        """
        out: Dict[str, Dict[str, Any]] = {}
        if not orbit_ids:
            return out
        # Deduplicate & chunk to avoid parameter explosion
        unique_ids = list({oid for oid in orbit_ids if oid})
        CHUNK = 200
        tables_to_try = [self.orbit_source_table]
        if self.orbit_source_table != self.source_table:
            tables_to_try.append(self.source_table)
        for table in tables_to_try:
            remaining = [oid for oid in unique_ids if oid not in out]
            if not remaining:
                break
            for i in range(0, len(remaining), CHUNK):
                chunk = remaining[i:i+CHUNK]
                # Build parameter list safely
                param_names = [f"p{j}" for j in range(len(chunk))]
                in_clause = ",".join(f":{n}" for n in param_names)
                sql = f"""
                    SELECT orbit_id, promo_start_date AS orbit_start_date, promo_end_date AS orbit_end_date
                    FROM {table}
                    WHERE orbit_id IN ({in_clause})
                """
                params = {n: v for n,v in zip(param_names, chunk)}
                try:
                    df = self.get_dataframe(sql, params)
                    if not df.empty:
                        for rec in df.to_dict('records'):
                            oid = str(rec.get('orbit_id') or '')
                            if oid and oid not in out:
                                out[oid] = {
                                    'orbit_start_date': rec.get('orbit_start_date',''),
                                    'orbit_end_date': rec.get('orbit_end_date','')
                                }
                except Exception as e:
                    logger.warning(f"Orbit batch date fetch failed on {table}: {e}")
                    break  # try next table
        return out

    def get_full_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Return full orbit record (all relevant columns) with source fallback."""
        base = """
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
                Desired_Execution
            FROM {table} WHERE orbit_id = :orbit_id
        """
        def _get(table: str):
            try:
                sql_full = base.format(table=table)
                df_f = self.get_dataframe(sql_full, {'orbit_id': orbit_id})
                if df_f.empty:
                    return None
                rec = df_f.iloc[0].to_dict()
                rec.setdefault('bill_facing_name', rec.get('description',''))
                rec['_table'] = table
                return rec
            except Exception as ex:
                logger.warning(f"Full orbit lookup failed on {table}: {ex}")
                return None
        rec = _get(self.orbit_source_table)
        if rec:
            return rec
        if self.orbit_source_table != self.source_table:
            return _get(self.source_table)
        return None
    
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
        json_record = {
            "code": db_record.get("code", ""),
            "description": db_record.get("description", ""),
            "bill_facing_name": db_record.get("bill_facing_name", ""),  # Use actual bill_facing_name field
            "owner": str(db_record.get("Owner", "Unknown")).strip('"'),  # Remove quotes from owner field
            "orbit_id": db_record.get("orbit_id", ""),
            "promo_notes": db_record.get("promo_notes", ""),  # Add promo_notes field
            "promo_start_date": format_date_for_html(db_record.get("promo_start_date")),
            "promo_end_date": format_date_for_html(db_record.get("promo_end_date")),
            "amount": str(db_record.get("amount", "")),
            "discount": str(db_record.get("discount", "")),
            "operator_id": str(db_record.get("operator_id", "")),
            "bptcr": str(db_record.get("orbit_id", "")),
            "sku_group_id": db_record.get("sku_group_id", ""),
            "soc_grouping": db_record.get("soc_grouping", ""),
            "trade_in_group_id": db_record.get("trade_in_group_id", ""),
            "product_type": db_record.get("product_type", ""),
            "bogo": "Y" if db_record.get("bogo") == "Y" else "N",  # Add bogo field
            "on_menu": "Y" if db_record.get("on_menu") == "Y" else "N",  # Add on_menu field
            "active_line_required": "Y" if str(db_record.get("active_line_required", "")).lower() in ["yes", "y"] else "N",
            "maintain_soc": "Y" if db_record.get("maintain_soc") == "Y" else "N",
            "maintain_active_line": "N",  # Not available in database
            "market_group": db_record.get("market_group", "*"),
            "store_group": db_record.get("store_group", "*"),
            "limit_per_ban": str(db_record.get("limit_per_ban", "")),
            "min_gsm_count": str(db_record.get("min_gsm_count", "")),
            "max_gsm_count": str(db_record.get("max_gsm_count", "")),
            "port_in_group_id": db_record.get("port_in_group_id", ""),
            "fpd_display_promo": "Y" if db_record.get("fpd_display_promo") == "Y" else "N",
            "nseip_drop": "Y" if db_record.get("nseip_drop") == "Y" else "N",
            "dcd_web_cart": "Y" if db_record.get("dcd_web_cart") == "Y" else "N",
            "promo_duration": str(db_record.get("promo_duration", "")),
            "delay_time": str(db_record.get("delay_time", "")),
            "application_grace_period": str(db_record.get("application_grace_period", "")),
            "device_sales_type": db_record.get("device_sales_type", ""),  # Add device_sales_type
            "activation_type": db_record.get("activation_type", ""),  # Add activation_type
            "account_type": db_record.get("account_type", ""),  # Add account_type
            "sales_application": db_record.get("sales_application", ""),  # Add sales_application
            "device_status_group_id": db_record.get("device_status_group_id", ""),
            "clawback_indicator": "Y" if db_record.get("clawback_indicator") == "Y" else "N",
            # Bill Facing Name (physical column may be 'bill facing name')
            "bill_facing_name": db_record.get("bill_facing_name") or db_record.get("bill facing name", ""),
            
            # Prefer direct DB column value for MPSS lookback; fall back to extraction from cat_description only if column absent/empty
            "mpss_lookback": db_record.get("mpss_lookback") or self._extract_mpss_lookback(db_record.get("cat_description", "")),
            
            # Add metadata
            "data_source": "database",
            "last_sync": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            
            # Execution type for tab separation
            "Desired_Execution": db_record.get("Desired_Execution", "RDC"),
            
            # Default values for fields not in database (PAM-only workflow fields)
            "pj_code": "",
            "sku_link": "",
            "tradein_link": "",
            "comm_end_date": format_date_for_html(db_record.get("comm_end_date")),
            "promo_grace": "",
            "trade_in_grace": "",
            "segment_name": "",
            "sub_segment": "",
            "segment_group_id": "",
            "segment_level": "",
            "flow_indicator": "NULL",
            "version_history": [],
            "uploaded_files": {},
            "generated_sql": "",
            "sql_file": {},
            "last_changes": None,
            "jira_ticket": "",
            # Initiative name from its own column; do not fall back to description to avoid overwriting user edits
            "initiative_name": db_record.get("initiative_name", ""),
            # Additional fields from database sample
            "crffc_maintainactivelinedev": "Y" if db_record.get("crffc_maintainactivelinedev") == "Y" else "N",
            "Broken_Trade": db_record.get("Broken_Trade", ""),
            "Anticipated_volume_take_rates_total": db_record.get("Anticipated_volume_take_rates_total", ""),
            
            # NEW FIELDS - Added from database analysis
            "Status": db_record.get("Status", ""),
            # Strip quotes from device fields if they exist
            "crffc_eligibletradeindevices": self._strip_quotes(db_record.get("crffc_eligibletradeindevices", "")),
            "cat_lobchannelhorizontalname": db_record.get("cat_lobchannelhorizontalname", ""),
            "cat_additionaleligibilityrequirementsname": db_record.get("cat_additionaleligibilityrequirementsname", ""),
            "cat_eligibledevices": self._strip_quotes(db_record.get("cat_eligibledevices", "")),
            "cat_channelsname": db_record.get("cat_channelsname", ""),
            "cat_description": db_record.get("cat_description", "")
        }

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

    def get_promo_extras(self, code: str) -> Dict[str, Any]:
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM promo_extras WHERE promo_code=?", (code,)).fetchone()
                return dict(row) if row else {}
        except Exception:
            return {}

    def upsert_promo_extras(self, code: str, extras: Dict[str, Any], user: str):
        # Extended field list to include testing status fields persisted with extras
        fields = ['jira_ticket','initiative_name','sku_link','tradein_link','promo_grace','trade_in_grace','segment_name','sub_segment','segment_group_id','segment_level','flow_indicator','test_status','zlab_status']
        cols = []
        vals = []
        for c in fields:
            cols.append(c)
            vals.append(extras.get(c))
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute(f"""
                    INSERT INTO promo_extras (promo_code, {', '.join(fields)}, created_at, updated_at, updated_by)
                    VALUES ({', '.join(['?']*(len(fields)+4))})
                    ON CONFLICT(promo_code) DO UPDATE SET
                        {', '.join([f"{f}=excluded.{f}" for f in fields])},
                        updated_at=excluded.updated_at,
                        updated_by=excluded.updated_by
                """, [code, *vals, now, now, user])
        except Exception as e:
            logger.error(f"Failed upsert extras for {code}: {e}")

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
            # Record creation history event with diff (fields old None -> new value)
            try:
                self.record_creation_event(code, {k: field_map.get(k) for k in insert_cols}, user=user)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Failed minimal insert for {code}: {e}")
            return False

    # --- SKU Group ID helpers ---
    def get_all_sku_group_ids(self) -> list[str]:
        """Return list of distinct sku_group_id values present in the source table (uppercase, pattern-like)."""
        sql = f"SELECT DISTINCT sku_group_id FROM {self.source_table} WHERE sku_group_id IS NOT NULL AND LEN(sku_group_id)=3"
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

    def record_version_entry(self, code: str, change_type: str, description: str, user: str, diff: Optional[Dict[str, Any]] = None):
        """Version history disabled/reset; no-op placeholder."""
        return

    # ===== New Minimal History API =====
    def record_creation_event(self, code: str, inserted_fields: Dict[str, Any], user: str = 'System') -> bool:
        """Record a single creation event with all inserted fields as NULL -> value diffs.

        inserted_fields: mapping of column->value used in initial insert.
        """
        try:
            diff = {}
            for k, v in (inserted_fields or {}).items():
                diff[k] = {'old': None, 'new': v}
            payload = (code, datetime.utcnow().isoformat(), 'Created', user, json.dumps(diff))
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute(
                    "INSERT INTO promo_history (promo_code, timestamp, event_type, user_name, diff_json) VALUES (?,?,?,?,?)",
                    payload
                )
            return True
        except Exception as e:
            logger.error(f"Failed to record creation event for {code}: {e}")
            return False

    def record_update_event(self, code: str, diff: Dict[str, Dict[str, Any]], user: str = 'System', window_seconds: int = 60) -> bool:
        """Record an update (edit) event with 1-minute consolidation window.

        If the most recent promo_history row for this promo is an 'Updated' event by the
        same user and its timestamp is within window_seconds of now, we MERGE the new diff
        into that existing row (keeping the original timestamp so the window does not slide).

        Merge semantics for each field:
          * If field not present yet -> add entire {old,new} pair.
          * If field present -> keep original 'old', overwrite 'new' with newest value.
        """
        if not diff:
            return False
        try:
            now = datetime.utcnow()
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT id, timestamp, user_name, diff_json FROM promo_history WHERE promo_code=? AND event_type='Updated' ORDER BY timestamp DESC, id DESC LIMIT 1",
                    (code,)
                )
                row = cur.fetchone()
                if row is not None:
                    try:
                        ts = datetime.fromisoformat(row['timestamp'])
                    except Exception:
                        ts = None
                    within_window = False
                    if ts is not None:
                        delta = (now - ts).total_seconds()
                        within_window = delta <= window_seconds
                    same_user = (row['user_name'] or 'System') == user
                    if within_window and same_user:
                        # Merge
                        existing = {}
                        try:
                            existing = json.loads(row['diff_json']) if row['diff_json'] else {}
                        except Exception:
                            existing = {}
                        for field, change in diff.items():
                            if field in existing and isinstance(existing[field], dict):
                                # Preserve original old; update new value
                                if isinstance(change, dict) and 'new' in change:
                                    existing[field]['new'] = change.get('new')
                            else:
                                existing[field] = change
                        conn.execute(
                            "UPDATE promo_history SET diff_json=? WHERE id=?",
                            (json.dumps(existing), row['id'])
                        )
                        return True
                # Otherwise insert new row
                payload = (code, now.isoformat(), 'Updated', user, json.dumps(diff))
                conn.execute(
                    "INSERT INTO promo_history (promo_code, timestamp, event_type, user_name, diff_json) VALUES (?,?,?,?,?)",
                    payload
                )
                return True
        except Exception as e:
            logger.error(f"Failed to record update event for {code}: {e}")
            return False

    def record_file_event(self, code: str, file_type: str, original_filename: str, stored_filename: str, size_bytes: int, checksum: Optional[str], user: str = 'System') -> bool:
        """Record a discrete file upload event (no consolidation) into promo_history.

        file_type expected values for history purposes:
          - sku_excel -> 'SKU List Uploaded'
          - tradein_excel -> 'Trade-In List Uploaded'
          - other types map to generic 'File Uploaded'
        Diff schema stored under keys representing metadata (original_filename, stored_filename, size_bytes, checksum, file_type).
        """
        try:
            mapping = {
                'sku_excel': 'SKU List Uploaded',
                'tradein_excel': 'Trade-In List Uploaded'
            }
            event_type = mapping.get(file_type, 'File Uploaded')
            diff = {
                'file_type': {'old': None, 'new': file_type},
                'original_filename': {'old': None, 'new': original_filename},
                'stored_filename': {'old': None, 'new': stored_filename},
                'size_bytes': {'old': None, 'new': size_bytes},
                'checksum': {'old': None, 'new': checksum}
            }
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute(
                    "INSERT INTO promo_history (promo_code, timestamp, event_type, user_name, diff_json) VALUES (?,?,?,?,?)",
                    (code, datetime.utcnow().isoformat(), event_type, user, json.dumps(diff))
                )
            return True
        except Exception as e:
            logger.error(f"Failed to record file event for {code}: {e}")
            return False

    def record_pcr_version_event(self, code: str, generation_time: float, sql_length: int, user: str = 'System') -> bool:
        """Record a PCR Version event with incrementing version number.

        Fields captured in diff: version (new only), generation_time_seconds, sql_length_chars, generated_at.
        Event label: PCR Version #N
        """
        try:
            # Count existing PCR Version events to determine next version number
            version = 1
            with sqlite3.connect(self._diag_db_path) as conn:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM promo_history WHERE promo_code=? AND event_type LIKE 'PCR Version %'",
                    (code,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    try:
                        version = int(row[0]) + 1
                    except Exception:
                        version = 1
                event_type = f"PCR Version #{version}"
                diff = {
                    'version': {'old': None, 'new': version},
                    'generation_time_seconds': {'old': None, 'new': round(generation_time, 4)},
                    'sql_length_chars': {'old': None, 'new': sql_length},
                    'generated_at': {'old': None, 'new': datetime.utcnow().isoformat()}
                }
                conn.execute(
                    "INSERT INTO promo_history (promo_code, timestamp, event_type, user_name, diff_json) VALUES (?,?,?,?,?)",
                    (code, datetime.utcnow().isoformat(), event_type, user, json.dumps(diff))
                )
            return True
        except Exception as e:
            logger.error(f"Failed to record PCR version event for {code}: {e}")
            return False

    def record_phase_change_event(self, code: str, old_phase: Optional[str], new_phase: str, user: str = 'System') -> bool:
        """Record a phase transition (Build -> Launched -> Expired, etc.).

        Stored as event_type 'Phase Change' with diff {'phase': {'old': old_phase, 'new': new_phase}}
        (old_phase may be None for initial materialization)
        """
        try:
            diff = {
                'phase': {'old': old_phase, 'new': new_phase}
            }
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute(
                    "INSERT INTO promo_history (promo_code, timestamp, event_type, user_name, diff_json) VALUES (?,?,?,?,?)",
                    (code, datetime.utcnow().isoformat(), 'Phase Change', user, json.dumps(diff))
                )
            return True
        except Exception as e:
            logger.error(f"Failed to record phase change for {code}: {e}")
            return False

    def record_end_date_system_update(self, code: str, old_end: str, new_end: str, user: str = 'System') -> bool:
        """Record a system-driven end date update event.

        Event label pattern: System Updates End Date - MM/DD/YYYY (new_end formatted)
        Diff contains only promo_end_date old -> new.
        """
        try:
            # Format target date for label; fall back to raw string if parsing fails
            label_date = new_end
            try:
                from datetime import datetime as _dt
                # Accept common date formats
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
                    try:
                        parsed = _dt.strptime(new_end, fmt)
                        label_date = parsed.strftime("%m/%d/%Y")
                        break
                    except Exception:
                        continue
            except Exception:
                pass
            event_type = f"System Updates End Date - {label_date}"
            diff = {
                'promo_end_date': {'old': old_end, 'new': new_end}
            }
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute(
                    "INSERT INTO promo_history (promo_code, timestamp, event_type, user_name, diff_json) VALUES (?,?,?,?,?)",
                    (code, datetime.utcnow().isoformat(), event_type, user, json.dumps(diff))
                )
            return True
        except Exception as e:
            logger.error(f"Failed to record end date system update for {code}: {e}")
            return False

    def get_creation_events(self, code: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute("SELECT promo_code, timestamp, event_type, user_name, diff_json FROM promo_history WHERE promo_code=? ORDER BY timestamp ASC", (code,))
                for r in cur.fetchall():
                    diff = None
                    try:
                        diff = json.loads(r['diff_json']) if r['diff_json'] else None
                    except Exception:
                        diff = None
                    rows.append({
                        'promo_code': r['promo_code'],
                        'timestamp': r['timestamp'],
                        'change_type': r['event_type'],
                        'changed_by': r['user_name'] or 'Unknown',
                        'description': 'Created Promo' if r['event_type'] == 'Created' else r['event_type'],
                        'field_changes': diff
                    })
        except Exception:
            return []
        return rows

    def count_version_events(self, code: str, change_type: str) -> int:
        """Return count of existing events for promo_code + change_type (SQLite)."""
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM version_history WHERE promo_code=? AND change_type=?",
                    (code, change_type)
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0
        except Exception:
            return 0

    def record_promo_file(self, code: str, original_filename: str, stored_filename: str, file_type: Optional[str], size_bytes: int, checksum: Optional[str], uploaded_by: str):
        """Persist a file upload record in promo_files."""
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute(
                    """INSERT INTO promo_files (promo_code, original_filename, stored_filename, file_type, size_bytes, checksum, uploaded_by, uploaded_at)
                        VALUES (?,?,?,?,?,?,?,?)""",
                    (code, original_filename, stored_filename, file_type, size_bytes, checksum, uploaded_by, datetime.utcnow().isoformat())
                )
        except Exception as e:
            logger.error(f"Failed to record promo file for {code}: {e}")

    def get_promo_files(self, code: str) -> List[Dict[str, Any]]:
        """Fetch uploaded file metadata records for a promo from SQLite.

        Returns list of rows with keys: original_filename, stored_filename, file_type, size_bytes, checksum, uploaded_at, uploaded_by
        """
        out: List[Dict[str, Any]] = []
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                cur = conn.execute(
                    "SELECT original_filename, stored_filename, file_type, size_bytes, checksum, uploaded_at, uploaded_by FROM promo_files WHERE promo_code=? ORDER BY uploaded_at DESC",
                    (code,)
                )
                for row in cur.fetchall():
                    try:
                        original_filename, stored_filename, file_type, size_bytes, checksum, uploaded_at, uploaded_by = row
                        out.append({
                            'original_filename': original_filename,
                            'stored_filename': stored_filename,
                            'file_type': file_type,
                            'size_bytes': size_bytes,
                            'checksum': checksum,
                            'uploaded_at': uploaded_at,
                            'uploaded_by': uploaded_by
                        })
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Failed to fetch promo files for {code}: {e}")
        return out

    def delete_promo_file(self, code: str, file_type: str):
        """Delete promo file metadata rows for a given promo + type."""
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute("DELETE FROM promo_files WHERE promo_code=? AND file_type=?", (code, file_type))
        except Exception as e:
            logger.error(f"Failed to delete promo file metadata for {code}/{file_type}: {e}")

    def delete_promo(self, promo_code: str, user_name: str = 'System') -> bool:
        """Delete a promotion row from the PAM source table and related metadata.

        This performs a HARD delete (no soft flag). Also removes any promo_extras and promo_files
        rows plus uploaded files directory if present. Records a version_history audit entry.
        Returns True on success (even if row absent), False on error.
        """
        code = (promo_code or '').strip()
        if not code:
            return False
        try:
            # 1. Delete from SQL Server source table
            engine = self.get_engine()
            del_sql = text(f"DELETE FROM {self.source_table} WHERE code = :code")
            with engine.begin() as conn:
                conn.execute(del_sql, { 'code': code })

            # 2. Clean SQLite metadata + version history audit
            with sqlite3.connect(self._diag_db_path) as conn:
                try:
                    conn.execute("DELETE FROM promo_extras WHERE promo_code=?", (code,))
                    conn.execute("DELETE FROM promo_files WHERE promo_code=?", (code,))
                    # NEW: remove history events for this promo
                    try:
                        conn.execute("DELETE FROM promo_history WHERE promo_code=?", (code,))
                    except Exception:
                        pass
                    conn.execute(
                        "INSERT INTO version_history (promo_code, timestamp, change_type, description, user_name, diff_json) VALUES (?,?,?,?,?,?)",
                        (code, datetime.utcnow().isoformat(), 'Deleted', f'Promo {code} deleted', user_name, None)
                    )
                    conn.commit()
                except Exception as ie:
                    logger.warning(f"Partial metadata cleanup failure for {code}: {ie}")

            # 3. Remove uploads folder (best-effort)
            uploads_dir = os.path.join('data','uploads', code)
            if os.path.isdir(uploads_dir):
                try:
                    import shutil
                    shutil.rmtree(uploads_dir, ignore_errors=True)
                except Exception:
                    pass
            logger.info(f"Deleted promo {code} from source + metadata")
            return True
        except Exception as e:
            logger.error(f"Failed to delete promo {code}: {e}")
            return False

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
