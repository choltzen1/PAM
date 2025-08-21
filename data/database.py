import pandas as pd
from sqlalchemy import create_engine, text
import urllib.parse
from typing import Dict, Any, List, Optional, Hashable
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages SQL Server database connections and queries for live promo data"""
    
    def __init__(self):
        self.server = 'PPOLWPQMR00003,50107'
        self.database = 'PromoQuality'
        self.username = 'Python_user'
        self.password = 'Pit30&i5t#w@y45$%^'
        self._engine = None
    
    def get_engine(self):
        """Create and return SQLAlchemy engine"""
        if self._engine is None:
            try:
                params = urllib.parse.quote_plus(
                    f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={self.server};DATABASE={self.database};UID={self.username};PWD={self.password}'
                )
                self._engine = create_engine(f'mssql+pyodbc:///?odbc_connect={params}')
                
                # Test connection
                with self._engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("Database connection established ✅")
                
            except Exception as e:
                logger.error(f"Failed to connect to database: {str(e)}")
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
        sql = """
        SELECT 
            code,
            Owner,
            description,
            promo_srart_date,
            promo_end_date,
            amount,
            discount,
            operator_id,
            orbit_id,
            sku_group_id,
            soc_grouping,
            product_type,
            active_line_required,
            maintain_soc,
            market_group,
            store_group,
            limit_per_ban,
            account_type,
            sales_application,
            activation_type,
            device_sales_type,
            clawback_indicator,
            on_menu,
            fpd_display_promo,
            dcd_web_cart,
            bogo,
            nseip_drop,
            promo_duration,
            delay_time,
            application_grace_period,
            Broken_Trade,
            Desired_Execution
        FROM [RDC].[PAM_Orbit_Data]
        ORDER BY code DESC
        """
        
        try:
            df = self.get_dataframe(sql)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch promotions: {str(e)}")
            return []
    
    def get_promo_by_code(self, promo_code: str) -> Optional[Dict[str, Any]]:
        """Fetch specific promotion by code"""
        sql = """
        SELECT 
            code,
            Owner,
            description,
            promo_srart_date,
            promo_end_date,
            amount,
            discount,
            operator_id,
            orbit_id,
            sku_group_id,
            soc_grouping,
            product_type,
            active_line_required,
            maintain_soc,
            market_group,
            store_group,
            limit_per_ban,
            account_type,
            sales_application,
            activation_type,
            device_sales_type,
            clawback_indicator,
            on_menu,
            fpd_display_promo,
            dcd_web_cart,
            bogo,
            nseip_drop,
            promo_duration,
            delay_time,
            application_grace_period,
            Broken_Trade,
            Desired_Execution
        FROM [RDC].[PAM_Orbit_Data]
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
        sql = """
        SELECT 
            code,
            Owner,
            description,
            promo_srart_date,
            promo_end_date,
            amount,
            operator_id,
            orbit_id
        FROM [RDC].[PAM_Orbit_Data]
        WHERE promo_srart_date >= DATEADD(day, -:days, GETDATE())
        ORDER BY promo_srart_date DESC
        """
        
        try:
            df = self.get_dataframe(sql, {'days': days})
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch recent promos: {str(e)}")
            return []
    
    def get_active_promos(self) -> List[Dict[Hashable, Any]]:
        """Fetch currently active promotions"""
        sql = """
        SELECT 
            code,
            Owner,
            description,
            promo_srart_date,
            promo_end_date,
            amount,
            operator_id,
            orbit_id
        FROM [RDC].[PAM_Orbit_Data]
        WHERE GETDATE() BETWEEN promo_srart_date AND promo_end_date
        ORDER BY promo_srart_date DESC
        """
        
        try:
            df = self.get_dataframe(sql)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch active promos: {str(e)}")
            return []
    
    def search_promos(self, search_term: str) -> List[Dict[Hashable, Any]]:
        """Search promotions by code or description"""
        sql = """
        SELECT 
            code,
            Owner,
            description,
            promo_srart_date,
            promo_end_date,
            amount,
            operator_id,
            orbit_id
        FROM [RDC].[PAM_Orbit_Data]
        WHERE code LIKE :search_term 
           OR description LIKE :search_term
        ORDER BY promo_srart_date DESC
        """
        
        try:
            search_pattern = f"%{search_term}%"
            df = self.get_dataframe(sql, {'search_term': search_pattern})
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to search promos: {str(e)}")
            return []
    
    def convert_db_record_to_json_format(self, db_record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database record to JSON storage format"""
        # Map database columns to JSON format
        json_record = {
            "code": db_record.get("code", ""),
            "description": db_record.get("description", ""),
            "promo_start_date": str(db_record.get("promo_srart_date", "")) if db_record.get("promo_srart_date") else "",
            "promo_end_date": str(db_record.get("promo_end_date", "")) if db_record.get("promo_end_date") else "",
            "amount": str(db_record.get("amount", "")),
            "discount": str(db_record.get("discount", "")),
            "operator_id": str(db_record.get("operator_id", "")),
            "bptcr": str(db_record.get("orbit_id", "")),
            "sku_group_id": db_record.get("sku_group_id", ""),
            "soc_grouping": db_record.get("soc_grouping", ""),
            "trade_in_group_id": db_record.get("trade_in_group_id", ""),
            "product_type": db_record.get("product_type", ""),
            "active_line_required": "Y" if db_record.get("active_line_required") == "Y" else "N",
            "maintain_soc": "Y" if db_record.get("maintain_soc") == "Y" else "N",
            "maintain_active_line": "N",  # Not available in database
            "market_group": db_record.get("market_group", "*"),
            "store_group": db_record.get("store_group", "*"),
            "limit_per_ban": db_record.get("limit_per_ban", ""),
            "min_gsm_count": str(db_record.get("min_gsm_count", "")),
            "max_gsm_count": str(db_record.get("max_gsm_count", "")),
            "port_in_group_id": db_record.get("port_in_group_id", ""),
            "fpd_display_promo": "Y" if db_record.get("fpd_display_promo") == "Y" else "N",
            "nseip_drop": "Y" if db_record.get("nseip_drop") == "Y" else "N",
            "dcd_web_cart": "Y" if db_record.get("dcd_web_cart") == "Y" else "N",
            "promo_duration": str(db_record.get("promo_duration", "")),
            "delay_time": str(db_record.get("delay_time", "")),
            "application_grace_period": db_record.get("application_grace_period", ""),
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
            
            # Default values for fields not in database
            "owner": str(db_record.get("Owner", "Unknown")).strip('"'),  # Remove quotes from owner field
            "bill_facing_name": db_record.get("description", ""),  # Use description instead
            "orbit_id": db_record.get("orbit_id", ""),
            "pj_code": "",
            "promo_notes": "",
            "bogo": db_record.get("bogo", "N"),
            "on_menu": db_record.get("on_menu", "N"),
            "sku_link": "",
            "tradein_link": "",
            "comm_end_date": "",
            "promo_grace": "",
            "trade_in_grace": "",
            "device_sales_type": db_record.get("device_sales_type", ""),
            "activation_type": db_record.get("activation_type", "*"),
            "segment_name": "",
            "sub_segment": "",
            "segment_group_id": "",
            "segment_level": "",
            "account_type": db_record.get("account_type", ""),
            "sales_application": db_record.get("sales_application", ""),
            "flow_indicator": "NULL",
            "version_history": [],
            "uploaded_files": {},
            "generated_sql": "",
            "sql_file": {},
            "last_changes": None,
            "jira_ticket": "",
            "initiative_name": ""
        }
        
        return json_record
