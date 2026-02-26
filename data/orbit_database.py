"""Orbit DB manager - SQL Server (rdc.pam_orbit_data).

Provides read-only access to orbit data from SQL Server.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import text
from .database import DatabaseManager

class OrbitDatabaseManager:
    def __init__(self):
        # Attempt to load .env if not already loaded (idempotent)
        try:
            env_path = find_dotenv()
            if env_path:
                load_dotenv(env_path)
        except Exception:
            pass
        
        self._last_error = None
        self.table = os.getenv('ORBIT_TABLE', 'rdc.pam_orbit_data')
        self._db = DatabaseManager()

    def get_orbit_record(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Get orbit record from SQL Server by orbit_id."""
        oid = (orbit_id or '').strip()
        if not oid:
            return {'_error': 'orbit_id required'}

        engine = self._db.get_engine()
        if not engine:
            return {'_error': 'db connection failed'}

        sql = text(f"SELECT TOP 1 * FROM {self.table} WHERE orbit_id = :oid")
        row = None
        with engine.connect() as conn:
            row = conn.execute(sql, {'oid': oid}).mappings().first()
            if not row and oid.isdigit():
                row = conn.execute(sql, {'oid': int(oid)}).mappings().first()

        if not row:
            return {'_error': 'not found'}

        raw = dict(row)
        mapped = {
            'Owner': raw.get('Owner') or raw.get('owner') or raw.get('promo_owner'),
            'promo_owner': raw.get('promo_owner') or raw.get('Owner') or raw.get('owner'),
            'promo_owner_email': raw.get('promo_owner_email') or raw.get('owner_email'),
            'bill_facing_name': raw.get('bill facing name') or raw.get('bill_facing_name') or raw.get('Bill_Facing_Name'),
            'initiative_name': raw.get('initiative_name') or raw.get('initiative name'),
            'orbit_id': raw.get('orbit_id') or raw.get('cat_gtmentryid') or raw.get('cat_legacygtmentryid'),
            'description': raw.get('description') or raw.get('cat_description'),
            'promo_notes': raw.get('promo_notes'),
            'promo_start_date': raw.get('promo_start_date') or raw.get('promo_start') or raw.get('start_date'),
            'promo_end_date': raw.get('promo_end_date') or raw.get('end_date'),
            'comm_end_date': raw.get('comm_end_date'),
            'discount': raw.get('discount'),
            'amount': raw.get('amount'),
            'nseip_drop': raw.get('nseip_drop'),
            'dcd_web_cart': raw.get('dcd_web_cart'),
            'product_type': raw.get('product_type'),
            'bogo': raw.get('bogo'),
            'fpd_display_promo': raw.get('fpd_display_promo'),
            'on_menu': raw.get('on_menu'),
            'device_sales_type': raw.get('device_sales_type'),
            'activation_type': raw.get('activation_type'),
            'active_line_required': raw.get('active_line_required'),
            'maintain_soc': raw.get('maintain_soc'),
            'maintain_active_line': raw.get('maintain_active_line') or raw.get('crffc_maintainactivelinedev'),
            'limit_per_ban': raw.get('limit_per_ban'),
            'application_grace_period': raw.get('application_grace_period'),
            'trade_in_grace': raw.get('trade_in_grace'),
            'market_group': raw.get('market_group'),
            'store_group': raw.get('store_group'),
            'soc_grouping': raw.get('soc_grouping'),
            'account_type': raw.get('account_type'),
            'sales_application': raw.get('sales_application'),
            'device_status_group_id': raw.get('device_status_group_id'),
            'segment_name': raw.get('segment_name'),
            'orbit_link': raw.get('orbit_link'),
            'legal_link': raw.get('legal_link'),
            'c2_link': raw.get('c2_link'),
            **raw
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def list_orbit_ids(self, limit: int = 10) -> List[str]:
        """List orbit IDs from SQL Server."""
        engine = self._db.get_engine()
        if not engine:
            return []
        sql = text(f"SELECT TOP {int(limit)} orbit_id FROM {self.table} WHERE orbit_id IS NOT NULL")
        with engine.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [str(r[0]) for r in rows if r and r[0] is not None]

    def get_columns(self) -> List[str]:
        """Return SQL column names."""
        engine = self._db.get_engine()
        if not engine:
            return []
        sql = text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table"
        )
        if '.' in self.table:
            schema, table = self.table.split('.', 1)
        else:
            schema, table = 'dbo', self.table
        with engine.connect() as conn:
            rows = conn.execute(sql, {'schema': schema.strip('[]'), 'table': table.strip('[]')}).fetchall()
        return [r[0] for r in rows]

__all__ = ["OrbitDatabaseManager"]
