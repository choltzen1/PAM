"""Orbit DB manager – delegates to Fabric or falls back to SQL Server.

When USE_FABRIC_ORBIT=true (default), orbit look-ups query the Microsoft
Fabric Data Warehouse via FabricDatabaseManager.  If Fabric is unavailable
or the flag is explicitly set to false, the manager falls back to the local
SQL Server table (rdc.pam_orbit_data).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import logging
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import text
from .database import DatabaseManager

logger = logging.getLogger(__name__)


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

        # Fabric toggle – defaults to True when Fabric env vars are present
        flag = os.getenv('USE_FABRIC_ORBIT', '').strip().lower()
        if flag in ('true', '1', 'yes'):
            self._use_fabric = True
        elif flag in ('false', '0', 'no'):
            self._use_fabric = False
        else:
            # Auto-detect: enable if the required Fabric vars exist
            self._use_fabric = bool(
                os.getenv('FABRIC_SERVER') and os.getenv('FABRIC_DATABASE')
            )

        if self._use_fabric:
            logger.info("OrbitDatabaseManager: Fabric delegation ENABLED")
        else:
            logger.info("OrbitDatabaseManager: using local SQL Server only")

    # ── Fabric delegation ───────────────────────────────────────────
    def _fabric_lookup(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Try to look up orbit_id via FabricDatabaseManager.search_by_gtm_id.
        Returns a raw dict on success, or None if Fabric is unavailable / not found.
        """
        try:
            from data.fabric_database import fabric_db
            logger.info(f"Fabric lookup: searching GTM ID {orbit_id}")
            result = fabric_db.search_by_gtm_id(orbit_id)
            if result:
                logger.info(f"Fabric lookup: FOUND orbit {orbit_id}")
                # Store the table name so callers see the source
                self.table = fabric_db.table
                return result
            else:
                logger.info(f"Fabric lookup: orbit {orbit_id} not found in Fabric")
                return None
        except Exception as e:
            logger.warning(f"Fabric lookup failed for {orbit_id}: {e}")
            return None

    def get_orbit_record(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Get orbit record – tries Fabric first (if enabled), then SQL Server."""
        oid = (orbit_id or '').strip()
        if not oid:
            return {'_error': 'orbit_id required'}

        # ── Try Fabric first ───────────────────────────────────────
        if self._use_fabric:
            fabric_row = self._fabric_lookup(oid)
            if fabric_row:
                return self._normalize_fabric_row(fabric_row, oid)
            # Fabric returned nothing – fall through to SQL Server
            logger.info(f"Fabric miss for {oid}, falling back to SQL Server")

        # ── SQL Server fallback ────────────────────────────────────
        engine = self._db.get_engine()
        if not engine:
            return {'_error': 'Database connection unavailable – cannot look up Orbit data'}

        try:
            sql = text(f"SELECT TOP 1 * FROM {self.table} WHERE CAST(orbit_id AS VARCHAR(50)) = :oid")
            row = None
            with engine.connect() as conn:
                row = conn.execute(sql, {'oid': oid}).mappings().first()
                if not row and oid.isdigit():
                    row = conn.execute(sql, {'oid': str(int(oid))}).mappings().first()
        except Exception as e:
            self._last_error = str(e)
            return {'_error': f'Database query failed: {str(e)[:150]}'}

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

    def _normalize_fabric_row(self, raw: Dict[str, Any], orbit_id: str) -> Dict[str, Any]:
        """Map Fabric column names (cat_*, crffc_*) to the normalized schema
        that the rest of PAM expects, mirroring the SQL Server mapping above."""
        mapped = {
            'Owner': raw.get('cat_businessowner') or raw.get('crffc_promoowner') or raw.get('Owner'),
            'promo_owner': raw.get('crffc_promoowner') or raw.get('cat_businessowner'),
            'promo_owner_email': raw.get('crffc_promoowneremail') or raw.get('promo_owner_email'),
            'bill_facing_name': raw.get('cat_billname') or raw.get('bill_facing_name'),
            'initiative_name': raw.get('cat_initiativename') or raw.get('initiative_name'),
            'orbit_id': str(raw.get('cat_legacygtmentryid') or raw.get('cat_gtmentryid') or orbit_id),
            'description': raw.get('cat_description') or raw.get('description'),
            'promo_notes': raw.get('promo_notes') or raw.get('cat_notes'),
            'promo_start_date': raw.get('cat_startdate') or raw.get('promo_start_date'),
            'promo_end_date': raw.get('cat_enddate') or raw.get('promo_end_date'),
            'comm_end_date': raw.get('comm_end_date'),
            'discount': raw.get('discount') or raw.get('cat_discountamount'),
            'amount': raw.get('amount') or raw.get('cat_totalofferspend'),
            'nseip_drop': raw.get('nseip_drop'),
            'dcd_web_cart': raw.get('dcd_web_cart'),
            'product_type': raw.get('product_type') or raw.get('cat_producttype'),
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
            **raw  # preserve all raw Fabric fields too
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
