"""Centralized workflow utilities for promo code generation and orbit ingestion.

Responsibilities:
- Orbit-first lookup (raw intake vs existing promotions)
- Next sequential promo code generation with issued code tombstoning
- Creation of a promo from an orbit record (idempotent if already created)

This consolidates logic previously scattered across api/routes and data/storage so
endpoints remain thin and re-usable by future CLI/tasks.
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, Any
import re

logger = logging.getLogger(__name__)

from data.database import DatabaseManager
from data.orbit_database import OrbitDatabaseManager
from data.storage import PromoDataManager
from data.sku_group_tracking import (
    load_issued_sku_group_ids,
    record_issued_sku_group_id,
    next_sku_group_id_progressive,
)
from data.version_history import log_version_event

# Issued code tracking (reuse existing helper location if available)
try:
    from data.code_tracking import load_issued_codes, record_issued_code  # type: ignore
except Exception:  # fallback no-op definitions
    def load_issued_codes():  # type: ignore
        return set()
    def record_issued_code(code: str):  # type: ignore
        pass

CODE_PATTERN = re.compile(r'^[A-Z](\d{3,4})$')

class PromoCodeWorkflow:
    def __init__(self, data_manager: Optional[PromoDataManager] = None):
        self.db = DatabaseManager()  # For PAM database writes
        self.orbit_db = OrbitDatabaseManager()  # For Fabric/orbit data reads
        self.data_manager = data_manager or PromoDataManager()

    # ---------------- Orbit Lookup -----------------
    def orbit_lookup(self, orbit_id: str) -> Dict[str, Any]:
        """Return dict with keys: found(bool), table(str|None), existing_code(str|None).

        Order: raw orbit intake table -> promotions table.
        """
        oid = (orbit_id or '').strip()
        if not oid:
            return {'found': False, 'error': 'orbit_id required'}
        # Use orbit_db directly for Fabric data
        row = self.orbit_db.get_orbit_record(oid)
        if row and not row.get('_error'):
            # Not yet created as promo (no code)
            return {'found': True, 'table': 'orbit', 'existing_code': None, 'orbit': row}
        # Check promotions for existing assignment
        for rec in self.db.get_all_promotions_unified():
            if str(rec.get('orbit_id','')) == oid:
                return {'found': True, 'table': 'promotions', 'existing_code': rec.get('code'), 'orbit': rec}
        return {'found': False}

    # --------------- Code Generation ----------------
    def generate_next_code(self) -> str:
        issued = load_issued_codes()
        # Determine current max via DB helper if present
        highest = self.db.get_highest_sequential_promo_code() or 'R000'
        m = re.match(r'^([A-Z])(\d{3,4})$', highest.upper())
        if not m:
            letter = 'R'; num = 1
        else:
            letter = m.group(1)
            num = int(m.group(2)) + 1
            if num > 9999:
                if letter == 'Z':
                    raise RuntimeError('Exhausted promo code namespace')
                letter = chr(ord(letter)+1)
                num = 1
        while True:
            width = 3 if num <= 999 else 4
            candidate = f"{letter}{num:0{width}d}"
            if candidate not in issued:
                record_issued_code(candidate)
                return candidate
            num += 1

    # --------------- Creation -----------------------
    def create_from_orbit(self, orbit_id: str, execution_type: str = 'RDC', user: str = 'System', config: str = '') -> Dict[str, Any]:
        """Ingest orbit record and create promo if not already present.

        Returns success False with existing_code if already created.
        """
        oid = (orbit_id or '').strip()
        if not oid:
            return {'success': False, 'error': 'orbit_id required'}
        # Fast duplicate check (avoid scanning all promos) using parameterized SQL
        try:
            sql = f"SELECT code FROM {self.db.source_table} WHERE orbit_id = :oid"
            df = self.db.get_dataframe(sql, {'oid': oid})
            if not df.empty:
                return {'success': False, 'error': 'Orbit already assigned', 'existing_code': df.iloc[0]['code']}
        except Exception:
            # Fall back to existing unified scan only if direct query fails
            lookup_scan = self.orbit_lookup(oid)
            if lookup_scan.get('existing_code'):
                return {'success': False, 'error': 'Orbit already assigned', 'existing_code': lookup_scan['existing_code']}
        # Lookup raw orbit (intake) row
        raw_lookup = self.orbit_lookup(oid)
        if not raw_lookup.get('found'):
            return {'success': False, 'error': f'Orbit {oid} not found'}
        if raw_lookup.get('existing_code'):
            return {'success': False, 'error': 'Orbit already assigned', 'existing_code': raw_lookup['existing_code']}
        # Obtain full orbit row (use orbit_db directly)
        full_row = self.orbit_db.get_orbit_record(oid)
        if not full_row or full_row.get('_error'):
            return {'success': False, 'error': f'Orbit {oid} not found'}
        new_code = self.generate_next_code()
        cfg = (config or '').lower()
        # Allocate next sku_group_id (always generate regardless of orbit row value)
        try:
            existing_db_ids = set(self.db.get_all_sku_group_ids())
        except Exception:
            existing_db_ids = set()
        existing_all = existing_db_ids | load_issued_sku_group_ids()
        try:
            allocated_sku_group_id = next_sku_group_id_progressive(existing_all)
        except Exception as alloc_err:
            return {'success': False, 'error': f'SKU group ID allocation failed: {alloc_err}'}
        # Core insertion column mapping (expand to reduce null columns). Only include keys with non-None values.
        # Defaults pulled from orbit row; will be overridden by config preset
        from promo.config_presets import get_config_preset
        
        # Get preset overrides for the selected configuration
        preset_overrides = get_config_preset(cfg) if cfg else {}
        logger.debug("[WORKFLOW] Config: '%s', Preset overrides: %s", cfg, preset_overrides)

        candidate_fields = {
            'code': new_code,
            'orbit_id': oid,
            # Map from Fabric fields (already transformed by orbit_database.py)
            'initiative_name': full_row.get('initiative_name'),  # From cat_initiativename
            'description': full_row.get('description'),  # From cat_description
            'bill_facing_name': full_row.get('bill_facing_name'),  # From cat_billname
            # Owner: Use promo_owner from ORBIT if available, otherwise use current SSO user
            'Owner': full_row.get('promo_owner') or full_row.get('Owner') or user,
            'promo_start_date': full_row.get('promo_start_date') or full_row.get('promo_start_date'),
            'promo_end_date': full_row.get('promo_end_date'),
            'comm_end_date': full_row.get('comm_end_date'),
            'application_grace_period': full_row.get('application_grace_period'),
            'device_sales_type': full_row.get('device_sales_type'),
            'activation_type': full_row.get('activation_type'),
            'active_line_required': full_row.get('active_line_required'),
            'maintain_soc': full_row.get('maintain_soc'),
            'limit_per_ban': full_row.get('limit_per_ban'),
            'account_type': full_row.get('account_type'),
            'sales_application': full_row.get('sales_application'),
            'market_group': full_row.get('market_group'),
            'store_group': full_row.get('store_group'),
            'sku_group_id': allocated_sku_group_id,
            'device_status_group_id': full_row.get('device_status_group_id'),
            'soc_grouping': full_row.get('soc_grouping'),
            'discount': full_row.get('discount'),
            'amount': full_row.get('amount'),
            'nseip_drop': full_row.get('nseip_drop'),
            'dcd_web_cart': full_row.get('dcd_web_cart'),
            'product_type': full_row.get('product_type'),
            'bogo': full_row.get('bogo'),
            'fpd_display_promo': full_row.get('fpd_display_promo'),
            'on_menu': full_row.get('on_menu'),
            'Desired_Execution': execution_type,
            'trade_in_grace': full_row.get('trade_in_grace'),
        }
        
        # Apply preset overrides AFTER building candidate_fields (preset values take precedence)
        if preset_overrides:
            logger.debug("[WORKFLOW] Applying preset overrides to candidate_fields")
            for key, value in preset_overrides.items():
                candidate_fields[key] = value
                logger.debug("[WORKFLOW] Override: %s = %s", key, value)
        
        insertion = {k:v for k,v in candidate_fields.items() if v is not None}
        logger.debug("[WORKFLOW] Final insertion fields: %s", list(insertion.keys()))
        ok = self.db.insert_promo_record(insertion)
        if not ok:
            return {'success': False, 'error': 'Insert failed', 'attempted_fields': list(insertion.keys())}
        # Persist sku_group_id tombstone (best effort)
        try:
            record_issued_sku_group_id(allocated_sku_group_id)
        except Exception:
            pass
        created_snapshot = {
            'orbit_id': oid,
            'promo_code': new_code,
            'promo_owner': insertion.get('Owner') or user,
            'promo_type': execution_type
        }
        log_version_event(
            promo_code=new_code,
            promo_id=new_code,
            orbit_id=oid,
            promo_owner=created_snapshot.get('promo_owner'),
            promo_type=created_snapshot.get('promo_type'),
            event_type='created',
            actor=user,
            source='create_from_orbit',
            created_snapshot=created_snapshot
        )
        db_record = self.db.get_promo_by_code(new_code) or {}
        payload = self.db.convert_db_record_to_json_format(db_record)
        payload['success'] = True
        return payload

__all__ = ['PromoCodeWorkflow']
