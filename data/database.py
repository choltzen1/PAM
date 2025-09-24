import pandas as pd
from sqlalchemy import create_engine, text
import urllib.parse
from typing import Dict, Any, List, Optional, Hashable
from datetime import datetime
import logging
import os
import sqlite3

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
                
                # Test connection
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
    
    def get_promos_by_execution_type(self, execution_type: str) -> List[Dict[Hashable, Any]]:
        """Fetch promotions filtered by Desired_Execution type (RDC, SPE, Rebate)"""
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
        sql = """
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
            df = self.get_dataframe(sql)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch active promos: {str(e)}")
            return []
    
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
            Desired_Execution
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
            return []

    def get_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Fetch raw promotion row by orbit_id only (record may not yet have a promo code assigned)."""
        sql = f"""
            SELECT 
            orbit_id,
            [bill facing name] as bill_facing_name,
            description,
            Owner,
            promo_srart_date,
            promo_end_date
            FROM {self.source_table}
            WHERE orbit_id = :orbit_id
        """
        try:
            df = self.get_dataframe(sql, {'orbit_id': orbit_id})
            if df.empty:
                return None
            row = df.iloc[0].to_dict()
            normalized = {
                'orbit_id': row.get('orbit_id',''),
                'bill_facing_name': row.get('bill_facing_name') or row.get('description',''),
                'description': row.get('description',''),
                'owner': str(row.get('Owner','')).strip('"'),
                'promo_start_date': row.get('promo_srart_date',''),
                'promo_end_date': row.get('promo_end_date','')
            }
            return normalized
        except Exception as e:
            logger.error(f"Orbit-only lookup failed for {orbit_id}: {e}")
            return None

    def get_full_orbit_record_by_orbit_id(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the full raw orbit record for ingestion (does not require code).

        Returns database row as dict or None.
        """
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
        WHERE orbit_id = :orbit_id
        """
        try:
            df = self.get_dataframe(sql, {'orbit_id': orbit_id})
            if df.empty:
                return None
            return df.iloc[0].to_dict()
        except Exception as e:
            logger.error(f"Full orbit lookup failed for {orbit_id}: {e}")
            return None
    
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
            "mpss_lookback": str(db_record.get("mpss_lookback", "")),
            "device_status_group_id": db_record.get("device_status_group_id", ""),
            "clawback_indicator": "Y" if db_record.get("clawback_indicator") == "Y" else "N",
            
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
            "Anticipated_volume_take_rates_total": db_record.get("Anticipated_volume_take_rates_total", "")
        }
        
        return json_record
