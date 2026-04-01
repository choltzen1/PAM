"""Orbit DB manager – queries live ORBIT data from SQL Server staging table.

Priority order:
  1. SQL Server staging table [PAM].[OrbitPromoExtract_stg] (primary – same
     server PAM already connects to, no OAuth/Fabric overhead)
  2. Microsoft Fabric Data Warehouse (optional fallback when USE_FABRIC_ORBIT=true)
  3. Legacy SQL Server table rdc.pam_orbit_data (last-resort fallback)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import text

from .database import DatabaseManager

logger = logging.getLogger(__name__)


class OrbitDatabaseManager:
    def __init__(self):
        try:
            env_path = find_dotenv()
            if env_path:
                load_dotenv(env_path)
        except Exception:
            pass

        self._last_error = None
        self.table = os.getenv('ORBIT_TABLE', 'rdc.pam_orbit_data')
        self.staging_table = os.getenv(
            'ORBIT_STAGING_TABLE',
            os.getenv('ORBIT_STG_TABLE', '[PAM].[OrbitPromoExtract_stg]'),
        )
        self._orbit_stg_table = self.staging_table
        self._db = DatabaseManager()
        flag = (os.getenv('USE_FABRIC_ORBIT') or '').strip().lower()
        self._use_fabric = flag in {'true', '1', 'yes'}

        logger.info(
            f"OrbitDatabaseManager: staging={self.staging_table}, "
            f"fabric_fallback={'ON' if self._use_fabric else 'OFF'}"
        )

    def _connect(self):
        """Legacy-compatible raw connection helper used by older test paths."""
        engine = self._db.get_engine()
        return engine.raw_connection() if engine is not None else None

    def _stg_lookup(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        engine = self._db.get_engine()
        if not engine:
            return None

        oid = str(orbit_id or '').strip()
        if not oid:
            return None

        try:
            sql = text(
                f"SELECT TOP 1 * FROM {self.staging_table} "
                f"WHERE CAST(orbit_id AS NVARCHAR(255)) = :oid"
            )
            with engine.connect() as conn:
                row = conn.execute(sql, {'oid': oid}).mappings().first()
            return dict(row) if row else None
        except Exception as e:
            self._last_error = str(e)
            logger.warning(f"Staging lookup failed for {oid}: {e}")
            return None

    def _fabric_lookup(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        try:
            from data.fabric_database import fabric_db

            logger.info(f"Fabric lookup: searching GTM ID {orbit_id}")
            result = fabric_db.search_by_gtm_id(orbit_id)
            if result:
                self.table = fabric_db.table
                return result
        except Exception as e:
            logger.warning(f"Fabric lookup failed for {orbit_id}: {e}")
        return None

    def get_orbit_record(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Get orbit record using staging first, then optional Fabric, then legacy SQL."""
        oid = str(orbit_id or '').strip()
        if not oid or oid.lower() in {'null', 'none', 'nan'}:
            return {'_error': 'orbit_id required'}

        staging_row = self.get_orbit_record_from_staging(oid)
        if staging_row and not staging_row.get('_error'):
            self.table = self.staging_table
            return staging_row

        if self._use_fabric:
            fabric_row = self._fabric_lookup(oid)
            if fabric_row:
                return self._normalize_fabric_row(fabric_row, oid)

        engine = self._db.get_engine()
        if not engine:
            return {'_error': 'Database connection unavailable – cannot look up Orbit data'}

        try:
            sql = text(
                f"SELECT TOP 1 * FROM {self.table} "
                f"WHERE CAST(orbit_id AS NVARCHAR(255)) = :oid"
            )
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
            **raw,
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def get_orbit_record_from_staging(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Get orbit record from [PAM].[OrbitPromoExtract_stg] by orbit_id."""
        oid = str(orbit_id or '').strip()
        if not oid or oid.lower() in {'null', 'none', 'nan'}:
            return {'_error': 'orbit_id required'}

        raw = self._stg_lookup(oid)
        if not raw:
            return {'_error': 'not found'}

        lower_map = {str(key).lower(): key for key in raw.keys()}

        def ci(key: str):
            if key in raw:
                return raw[key]
            actual = lower_map.get(key.lower())
            return raw.get(actual) if actual else None

        mapped = {
            'Owner': ci('Owner') or ci('owner'),
            'promo_owner': ci('Owner') or ci('owner'),
            'bill_facing_name': ci('bill_facing_name'),
            'orbit_id': ci('orbit_id'),
            'initiative_name': ci('initiative_name'),
            'description': ci('cat_description') or ci('description'),
            'promo_notes': ci('promo_notes'),
            'promo_start_date': ci('promo_start_date'),
            'promo_end_date': ci('promo_end_date'),
            'comm_end_date': ci('comm_end_date'),
            'discount': ci('discount'),
            'amount': ci('amount'),
            'nseip_drop': ci('nseip_drop'),
            'dcd_web_cart': ci('dcd_web_cart'),
            'product_type': ci('product_type'),
            'bogo': ci('bogo'),
            'fpd_display_promo': ci('fpd_display_promo'),
            'on_menu': ci('on_menu'),
            'market_group': ci('market_group'),
            'store_group': ci('store_group'),
            'device_sales_type': ci('device_sales_type'),
            'activation_type': ci('activation_type'),
            'active_line_required': ci('active_line_required'),
            'maintain_soc': ci('maintain_soc'),
            'maintain_active_line': ci('maintain_active_line') or ci('crffc_maintainactivelinedev'),
            'limit_per_ban': ci('limit_per_ban'),
            'application_grace_period': ci('application_grace_period'),
            'trade_in_grace': ci('trade_in_grace'),
            'soc_grouping': ci('soc_grouping'),
            'account_type': ci('account_type'),
            'sales_application': ci('sales_application'),
            'device_status_group_id': ci('device_status_group_id'),
            'segment_name': ci('segment_name'),
            'Desired_Execution': ci('Desired_Execution'),
            'clawback_indicator': ci('clawback_indicator'),
            'Broken_Trade': ci('Broken_Trade'),
            'Anticipated_volume_take_rates_total': ci('Anticipated_volume_take_rates_total'),
            'Status': ci('Status'),
            'crffc_eligibletradeindevices': ci('crffc_eligibletradeindevices'),
            'cat_lobchannelhorizontalname': ci('cat_lobchannelhorizontalname'),
            'cat_additionaleligibilityrequirementsname': ci('cat_additionaleligibilityrequirementsname'),
            'cat_eligibledevices': ci('cat_eligibledevices'),
            'cat_channelsname': ci('cat_channelsname'),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def get_orbit_dates_map(self, orbit_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Bulk fetch orbit start/end dates keyed by orbit_id from staging."""
        cleaned_ids: List[str] = []
        seen = set()
        for orbit_id in orbit_ids or []:
            oid = str(orbit_id or '').strip()
            if not oid or oid.lower() in {'null', 'none', 'nan'} or oid in seen:
                continue
            seen.add(oid)
            cleaned_ids.append(oid)

        if not cleaned_ids:
            return {}

        engine = self._db.get_engine()
        if not engine:
            return {}

        out: Dict[str, Dict[str, Any]] = {}
        chunk_size = 500
        with engine.connect() as conn:
            for index in range(0, len(cleaned_ids), chunk_size):
                chunk = cleaned_ids[index:index + chunk_size]
                params = {f'oid{i}': oid for i, oid in enumerate(chunk)}
                placeholders = ', '.join(f":oid{i}" for i in range(len(chunk)))
                sql = text(
                    f"SELECT CAST(orbit_id AS NVARCHAR(255)) AS orbit_id, "
                    f"promo_start_date, promo_end_date "
                    f"FROM {self.staging_table} "
                    f"WHERE CAST(orbit_id AS NVARCHAR(255)) IN ({placeholders})"
                )
                try:
                    rows = conn.execute(sql, params).mappings().all()
                except Exception:
                    continue

                for row in rows:
                    oid = str(row.get('orbit_id') or '').strip()
                    if not oid:
                        continue
                    out[oid] = {
                        'orbit_start_date': row.get('promo_start_date', '') or '',
                        'orbit_end_date': row.get('promo_end_date', '') or '',
                    }

        return out

    def _normalize_fabric_row(self, raw: Dict[str, Any], orbit_id: str) -> Dict[str, Any]:
        mapped = {
            'Owner': raw.get('crffc_productownername') or raw.get('crffc_businessownername') or raw.get('Owner'),
            'promo_owner': raw.get('crffc_productownername') or raw.get('crffc_businessownername') or raw.get('promo_owner'),
            'promo_owner_email': raw.get('crffc_promoowneremail') or raw.get('promo_owner_email'),
            'bill_facing_name': raw.get('cat_billname') or raw.get('bill_facing_name'),
            'initiative_name': raw.get('cat_initiativename') or raw.get('initiative_name'),
            'orbit_id': str(raw.get('cat_gtmentryid') or raw.get('cat_legacygtmentryid') or orbit_id),
            'description': raw.get('cat_description') or raw.get('description'),
            'promo_notes': raw.get('cat_notes') or raw.get('promo_notes'),
            'promo_start_date': raw.get('cat_startdate') or raw.get('cat_requestedlaunchdate') or raw.get('promo_start_date'),
            'promo_end_date': raw.get('cat_enddate') or raw.get('promo_end_date'),
            'comm_end_date': raw.get('cat_commenddate') or raw.get('comm_end_date'),
            'discount': raw.get('cat_discount') or raw.get('discount'),
            'amount': raw.get('cat_amount') or raw.get('crffc_amount') or raw.get('amount'),
            'nseip_drop': raw.get('cat_nseipdrop') or raw.get('nseip_drop'),
            'dcd_web_cart': raw.get('cat_dcdwebcart') or raw.get('dcd_web_cart'),
            'product_type': raw.get('cat_producttypename') or raw.get('product_type'),
            'bogo': raw.get('cat_bogo') or raw.get('bogo'),
            'fpd_display_promo': raw.get('cat_fpddisplaypromo') or raw.get('fpd_display_promo'),
            'on_menu': raw.get('cat_onmenu') or raw.get('on_menu'),
            'device_sales_type': raw.get('cat_devicesalestypename') or raw.get('device_sales_type'),
            'activation_type': raw.get('cat_activationtypename') or raw.get('activation_type'),
            'active_line_required': raw.get('cat_activelinerequired') or raw.get('active_line_required'),
            'maintain_soc': raw.get('cat_maintainsoc') or raw.get('maintain_soc'),
            'maintain_active_line': raw.get('crffc_maintainactivelinedev') or raw.get('maintain_active_line'),
            'limit_per_ban': raw.get('cat_limitperban') or raw.get('limit_per_ban'),
            'application_grace_period': raw.get('cat_applicationgraceperiod') or raw.get('application_grace_period'),
            'trade_in_grace': raw.get('cat_tradeingraceperiod') or raw.get('trade_in_grace'),
            'market_group': raw.get('cat_marketgroupname') or raw.get('market_group'),
            'store_group': raw.get('cat_storegroupname') or raw.get('store_group'),
            'soc_grouping': raw.get('cat_socgrouping') or raw.get('soc_grouping'),
            'account_type': raw.get('cat_accounttypename') or raw.get('account_type'),
            'sales_application': raw.get('cat_salesapplicationname') or raw.get('sales_application'),
            'device_status_group_id': raw.get('cat_devicestatusgroupid') or raw.get('device_status_group_id'),
            'segment_name': raw.get('cat_segmentname') or raw.get('segment_name'),
            'orbit_link': raw.get('cat_orbitlink') or raw.get('orbit_link'),
            'legal_link': raw.get('cat_legallink') or raw.get('legal_link'),
            'c2_link': raw.get('cat_c2link') or raw.get('c2_link'),
            **raw,
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def list_orbit_ids(self, limit: int = 10) -> List[str]:
        engine = self._db.get_engine()
        if not engine:
            return []
        sql = text(f"SELECT TOP {int(limit)} orbit_id FROM {self.table} WHERE orbit_id IS NOT NULL")
        with engine.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [str(row[0]) for row in rows if row and row[0] is not None]

    def get_columns(self) -> List[str]:
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
            rows = conn.execute(
                sql,
                {'schema': schema.strip('[]'), 'table': table.strip('[]')},
            ).fetchall()
        return [row[0] for row in rows]


__all__ = ['OrbitDatabaseManager']
