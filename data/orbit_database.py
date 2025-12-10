"""Lightweight Orbit DB manager.

Provides minimal read-only access to the orbit table using ORBIT_* env vars or
ORBIT_CONNECTION_STRING. Supports both local SQL Server and Microsoft Fabric 
Data Warehouse based on USE_FABRIC_ORBIT environment variable.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
from dotenv import load_dotenv, find_dotenv

class OrbitDatabaseManager:
    def __init__(self):
        # Attempt to load .env if not already loaded (idempotent)
        try:
            env_path = find_dotenv()
            if env_path:
                load_dotenv(env_path)
        except Exception:
            pass
        
        # Check if we should use Fabric instead of local SQL Server
        self.use_fabric = os.getenv('USE_FABRIC_ORBIT', 'false').lower() == 'true'
        
        if self.use_fabric:
            # Delegate to Fabric manager
            from .fabric_database import FabricDatabaseManager
            self._fabric_manager = FabricDatabaseManager()
            self._last_error = None
            self.table = 'dbo.ORBIT_Reporting_Table'  # Fabric table name
            return
        
        # Original SQL Server configuration
        raw_conn = os.getenv('ORBIT_CONNECTION_STRING')
        # Treat placeholder as absent
        if raw_conn and 'Server=server;' in raw_conn:
            raw_conn = None
        self.connection_string = raw_conn
        self.server = os.getenv('ORBIT_DB_SERVER') or os.getenv('PAM_DB_SERVER','localhost')
        self.database = os.getenv('ORBIT_DB_DATABASE') or os.getenv('PAM_DB_DATABASE','PromoQuality')
        self.username = os.getenv('ORBIT_DB_USERNAME') or os.getenv('PAM_DB_USERNAME','')
        self.password = os.getenv('ORBIT_DB_PASSWORD') or os.getenv('PAM_DB_PASSWORD','')
        self.driver = os.getenv('ORBIT_DB_DRIVER','ODBC Driver 17 for SQL Server')
        self.encrypt = os.getenv('ORBIT_DB_ENCRYPT','no').lower()
        self.trust_cert = os.getenv('ORBIT_DB_TRUST_CERT','yes').lower()
        self.login_timeout = os.getenv('ORBIT_DB_LOGIN_TIMEOUT','15')
        self.table = os.getenv('ORBIT_TABLE') or '[RDC].[PAM_Orbit_Data]'
        self._used_connection_string = None
        self._last_error = None

    def _build_conn_str(self) -> str:
        if self.connection_string:
            return self.connection_string
        return (f"DRIVER={{{self.driver}}};SERVER={self.server};DATABASE={self.database};"\
                f"UID={self.username};PWD={self.password};Encrypt={self.encrypt};TrustServerCertificate={self.trust_cert};"\
                f"LoginTimeout={self.login_timeout}")

    def _connect(self):
        import pyodbc
        attempted = []
        base_conn_str = self._build_conn_str()
        variants = []
        # If server has pattern Host\Instance,Port produce stripped variants
        if '\\' in self.server and ',' in self.server:
            host_part = self.server.split('\\')[0]
            instance_part = self.server.split('\\')[1].split(',')[0]
            port_part = self.server.split(',')[1]
            # Variant 1: host,port
            variants.append(f"DRIVER={{{self.driver}}};SERVER={host_part},{port_part};DATABASE={self.database};UID={self.username};PWD={self.password};Encrypt={self.encrypt};TrustServerCertificate={self.trust_cert};LoginTimeout={self.login_timeout}")
            # Variant 2: host\\instance (drop port)
            variants.append(f"DRIVER={{{self.driver}}};SERVER={host_part}\\{instance_part};DATABASE={self.database};UID={self.username};PWD={self.password};Encrypt={self.encrypt};TrustServerCertificate={self.trust_cert};LoginTimeout={self.login_timeout}")
        # Always attempt original first
        for conn_str in [base_conn_str] + variants:
            try:
                c = pyodbc.connect(conn_str)
                self._used_connection_string = conn_str
                return c
            except Exception as e:
                attempted.append(f"{e}")
                self._last_error = f"connection failed: {e}"
                continue
        raise Exception(self._last_error or 'connection attempts failed')

    def get_orbit_record(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        # Route to Fabric if enabled
        if self.use_fabric:
            result = self._fabric_manager.search_by_gtm_id(orbit_id)
            if result:
                # Map Fabric fields to expected format
                return {
                    'Owner': result.get('cat_businessowner'),
                    'bill_facing_name': result.get('cat_billname'),  # Bill facing name
                    'initiative_name': result.get('cat_initiativename'),  # Initiative name
                    'orbit_id': result.get('cat_gtmentryid'),
                    'description': result.get('cat_description'),  # Full description
                    'promo_start_date': result.get('cat_startdate'),
                    'promo_end_date': result.get('cat_enddate'),
                    **result  # Include all other fields
                }
            return {'_error': 'not found'}
        
        # Original SQL Server logic
        oid = (orbit_id or '').strip()
        if not oid:
            return {'_error': 'orbit_id required'}
        sql = ("SELECT Owner, [bill facing name] AS bill_facing_name, orbit_id, description, "
               "promo_srart_date AS promo_start_date, promo_end_date "
               f"FROM {self.table} WHERE orbit_id = ?")
        self._last_error = None
        try:
            conn = self._connect()
        except Exception:
            # Include attempted connection info in error payload
            return {'_error': self._last_error, '_used_connection': self._used_connection_string}
        try:
            cur = conn.cursor()
            cur.execute(sql, (oid,))
            row = cur.fetchone()
            if not row:
                return {'_error': 'not found'}
            cols = [c[0] for c in cur.description]
            data = {c: (v.strip() if isinstance(v, str) else v) for c, v in zip(cols, row)}
            return data
        except Exception as ex:
            self._last_error = f"query failed: {ex}"
            return {'_error': self._last_error, '_used_connection': self._used_connection_string}
        finally:
            try: conn.close()
            except Exception: pass

    def list_orbit_ids(self, limit: int = 10) -> List[str]:
        # Route to Fabric if enabled
        if self.use_fabric:
            promotions = self._fabric_manager.get_all_promotions(limit=limit)
            return [p.get('cat_gtmentryid', '') for p in promotions if p.get('cat_gtmentryid')]
        
        # Original SQL Server logic
        sql = f"SELECT TOP {limit} orbit_id FROM {self.table} WHERE orbit_id IS NOT NULL"
        out: List[str] = []
        try:
            conn = self._connect()
        except Exception:
            return out
        try:
            cur = conn.cursor()
            cur.execute(sql)
            for r in cur.fetchall():
                out.append(str(r[0]))
        except Exception:
            return out
        finally:
            try: conn.close()
            except Exception: pass
        return out

    def get_columns(self) -> List[str]:
        # Route to Fabric if enabled
        if self.use_fabric:
            # Return common Fabric column names
            return ['cat_initiativename', 'crffc_promocodeid', 'cat_gtmentryid', 'cat_startdate', 
                    'cat_enddate', 'cat_billname', 'cat_description', 'modifiedon']
        
        # Original SQL Server logic
        sql = f"SELECT TOP 1 * FROM {self.table}"
        try:
            conn = self._connect()
        except Exception:
            return []
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return [c[0] for c in cur.description]
        except Exception:
            return []
        finally:
            try: conn.close()
            except Exception: pass

__all__ = ["OrbitDatabaseManager"]
