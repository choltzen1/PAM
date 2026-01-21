#!/usr/bin/env python3
"""ORBIT to PAM Field Mapping Validation

This script:
1. Connects to Microsoft Fabric (ORBIT source)
2. Pulls sample data
3. Validates each field against PAM database requirements
4. Generates a detailed report showing data quality

Use this to PROVE data is valid and accurate for PAM.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# PAM destination fields and their Fabric source mappings
PAM_FIELD_MAPPINGS = {
    # Format: 'pam_field': {'fabric_columns': [...], 'required': bool, 'type': str, 'description': str}
    
    # ===== IDENTITY / DESCRIPTIVE =====
    'bill_facing_name': {
        'fabric_columns': ['cat_billname'],
        'required': True,
        'type': 'string',
        'max_length': 255,
        'description': 'Customer-facing bill name'
    },
    'initiative_name': {
        'fabric_columns': ['cat_initiativename'],
        'required': True,
        'type': 'string',
        'max_length': 500,
        'description': 'Promotion initiative name'
    },
    'description': {
        'fabric_columns': ['cat_description'],
        'required': False,
        'type': 'string',
        'max_length': 4000,
        'description': 'Promotion description'
    },
    'promo_notes': {
        'fabric_columns': ['cat_notes'],
        'required': False,
        'type': 'string',
        'max_length': 4000,
        'description': 'Additional notes'
    },
    'Owner': {
        'fabric_columns': ['crffc_productownername', 'crffc_businessownername'],
        'required': True,
        'type': 'string',
        'max_length': 255,
        'description': 'Product or Business Owner'
    },
    'orbit_id': {
        'fabric_columns': ['cat_gtmentryid', 'cat_legacygtmentryid'],
        'required': True,
        'type': 'string',
        'max_length': 50,
        'description': 'ORBIT GTM Entry ID'
    },
    
    # ===== DATES =====
    'promo_start_date': {
        'fabric_columns': ['cat_startdate', 'cat_requestedlaunchdate'],
        'required': True,
        'type': 'date',
        'description': 'Promotion start date'
    },
    'promo_end_date': {
        'fabric_columns': ['cat_enddate'],
        'required': False,
        'type': 'date',
        'description': 'Promotion end date'
    },
    'comm_end_date': {
        'fabric_columns': ['cat_commenddate'],
        'required': False,
        'type': 'date',
        'description': 'Communication end date'
    },
    
    # ===== PRICING / OFFER TERMS =====
    'discount': {
        'fabric_columns': ['cat_discount'],
        'required': False,
        'type': 'number',
        'description': 'Discount amount/percentage'
    },
    'amount': {
        'fabric_columns': ['cat_amount', 'crffc_amount'],
        'required': False,
        'type': 'number',
        'description': 'Promotion amount'
    },
    'product_type': {
        'fabric_columns': ['cat_producttypename'],
        'required': False,
        'type': 'string',
        'description': 'Product type classification'
    },
    'bogo': {
        'fabric_columns': ['cat_bogo'],
        'required': False,
        'type': 'boolean',
        'description': 'Buy One Get One indicator'
    },
    
    # ===== EXECUTION & ELIGIBILITY =====
    'device_sales_type': {
        'fabric_columns': ['cat_devicesalestypename'],
        'required': False,
        'type': 'string',
        'description': 'Type of device sale'
    },
    'activation_type': {
        'fabric_columns': ['cat_activationtypename'],
        'required': False,
        'type': 'string',
        'description': 'Type of activation required'
    },
    'active_line_required': {
        'fabric_columns': ['cat_activelinerequired'],
        'required': False,
        'type': 'boolean',
        'description': 'Whether active line is required'
    },
    'maintain_soc': {
        'fabric_columns': ['cat_maintainsoc'],
        'required': False,
        'type': 'boolean',
        'description': 'Maintain SOC requirement'
    },
    'maintain_active_line': {
        'fabric_columns': ['crffc_maintainactivelinedev'],
        'required': False,
        'type': 'boolean',
        'description': 'Maintain active line requirement'
    },
    'limit_per_ban': {
        'fabric_columns': ['cat_limitperban'],
        'required': False,
        'type': 'number',
        'description': 'Limit per billing account'
    },
    
    # ===== GROUPINGS / SEGMENTATION =====
    'market_group': {
        'fabric_columns': ['cat_marketgroupname'],
        'required': False,
        'type': 'string',
        'description': 'Market group classification'
    },
    'store_group': {
        'fabric_columns': ['cat_storegroupname'],
        'required': False,
        'type': 'string',
        'description': 'Store group classification'
    },
    'soc_grouping': {
        'fabric_columns': ['cat_socgrouping'],
        'required': False,
        'type': 'string',
        'description': 'SOC grouping'
    },
    'account_type': {
        'fabric_columns': ['cat_accounttypename'],
        'required': False,
        'type': 'string',
        'description': 'Account type'
    },
    'sales_application': {
        'fabric_columns': ['cat_salesapplicationname'],
        'required': False,
        'type': 'string',
        'description': 'Sales application'
    },
    'segment_name': {
        'fabric_columns': ['cat_segmentname'],
        'required': False,
        'type': 'string',
        'description': 'Customer segment'
    },
    
    # ===== LINKS =====
    'orbit_link': {
        'fabric_columns': ['cat_orbitlink'],
        'required': False,
        'type': 'url',
        'description': 'ORBIT URL link'
    },
    'legal_link': {
        'fabric_columns': ['cat_legallink'],
        'required': False,
        'type': 'url',
        'description': 'Legal documentation link'
    },
    'c2_link': {
        'fabric_columns': ['cat_c2link'],
        'required': False,
        'type': 'url',
        'description': 'C2 documentation link'
    },
    
    # ===== ADDITIONAL OWNERS =====
    'business_owner': {
        'fabric_columns': ['crffc_businessownername'],
        'required': False,
        'type': 'string',
        'description': 'Business owner name'
    },
    'sponsoring_vp': {
        'fabric_columns': ['crffc_sponsoringvpname'],
        'required': False,
        'type': 'string',
        'description': 'Sponsoring VP name'
    },
    'product_owner': {
        'fabric_columns': ['crffc_productownername'],
        'required': False,
        'type': 'string',
        'description': 'Product owner name'
    },
    
    # ===== CHANNELS =====
    'channels': {
        'fabric_columns': ['cat_channelsname'],
        'required': False,
        'type': 'string',
        'description': 'Distribution channels'
    },
    'lob_channel_horizontal': {
        'fabric_columns': ['cat_lobchannelhorizontalname'],
        'required': False,
        'type': 'string',
        'description': 'Line of business / channel horizontal'
    },
}


def validate_value(value: Any, field_config: Dict) -> Dict[str, Any]:
    """Validate a single value against field requirements."""
    result = {
        'value': value,
        'valid': True,
        'issues': []
    }
    
    # Check for null/empty on required fields
    if field_config.get('required') and (value is None or str(value).strip() == ''):
        result['valid'] = False
        result['issues'].append('Required field is empty')
        return result
    
    if value is None or str(value).strip() == '':
        return result  # Empty optional field is fine
    
    field_type = field_config.get('type', 'string')
    
    # Type-specific validation
    if field_type == 'string':
        max_len = field_config.get('max_length', 255)
        if len(str(value)) > max_len:
            result['issues'].append(f'Value exceeds max length {max_len}')
    
    elif field_type == 'date':
        if not isinstance(value, datetime):
            try:
                # Try to parse as date
                if isinstance(value, str):
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                result['issues'].append('Invalid date format')
    
    elif field_type == 'number':
        try:
            float(value)
        except (TypeError, ValueError):
            result['issues'].append('Invalid numeric value')
    
    elif field_type == 'boolean':
        if not isinstance(value, bool) and value not in [0, 1, '0', '1', 'true', 'false', 'True', 'False']:
            result['issues'].append('Invalid boolean value')
    
    elif field_type == 'url':
        if isinstance(value, str) and not value.startswith(('http://', 'https://')):
            result['issues'].append('Invalid URL format')
    
    if result['issues']:
        result['valid'] = False
    
    return result


def run_validation():
    """Run full validation of Fabric data against PAM requirements."""
    
    print("=" * 100)
    print("ORBIT TO PAM DATA VALIDATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    print()
    
    # Import Fabric manager
    from data.fabric_database import FabricDatabaseManager
    fabric = FabricDatabaseManager()
    
    # Test connection
    print("🔌 Connecting to Microsoft Fabric...")
    if not fabric.test_connection():
        print("❌ Failed to connect to Fabric!")
        print("   Check your credentials and network connection.")
        return
    print("✅ Connected to Fabric successfully")
    print()
    
    # Get sample data
    print("📊 Fetching sample records from ORBIT...")
    conn = fabric._get_connection()
    cursor = conn.cursor()
    
    # Get 50 recent records for analysis
    query = """
    SELECT TOP 50 *
    FROM dbo.ORBIT_Reporting_Table
    ORDER BY modifiedon DESC
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    
    print(f"✅ Retrieved {len(rows)} records for validation")
    print()
    
    # Convert to list of dicts
    records = []
    for row in rows:
        records.append(dict(zip(columns, row)))
    
    # ===== VALIDATION RESULTS =====
    print("=" * 100)
    print("FIELD-BY-FIELD VALIDATION")
    print("=" * 100)
    print()
    
    field_stats = {}
    
    for pam_field, config in PAM_FIELD_MAPPINGS.items():
        fabric_cols = config['fabric_columns']
        required = config.get('required', False)
        
        # Find values from Fabric
        values_found = 0
        values_valid = 0
        sample_values = []
        issues_found = []
        source_column_used = None
        
        for record in records:
            # Try each possible source column
            value = None
            for fc in fabric_cols:
                if fc in record and record[fc] is not None and str(record[fc]).strip() != '':
                    value = record[fc]
                    source_column_used = fc
                    break
            
            if value is not None:
                values_found += 1
                validation = validate_value(value, config)
                if validation['valid']:
                    values_valid += 1
                else:
                    issues_found.extend(validation['issues'])
                
                if len(sample_values) < 3:
                    sample_values.append(str(value)[:60])
        
        # Calculate stats
        population_pct = (values_found / len(records) * 100) if records else 0
        valid_pct = (values_valid / values_found * 100) if values_found > 0 else 0
        
        # Determine status
        if required and values_found == 0:
            status = "🔴 MISSING"
        elif required and population_pct < 80:
            status = "🟡 LOW DATA"
        elif values_found > 0 and valid_pct < 90:
            status = "🟡 QUALITY"
        elif values_found > 0:
            status = "🟢 GOOD"
        else:
            status = "⚪ EMPTY"
        
        field_stats[pam_field] = {
            'status': status,
            'source': source_column_used or fabric_cols[0],
            'population_pct': population_pct,
            'valid_pct': valid_pct,
            'required': required,
            'samples': sample_values,
            'issues': list(set(issues_found))[:3]
        }
    
    # Print results table
    print(f"{'PAM Field':<30} {'Status':<12} {'Source Column':<35} {'% Pop':<8} {'% Valid':<8} {'Req?'}")
    print("-" * 110)
    
    # Sort: Required first, then by status
    sorted_fields = sorted(field_stats.items(), 
                          key=lambda x: (not x[1]['required'], x[1]['status']))
    
    for pam_field, stats in sorted_fields:
        req = "✓" if stats['required'] else ""
        print(f"{pam_field:<30} {stats['status']:<12} {stats['source']:<35} {stats['population_pct']:>5.1f}%  {stats['valid_pct']:>5.1f}%   {req}")
    
    print()
    print("=" * 100)
    print("SAMPLE VALUES FOR KEY FIELDS")
    print("=" * 100)
    print()
    
    key_fields = ['initiative_name', 'Owner', 'orbit_id', 'promo_start_date', 'bill_facing_name', 'amount']
    for field in key_fields:
        if field in field_stats:
            stats = field_stats[field]
            print(f"📌 {field} (from {stats['source']}):")
            for i, sample in enumerate(stats['samples'], 1):
                print(f"   {i}. {sample}")
            print()
    
    # ===== SUMMARY =====
    print("=" * 100)
    print("VALIDATION SUMMARY")
    print("=" * 100)
    print()
    
    good = len([f for f, s in field_stats.items() if s['status'] == '🟢 GOOD'])
    low = len([f for f, s in field_stats.items() if s['status'] == '🟡 LOW DATA'])
    quality = len([f for f, s in field_stats.items() if s['status'] == '🟡 QUALITY'])
    missing = len([f for f, s in field_stats.items() if s['status'] == '🔴 MISSING'])
    empty = len([f for f, s in field_stats.items() if s['status'] == '⚪ EMPTY'])
    
    print(f"🟢 GOOD (>80% populated, >90% valid):   {good} fields")
    print(f"🟡 LOW DATA (required but <80%):        {low} fields")
    print(f"🟡 QUALITY ISSUES (<90% valid):         {quality} fields")
    print(f"🔴 MISSING (required but 0%):           {missing} fields")
    print(f"⚪ EMPTY (optional, 0% populated):      {empty} fields")
    print()
    
    # Required fields check
    required_fields = [f for f, c in PAM_FIELD_MAPPINGS.items() if c.get('required')]
    required_ok = [f for f in required_fields if field_stats[f]['status'] == '🟢 GOOD']
    
    print(f"Required Fields: {len(required_ok)}/{len(required_fields)} passing")
    print()
    
    if missing > 0 or low > 0:
        print("⚠️  ACTION NEEDED:")
        for field, stats in field_stats.items():
            if stats['status'] in ['🔴 MISSING', '🟡 LOW DATA']:
                print(f"   - {field}: {stats['status']} - Source: {stats['source']}")
    else:
        print("✅ All required fields have sufficient data!")
    
    print()
    print("=" * 100)
    print("COMPLETE RECORD SAMPLE")
    print("=" * 100)
    print()
    
    if records:
        print("First record (mapped to PAM format):\n")
        record = records[0]
        for pam_field, config in sorted(PAM_FIELD_MAPPINGS.items()):
            value = None
            source = None
            for fc in config['fabric_columns']:
                if fc in record and record[fc]:
                    value = record[fc]
                    source = fc
                    break
            if value:
                print(f"  {pam_field}: {str(value)[:80]}")
                print(f"    └─ from: {source}")
    
    print()
    print("=" * 100)
    print("REPORT COMPLETE")
    print("=" * 100)
    
    # Export to JSON for sharing
    report_path = Path(__file__).parent.parent / 'data' / 'orbit_validation_report.json'
    report_data = {
        'generated_at': datetime.now().isoformat(),
        'records_analyzed': len(records),
        'field_stats': field_stats,
        'summary': {
            'good': good,
            'low_data': low,
            'quality_issues': quality,
            'missing': missing,
            'empty': empty,
            'required_ok': len(required_ok),
            'required_total': len(required_fields)
        }
    }
    
    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2, default=str)
    
    print(f"\n📄 Report saved to: {report_path}")


if __name__ == '__main__':
    run_validation()
