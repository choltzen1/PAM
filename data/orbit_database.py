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
        # ORBIT_TABLE: used for dates enrichment (date-mismatch page)
        self.table = os.getenv('ORBIT_TABLE', 'rdc.pam_orbit_data')
        # ORBIT_STAGING_TABLE: used for "Get Promo Code" orbit lookup
        self.staging_table = os.getenv('ORBIT_STAGING_TABLE', '[PAM].[OrbitPromoExtract_stg]')
        self._db = DatabaseManager()

    def _connect(self):
        """Legacy-compatible raw connection helper used by compatibility tests."""
        engine = self._db.get_engine()
        return engine.raw_connection() if engine is not None else None

    def get_orbit_record(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Get orbit record from SQL Server by orbit_id."""
        oid = str(orbit_id or '').strip()
        if not oid or oid.lower() in {'null', 'none', 'nan'}:
            return {'_error': 'orbit_id required'}

        # Legacy cursor path (supports monkeypatching _connect in tests)
        try:
            conn = self._connect()
            if conn is not None and hasattr(conn, 'cursor'):
                try:
                    cursor = conn.cursor()
                    sql = (
                        f"SELECT TOP 1 Owner, bill_facing_name, orbit_id, description, "
                        f"promo_srart_date AS promo_start_date, promo_end_date "
                        f"FROM {self.table} WHERE orbit_id = ?"
                    )
                    cursor.execute(sql, (oid,))
                    row = cursor.fetchone()
                    if row:
                        col_names = [d[0] for d in getattr(cursor, 'description', [])]
                        raw = dict(zip(col_names, row)) if col_names else {}
                        mapped = {
                            'Owner': raw.get('Owner') or raw.get('owner') or raw.get('promo_owner'),
                            'promo_owner': raw.get('promo_owner') or raw.get('Owner') or raw.get('owner'),
                            'bill_facing_name': raw.get('bill facing name') or raw.get('bill_facing_name') or raw.get('Bill_Facing_Name'),
                            'orbit_id': raw.get('orbit_id') or raw.get('cat_gtmentryid') or raw.get('cat_legacygtmentryid'),
                            'description': raw.get('description') or raw.get('cat_description'),
                            'promo_start_date': raw.get('promo_start_date') or raw.get('promo_srart_date') or raw.get('promo_start') or raw.get('start_date'),
                            'promo_end_date': raw.get('promo_end_date') or raw.get('end_date'),
                            **raw,
                        }
                        return {k: v for k, v in mapped.items() if v is not None}
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
        except Exception:
            pass

        engine = self._db.get_engine()
        if not engine:
            return {'_error': 'db connection failed'}

        sql = text(f"SELECT TOP 1 * FROM {self.table} WHERE CAST(orbit_id AS NVARCHAR(255)) = :oid")
        row = None
        with engine.connect() as conn:
            row = conn.execute(sql, {'oid': oid}).mappings().first()

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

    def get_orbit_record_from_staging(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Get orbit record from [PAM].[OrbitPromoExtract_stg] by orbit_id.

        The staging table is populated by ssms_job.py from Dataverse and has
        clean friendly column names, but differs from the old orbit table:
          - 'initiative_name' column stores cat_initiativename
          - 'cat_description' column stores the actual description text
          - 'promo_start_date' is spelled correctly (no typo)
          - 'crffc_maintainactivelinedev' stores maintain_active_line value
        """
        oid = str(orbit_id or '').strip()
        if not oid or oid.lower() in {'null', 'none', 'nan'}:
            return {'_error': 'orbit_id required'}

        engine = self._db.get_engine()
        if not engine:
            return {'_error': 'db connection failed'}

        sql = text(
            f"SELECT TOP 1 * FROM {self.staging_table} "
            f"WHERE CAST(orbit_id AS NVARCHAR(255)) = :oid"
        )
        with engine.connect() as conn:
            row = conn.execute(sql, {'oid': oid}).mappings().first()

        if not row:
            return {'_error': 'not found'}

        raw = dict(row)
        # Case-insensitive helper for column lookups (SQL Server may return mixed case)
        _lower_map = {str(k).lower(): k for k in raw.keys()}
        def _ci(key):
            """Case-insensitive get from raw dict."""
            if key in raw:
                return raw[key]
            actual = _lower_map.get(key.lower())
            return raw.get(actual) if actual else None
        # Staging table has 'description' column holding cat_initiativename,
        # and a separate 'cat_description' column for the actual description.
        # Map explicitly — no **raw spread to avoid overwrites.
        mapped = {
            'Owner': _ci('Owner') or _ci('owner'),
            'promo_owner': _ci('Owner') or _ci('owner'),
            'bill_facing_name': _ci('bill_facing_name'),
            'orbit_id': _ci('orbit_id'),
            'initiative_name': _ci('initiative_name'),
            'description': _ci('cat_description'),
            'promo_notes': _ci('promo_notes'),
            'promo_start_date': _ci('promo_start_date'),
            'promo_end_date': _ci('promo_end_date'),
            'comm_end_date': _ci('comm_end_date'),
            'discount': _ci('discount'),
            'amount': _ci('amount'),
            'nseip_drop': _ci('nseip_drop'),
            'dcd_web_cart': _ci('dcd_web_cart'),
            'product_type': _ci('product_type'),
            'bogo': _ci('bogo'),
            'fpd_display_promo': _ci('fpd_display_promo'),
            'on_menu': _ci('on_menu'),
            'market_group': _ci('market_group'),
            'store_group': _ci('store_group'),
            'device_sales_type': _ci('device_sales_type'),
            'activation_type': _ci('activation_type'),
            'active_line_required': _ci('active_line_required'),
            'maintain_soc': _ci('maintain_soc'),
            'maintain_active_line': _ci('crffc_maintainactivelinedev'),
            'limit_per_ban': _ci('limit_per_ban'),
            'application_grace_period': _ci('application_grace_period'),
            'soc_grouping': _ci('soc_grouping'),
            'account_type': _ci('account_type'),
            'sales_application': _ci('sales_application'),
            'device_status_group_id': _ci('device_status_group_id'),
            'Desired_Execution': _ci('Desired_Execution'),
            'clawback_indicator': _ci('clawback_indicator'),
            'Broken_Trade': _ci('Broken_Trade'),
            'Anticipated_volume_take_rates_total': _ci('Anticipated_volume_take_rates_total'),
            'Status': _ci('Status'),
            'crffc_eligibletradeindevices': _ci('crffc_eligibletradeindevices'),
            'cat_lobchannelhorizontalname': _ci('cat_lobchannelhorizontalname'),
            'cat_additionaleligibilityrequirementsname': _ci('cat_additionaleligibilityrequirementsname'),
            'cat_eligibledevices': _ci('cat_eligibledevices'),
            'cat_channelsname': _ci('cat_channelsname'),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def get_orbit_dates_map(self, orbit_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Bulk fetch orbit start/end dates keyed by orbit_id.

        Uses the staging table [PAM].[OrbitPromoExtract_stg] as the
        authoritative source for orbit data, with chunked IN queries.
        """
        cleaned_ids: List[str] = []
        seen = set()
        for orbit_id in orbit_ids or []:
            oid = str(orbit_id or '').strip()
            if not oid or oid.lower() in {'null', 'none', 'nan'}:
                continue
            if oid in seen:
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
            for i in range(0, len(cleaned_ids), chunk_size):
                chunk = cleaned_ids[i:i + chunk_size]
                params = {f'oid{i}': oid for i, oid in enumerate(chunk)}
                placeholders = ', '.join(f":oid{i}" for i in range(len(chunk)))
                sql = text(
                    f"SELECT CAST(orbit_id AS NVARCHAR(255)) AS orbit_id, "
                    f"promo_start_date, "
                    f"promo_end_date "
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
                        'orbit_end_date': row.get('promo_end_date', '') or ''
                    }

        return out

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
