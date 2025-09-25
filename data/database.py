import pandas as pd
from sqlalchemy import create_engine, text
import urllib.parse
from typing import Dict, Any, List, Optional, Hashable
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
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS version_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        promo_code TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        description TEXT NOT NULL,
                        user_name TEXT NULL,
                        diff_json TEXT NULL
                    )
                """)
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
                    if 'user_name' not in cols:
                        conn.execute("ALTER TABLE version_history ADD COLUMN user_name TEXT NULL")
                except Exception as mig_e:
                    logger.warning(f"Version history migration check failed: {mig_e}")
        except Exception as e:
            logger.warning(f"Failed to ensure diagnostics tables: {e}")
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
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS version_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        promo_code TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        description TEXT NOT NULL,
                        user_name TEXT NULL,
                        diff_json TEXT NULL
                    )
                """)
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
                    if 'user_name' not in cols:
                        conn.execute("ALTER TABLE version_history ADD COLUMN user_name TEXT NULL")
                except Exception as mig_e:
                    logger.warning(f"Version history migration check failed: {mig_e}")
        except Exception as e:
            logger.warning(f"Failed to ensure diagnostics tables: {e}")
    
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
                
                # Test connection
                with self._engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("Database connection established ✅")
                
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                logger.error("Troubleshooting tips: 1) Verify server/port reachable (ping / Test-NetConnection) 2) Confirm ODBC driver installed 3) Check firewall/VPN 4) Validate credentials.")
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
    
    def get_all_promos(self) -> List[Dict[Hashable, Any]]:
        """Fetch all promotions from PAM_Orbit_Data table"""
        return self.get_promos_by_execution_type("RDC")

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
    
    def get_promos_by_execution_type(self, execution_type: str) -> List[Dict[Hashable, Any]]:
        """Fetch promotions filtered by Desired_Execution type (RDC, SPE, Rebate)"""
        sql = f"""
            SELECT 
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
            promo_srart_date,
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
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch {execution_type} promotions: {str(e)}")
            return []
    
    def get_all_spe_promos(self) -> List[Dict[Hashable, Any]]:
        """Fetch all SPE promotions from database"""
        return self.get_promos_by_execution_type("SPE")
    
    def get_all_rebates(self) -> List[Dict[Hashable, Any]]:
        """Fetch all rebate promotions from database"""
        return self.get_promos_by_execution_type("Rebate")
    
    def get_all_promotions_unified(self) -> List[Dict[Hashable, Any]]:
        """Fetch ALL promotions regardless of type"""
        sql = f"""
            SELECT 
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
            promo_srart_date,
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
            WHERE cast(promo_srart_date as date)  >= DATEADD(day, -?, GETDATE())
        ORDER BY code DESC
        """
        try:
            df = self.get_dataframe(sql)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch all promotions: {str(e)}")
            return []
    
    def get_promo_by_code(self, promo_code: str) -> Optional[Dict[str, Any]]:
        """Fetch specific promotion by code"""
        sql = f"""
    
    def get_promo_by_code(self, promo_code: str) -> Optional[Dict[str, Any]]:
        """Fetch specific promotion by code"""
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
            promo_srart_date,
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
        WHERE code = :promo_code
        """
        
        try:
            df = self.get_dataframe(sql, {'promo_code': promo_code})
            if not df.empty:
                return df.iloc[0].to_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to fetch promo {promo_code}: {str(e)}")
            return None

    def get_recent_promos(self, days: int = 30) -> List[Dict[Hashable, Any]]:
        """Fetch promotions created/updated in the last N days"""
        # Some rows have non-date / malformed values in promo_srart_date (stored as text).
        # Direct comparison causes implicit conversion and raises: Conversion failed when converting date and/or time from character string.
        # Use TRY_CONVERT to safely skip bad rows.
        sql = f"""
            SELECT 
            code,
            Owner,
            description,
            promo_srart_date,
            promo_end_date,
            amount,
            operator_id,
            orbit_id
            FROM {self.source_table}
        WHERE TRY_CONVERT(date, promo_srart_date) IS NOT NULL
    AND cast(promo_srart_date as date)  >= DATEADD(day, -:days, GETDATE())
        ORDER BY TRY_CONVERT(date, promo_srart_date) DESC
        """
        
        try:
            df = self.get_dataframe(sql, {'days': days})
            records = df.to_dict('records')
            # Diagnostic: count invalid date rows skipped
            try:
                # Pull a lightweight set of raw date values to count invalids
                raw_sql = f"SELECT promo_srart_date FROM {self.source_table} WHERE promo_srart_date IS NOT NULL"
                raw_df = self.get_dataframe(raw_sql)
                total_with_value = len(raw_df)
                valid_mask = raw_df['promo_srart_date'].apply(lambda v: self._is_valid_date_string(v))
                valid_count = int(valid_mask.sum())
                invalid_count = total_with_value - valid_count
                ratio = (invalid_count / total_with_value) if total_with_value else 0.0
                if total_with_value and ratio > self.invalid_ratio_threshold:
                    logger.warning(f"High invalid promo_srart_date ratio: {invalid_count}/{total_with_value} (>{self.invalid_ratio_threshold*100:.0f}%)")
                # Persist snapshot
                try:
                    with sqlite3.connect(self._diag_db_path) as c2:
                        c2.execute(
                            "INSERT INTO date_diagnostics_history (captured_at, window_days, total_with_value, valid_dates, invalid_dates, invalid_ratio) VALUES (?,?,?,?,?,?)",
                            (datetime.utcnow().isoformat(), days, total_with_value, valid_count, invalid_count, ratio)
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
            return records
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
    
    def get_active_promos(self) -> List[Dict[Hashable, Any]]:
        """Fetch currently active promotions"""
        sql = f"""
            SELECT 
            code,
            Owner,
            description,
            promo_srart_date,
            promo_end_date,
            amount,
            operator_id,
            orbit_id
            FROM {self.source_table}
            WHERE TRY_CONVERT(date, promo_srart_date) IS NOT NULL
              AND TRY_CONVERT(date, promo_end_date) IS NOT NULL
              AND CONVERT(date, GETDATE()) BETWEEN TRY_CONVERT(date, promo_srart_date) AND TRY_CONVERT(date, promo_end_date)
            ORDER BY TRY_CONVERT(date, promo_srart_date) DESC
        """
        try:
            df = self.get_dataframe(sql, {'days': days})
            records = df.to_dict('records')
            # Diagnostic: count invalid date rows skipped
            try:
                # Pull a lightweight set of raw date values to count invalids
                raw_sql = f"SELECT promo_srart_date FROM {self.source_table} WHERE promo_srart_date IS NOT NULL"
                raw_df = self.get_dataframe(raw_sql)
                total_with_value = len(raw_df)
                valid_mask = raw_df['promo_srart_date'].apply(lambda v: self._is_valid_date_string(v))
                valid_count = int(valid_mask.sum())
                invalid_count = total_with_value - valid_count
                ratio = (invalid_count / total_with_value) if total_with_value else 0.0
                if total_with_value and ratio > self.invalid_ratio_threshold:
                    logger.warning(f"High invalid promo_srart_date ratio: {invalid_count}/{total_with_value} (>{self.invalid_ratio_threshold*100:.0f}%)")
                # Persist snapshot
                try:
                    with sqlite3.connect(self._diag_db_path) as c2:
                        c2.execute(
                            "INSERT INTO date_diagnostics_history (captured_at, window_days, total_with_value, valid_dates, invalid_dates, invalid_ratio) VALUES (?,?,?,?,?,?)",
                            (datetime.utcnow().isoformat(), days, total_with_value, valid_count, invalid_count, ratio)
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
            return records
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
    
    def get_active_promos(self) -> List[Dict[Hashable, Any]]:
        """Fetch currently active promotions"""
        sql = f"""
            SELECT 
            code,
            Owner,
            description,
            promo_srart_date,
            promo_end_date,
            amount,
            operator_id,
            orbit_id
            FROM {self.source_table}
            WHERE TRY_CONVERT(date, promo_srart_date) IS NOT NULL
              AND TRY_CONVERT(date, promo_end_date) IS NOT NULL
              AND CONVERT(date, GETDATE()) BETWEEN TRY_CONVERT(date, promo_srart_date) AND TRY_CONVERT(date, promo_end_date)
            ORDER BY TRY_CONVERT(date, promo_srart_date) DESC
        """
        try:
            df = self.get_dataframe(sql)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch active promos: {str(e)}")
            logger.error(f"Failed to fetch active promos: {str(e)}")
            return []
    
    def search_promos(self, search_term: str) -> List[Dict[Hashable, Any]]:
        """Search promotions by code or description"""
        sql = f"""
            SELECT 
    def search_promos(self, search_term: str) -> List[Dict[Hashable, Any]]:
        """Search promotions by code or description"""
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
            promo_srart_date,
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
            WHERE (code LIKE :search_term 
               OR description LIKE :search_term
               OR [bill facing name] LIKE :search_term)
              AND TRY_CONVERT(date, promo_srart_date) IS NOT NULL
            ORDER BY TRY_CONVERT(date, promo_srart_date) DESC
        """
        try:
            search_pattern = f"%{search_term}%"
            df = self.get_dataframe(sql, {'search_term': search_pattern})
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to search promos: {str(e)}")
            logger.error(f"Failed to search promos: {str(e)}")
            return []

    def get_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Fetch lightweight orbit intake row by orbit_id.

        1) Query raw orbit source table (self.orbit_source_table) which contains intake data before promo creation.
        2) If not found AND orbit & promo tables differ, fallback to promotions table (self.source_table).
        Returns minimal normalized dict or None.
        """
        def _run(sql_table: str):
            sql_local = f"""
                SELECT orbit_id,[bill facing name] as bill_facing_name,description,Owner,promo_srart_date,promo_end_date
                FROM {sql_table}
                WHERE orbit_id = :orbit_id
            """
            try:
                df_local = self.get_dataframe(sql_local, {'orbit_id': orbit_id})
                if df_local.empty:
                    return None
                r = df_local.iloc[0].to_dict()
                return {
                    'orbit_id': r.get('orbit_id',''),
                    'bill_facing_name': r.get('bill_facing_name') or r.get('description',''),
                    'description': r.get('description',''),
                    'owner': str(r.get('Owner','')).strip('"'),
                    'promo_start_date': r.get('promo_srart_date',''),
                    'promo_end_date': r.get('promo_end_date',''),
                    '_table': sql_table
                }
            except Exception as ex:
                logger.error(f"Orbit-only lookup query failed against {sql_table}: {ex}")
                return None
        # Primary: raw orbit table
        primary = _run(self.orbit_source_table)
        if primary:
            return primary
        # Fallback if different
        if self.orbit_source_table != self.source_table:
            return _run(self.source_table)
        return None

    def get_full_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full raw orbit (intake) record; fallback to promotions table if not found.

        Priority: self.orbit_source_table then self.source_table (if different).
        Returns dict or None.
        """
        base_select = """
            SELECT 

    def get_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Fetch lightweight orbit intake row by orbit_id.

        1) Query raw orbit source table (self.orbit_source_table) which contains intake data before promo creation.
        2) If not found AND orbit & promo tables differ, fallback to promotions table (self.source_table).
        Returns minimal normalized dict or None.
        """
        def _run(sql_table: str):
            sql_local = f"""
                SELECT orbit_id,[bill facing name] as bill_facing_name,description,Owner,promo_srart_date,promo_end_date
                FROM {sql_table}
                WHERE orbit_id = :orbit_id
            """
            try:
                df_local = self.get_dataframe(sql_local, {'orbit_id': orbit_id})
                if df_local.empty:
                    return None
                r = df_local.iloc[0].to_dict()
                return {
                    'orbit_id': r.get('orbit_id',''),
                    'bill_facing_name': r.get('bill_facing_name') or r.get('description',''),
                    'description': r.get('description',''),
                    'owner': str(r.get('Owner','')).strip('"'),
                    'promo_start_date': r.get('promo_srart_date',''),
                    'promo_end_date': r.get('promo_end_date',''),
                    '_table': sql_table
                }
            except Exception as ex:
                logger.error(f"Orbit-only lookup query failed against {sql_table}: {ex}")
                return None
        # Primary: raw orbit table
        primary = _run(self.orbit_source_table)
        if primary:
            return primary
        # Fallback if different
        if self.orbit_source_table != self.source_table:
            return _run(self.source_table)
        return None

    def get_full_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full raw orbit (intake) record; fallback to promotions table if not found.

        Priority: self.orbit_source_table then self.source_table (if different).
        Returns dict or None.
        """
        base_select = """
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
            promo_srart_date,
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
        def _query(table_name: str):
            try:
                sql_local = base_select.format(table=table_name)
                df_local = self.get_dataframe(sql_local, {'orbit_id': orbit_id})
                if df_local.empty:
                    return None
                rec = df_local.iloc[0].to_dict()
                rec['_table'] = table_name
                return rec
            except Exception as ex:
                logger.error(f"Full orbit lookup failed against {table_name} for {orbit_id}: {ex}")
                return None
        primary = _query(self.orbit_source_table)
        if primary:
            return primary
        if self.orbit_source_table != self.source_table:
            return _query(self.source_table)
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
            "promo_start_date": format_date_for_html(db_record.get("promo_srart_date")),
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
            
            # Parse cat_description to extract MPSS lookback value
            "mpss_lookback": self._extract_mpss_lookback(db_record.get("cat_description", "")),
            
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
            "initiative_name": db_record.get("description", ""),  # Map description to initiative_name for UI
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
        
        return json_record

    # --- Write helpers for PAM table & SQLite overlays ---
    def update_promo_fields(self, code: str, field_map: Dict[str, Any]) -> bool:
        """Update mutable fields in PAM source table.

        field_map: dict of column->value (only columns that exist in self.source_table)
        Returns True if update succeeded (>=0 rows). Silent if no fields provided.
        """
        if not field_map:
            return True
        # Build dynamic SQL with parameters
        assignments = []
        params = {}
        for i,(col,val) in enumerate(field_map.items()):
            safe_col = col  # assume validated upstream
            param_name = f"p{i}"
            assignments.append(f"{safe_col} = :{param_name}")
            params[param_name] = val
        params['code'] = code
        sql = f"UPDATE {self.source_table} SET " + ", ".join(assignments) + " WHERE code = :code"
        try:
            engine = self.get_engine()
            with engine.begin() as conn:
                conn.execute(text(sql), params)
            return True
        except Exception as e:
            logger.error(f"Failed to update promo {code}: {e}")
            return False

    def get_promo_extras(self, code: str) -> Dict[str, Any]:
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM promo_extras WHERE promo_code=?", (code,)).fetchone()
                return dict(row) if row else {}
        except Exception:
            return {}

    def upsert_promo_extras(self, code: str, extras: Dict[str, Any], user: str):
        fields = ['jira_ticket','initiative_name','sku_link','tradein_link','promo_grace','trade_in_grace','segment_name','sub_segment','segment_group_id','segment_level','flow_indicator']
        cols = []
        vals = []
        for c in fields:
            cols.append(c)
            vals.append(extras.get(c))
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute("""
                    INSERT INTO promo_extras (promo_code, jira_ticket, initiative_name, sku_link, tradein_link, promo_grace, trade_in_grace, segment_name, sub_segment, segment_group_id, segment_level, flow_indicator, created_at, updated_at, updated_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(promo_code) DO UPDATE SET
                        jira_ticket=excluded.jira_ticket,
                        initiative_name=excluded.initiative_name,
                        sku_link=excluded.sku_link,
                        tradein_link=excluded.tradein_link,
                        promo_grace=excluded.promo_grace,
                        trade_in_grace=excluded.trade_in_grace,
                        segment_name=excluded.segment_name,
                        sub_segment=excluded.sub_segment,
                        segment_group_id=excluded.segment_group_id,
                        segment_level=excluded.segment_level,
                        flow_indicator=excluded.flow_indicator,
                        updated_at=excluded.updated_at,
                        updated_by=excluded.updated_by
                """, [code, *vals, now, now, user])
        except Exception as e:
            logger.error(f"Failed upsert extras for {code}: {e}")

    def record_version_entry(self, code: str, change_type: str, description: str, user: str, diff: Optional[Dict[str, Any]] = None):
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute(
                    "INSERT INTO version_history (promo_code, timestamp, change_type, description, user_name, diff_json) VALUES (?,?,?,?,?,?)",
                    (code, datetime.utcnow().isoformat(), change_type, description, user, json.dumps(diff) if diff else None)
                )
        except Exception as e:
            logger.error(f"Failed to record version history for {code}: {e}")

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
        for i, (col, val) in enumerate(field_map.items()):
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
            return False

    # --- Write helpers for PAM table & SQLite overlays ---
    def update_promo_fields(self, code: str, field_map: Dict[str, Any]) -> bool:
        """Update mutable fields in PAM source table.

        field_map: dict of column->value (only columns that exist in self.source_table)
        Returns True if update succeeded (>=0 rows). Silent if no fields provided.
        """
        if not field_map:
            return True
        # Build dynamic SQL with parameters
        assignments = []
        params = {}
        for i,(col,val) in enumerate(field_map.items()):
            safe_col = col  # assume validated upstream
            param_name = f"p{i}"
            assignments.append(f"{safe_col} = :{param_name}")
            params[param_name] = val
        params['code'] = code
        sql = f"UPDATE {self.source_table} SET " + ", ".join(assignments) + " WHERE code = :code"
        try:
            engine = self.get_engine()
            with engine.begin() as conn:
                conn.execute(text(sql), params)
            return True
        except Exception as e:
            logger.error(f"Failed to update promo {code}: {e}")
            return False

    def get_promo_extras(self, code: str) -> Dict[str, Any]:
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM promo_extras WHERE promo_code=?", (code,)).fetchone()
                return dict(row) if row else {}
        except Exception:
            return {}

    def upsert_promo_extras(self, code: str, extras: Dict[str, Any], user: str):
        fields = ['jira_ticket','initiative_name','sku_link','tradein_link','promo_grace','trade_in_grace','segment_name','sub_segment','segment_group_id','segment_level','flow_indicator']
        cols = []
        vals = []
        for c in fields:
            cols.append(c)
            vals.append(extras.get(c))
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute("""
                    INSERT INTO promo_extras (promo_code, jira_ticket, initiative_name, sku_link, tradein_link, promo_grace, trade_in_grace, segment_name, sub_segment, segment_group_id, segment_level, flow_indicator, created_at, updated_at, updated_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(promo_code) DO UPDATE SET
                        jira_ticket=excluded.jira_ticket,
                        initiative_name=excluded.initiative_name,
                        sku_link=excluded.sku_link,
                        tradein_link=excluded.tradein_link,
                        promo_grace=excluded.promo_grace,
                        trade_in_grace=excluded.trade_in_grace,
                        segment_name=excluded.segment_name,
                        sub_segment=excluded.sub_segment,
                        segment_group_id=excluded.segment_group_id,
                        segment_level=excluded.segment_level,
                        flow_indicator=excluded.flow_indicator,
                        updated_at=excluded.updated_at,
                        updated_by=excluded.updated_by
                """, [code, *vals, now, now, user])
        except Exception as e:
            logger.error(f"Failed upsert extras for {code}: {e}")

    def record_version_entry(self, code: str, change_type: str, description: str, user: str, diff: Optional[Dict[str, Any]] = None):
        try:
            with sqlite3.connect(self._diag_db_path) as conn:
                conn.execute(
                    "INSERT INTO version_history (promo_code, timestamp, change_type, description, user_name, diff_json) VALUES (?,?,?,?,?,?)",
                    (code, datetime.utcnow().isoformat(), change_type, description, user, json.dumps(diff) if diff else None)
                )
        except Exception as e:
            logger.error(f"Failed to record version history for {code}: {e}")

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
        for i, (col, val) in enumerate(field_map.items()):
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
            return False
