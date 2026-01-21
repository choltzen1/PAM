"""Orbit DB manager - Microsoft Fabric ONLY.

Provides read-only access to orbit data from Microsoft Fabric Data Warehouse.
No fallback to local SQL Server or fake data - if Fabric fails, the app fails.
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
        
        # ALWAYS use Fabric - no fallback
        from .fabric_database import FabricDatabaseManager
        self._fabric_manager = FabricDatabaseManager()
        self._last_error = None
        self.table = 'dbo.ORBIT_Reporting_Table'  # Fabric table name

    def get_orbit_record(self, orbit_id: str) -> Optional[Dict[str, Any]]:
        """Get orbit record from Fabric by GTM ID (GUID or legacy numeric ID)."""
        result = self._fabric_manager.search_by_gtm_id(orbit_id)
        if result:
            # Map Fabric fields to expected PAM format
            # Core fields
            # Owner: Use promo owner from Promotion_Details JOIN only (no fallback to business owner)
            mapped = {
                'Owner': result.get('crffc_promoowner'),
                'promo_owner': result.get('crffc_promoowner'),
                'promo_owner_email': result.get('crffc_promoowneremail'),
                'business_owner': result.get('crffc_businessownername'),
                'sponsoring_vp': result.get('crffc_sponsoringvpname'),
                'product_owner': result.get('crffc_productownerfullname'),
                'bill_facing_name': result.get('cat_billname'),
                'initiative_name': result.get('cat_initiativename'),
                'orbit_id': result.get('cat_gtmentryid') or result.get('cat_legacygtmentryid'),
                'description': result.get('cat_description'),
                'promo_notes': result.get('cat_productnotes'),
                # Use cat_startdate if available, otherwise fall back to cat_requestedlaunchdate
                'promo_start_date': result.get('cat_startdate') or result.get('cat_requestedlaunchdate'),
                'promo_end_date': result.get('cat_enddate'),
                'comm_end_date': result.get('cat_commenddate'),
                
                # Pricing / offer terms
                'discount': result.get('cat_discount'),
                'amount': result.get('cat_amount') or result.get('crffc_amount'),
                'nseip_drop': result.get('cat_nseipdrop'),
                'dcd_web_cart': result.get('cat_dcdwebcart'),
                'product_type': result.get('cat_producttypename'),
                'bogo': result.get('cat_bogo'),
                'fpd_display_promo': result.get('cat_fpddisplaypromo'),
                'on_menu': result.get('cat_onmenu'),
                
                # Execution & eligibility
                'device_sales_type': result.get('cat_devicesalestypename'),
                'activation_type': result.get('cat_activationtypename'),
                'active_line_required': result.get('cat_activelinerequired'),
                'maintain_soc': result.get('cat_maintainsoc'),
                'maintain_active_line': result.get('crffc_maintainactivelinedev'),
                'crffc_maintainactivelinedev': result.get('crffc_maintainactivelinedev'),
                'limit_per_ban': result.get('cat_limitperban'),
                'application_grace_period': result.get('cat_applicationgraceperiod'),
                'trade_in_grace': result.get('cat_tradeingraceperiod'),
                
                # Groupings / segmentation
                'market_group': result.get('cat_marketgroupname'),
                'store_group': result.get('cat_storegroupname'),
                'soc_grouping': result.get('cat_socgrouping'),
                'account_type': result.get('cat_accounttypename'),
                'sales_application': result.get('cat_salesapplicationname'),
                'device_status_group_id': result.get('cat_devicestatusgroupid'),
                'segment_name': result.get('CustomerSegmentsOptionLabels.OptionValues'),
                
                # Links
                'orbit_link': result.get('cat_orbitlink'),
                'legal_link': result.get('cat_legallink'),
                'c2_link': result.get('crffc_c2link'),
                
                # Additional Fabric-specific fields
                'cat_lobchannelhorizontalname': result.get('cat_lobchannelhorizontal_display'),
                'cat_additionaleligibilityrequirementsname': result.get('cat_additionaleligibilityrequirementsname'),
                'cat_eligibledevices': result.get('cat_eligibledevices'),
                'cat_channelsname': result.get('cat_channelsname'),
                'crffc_eligibletradeindevices': result.get('crffc_eligibletradeindevices'),
                
                # Include all raw Fabric fields as well (for debugging/completeness)
                **result
            }
            return {k: v for k, v in mapped.items() if v is not None}
        
        return {'_error': 'not found'}

    def list_orbit_ids(self, limit: int = 10) -> List[str]:
        """List orbit IDs from Fabric."""
        promotions = self._fabric_manager.get_all_promotions(limit=limit)
        return [p.get('cat_gtmentryid', '') for p in promotions if p.get('cat_gtmentryid')]

    def get_columns(self) -> List[str]:
        """Return Fabric column names."""
        return ['cat_initiativename', 'crffc_promocodeid', 'cat_gtmentryid', 'cat_startdate', 
                'cat_enddate', 'cat_billname', 'cat_description', 'modifiedon']

__all__ = ["OrbitDatabaseManager"]
