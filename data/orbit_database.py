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
        self.table = os.getenv('ORBIT_TABLE', '[PAM].[OrbitPromoExtract_stg]')
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
                    sql = f"SELECT TOP 1 * FROM {self.table} WHERE orbit_id = ?"
                    cursor.execute(sql, (oid,))
                    row = cursor.fetchone()
                    if row:
                        col_names = [d[0] for d in getattr(cursor, 'description', [])]
                        raw = dict(zip(col_names, row)) if col_names else {}
                        mapped = {
                            'Owner': raw.get('Owner') or raw.get('owner') or raw.get('promo_owner'),
                            'promo_owner': raw.get('promo_owner') or raw.get('Owner') or raw.get('owner'),
                            'bill_facing_name': raw.get('bill_facing_name') or raw.get('bill facing name') or raw.get('Bill_Facing_Name'),
                            'orbit_id': raw.get('orbit_id') or raw.get('cat_gtmentryid') or raw.get('cat_legacygtmentryid'),
                            # staging table stores cat_initiativename in 'description'; cat_description holds the actual description
                            'initiative_name': raw.get('initiative_name') or raw.get('initiative name') or raw.get('description'),
                            'description': raw.get('cat_description') or raw.get('description'),
                            'promo_start_date': raw.get('promo_start_date') or raw.get('promo_srart_date') or raw.get('promo_start') or raw.get('start_date'),
                            'promo_end_date': raw.get('promo_end_date') or raw.get('end_date'),
                            'maintain_active_line': raw.get('maintain_active_line') or raw.get('crffc_maintainactivelinedev'),
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
            'bill_facing_name': raw.get('bill_facing_name') or raw.get('bill facing name') or raw.get('Bill_Facing_Name'),
            # staging table: cat_initiativename was inserted into 'description'; cat_description holds the actual description text
            'initiative_name': raw.get('initiative_name') or raw.get('initiative name') or raw.get('description'),
            'orbit_id': raw.get('orbit_id') or raw.get('cat_gtmentryid') or raw.get('cat_legacygtmentryid'),
            'description': raw.get('cat_description') or raw.get('description'),
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

    def get_orbit_dates_map(self, orbit_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Bulk fetch orbit start/end dates keyed by orbit_id.

        Uses chunked IN queries to avoid one-query-per-orbit bottlenecks.
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

        def _fetch_chunk(conn, ids_chunk: List[str], start_col_expr: str):
            params = {f'oid{i}': oid for i, oid in enumerate(ids_chunk)}
            placeholders = ', '.join(f":oid{i}" for i in range(len(ids_chunk)))
            sql = text(
                f"SELECT CAST(orbit_id AS NVARCHAR(255)) AS orbit_id, "
                f"{start_col_expr} AS promo_start_date, "
                f"promo_end_date "
                f"FROM {self.table} "
                f"WHERE CAST(orbit_id AS NVARCHAR(255)) IN ({placeholders})"
            )
            return conn.execute(sql, params).mappings().all()

        with engine.connect() as conn:
            for i in range(0, len(cleaned_ids), chunk_size):
                chunk = cleaned_ids[i:i + chunk_size]
                rows = []
                try:
                    rows = _fetch_chunk(conn, chunk, 'promo_start_date')
                except Exception:
                    try:
                        rows = _fetch_chunk(conn, chunk, 'promo_srart_date')
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
