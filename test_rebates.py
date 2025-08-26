from data.database import DatabaseManager
from data.hybrid_storage import HybridPromoDataManager

print("=== Testing Rebate Data Flow ===")

# Test database directly
db = DatabaseManager()
db_rebates = db.get_all_rebates()
print(f"Database returned: {len(db_rebates)} rebates")

# Test conversion process
print("\nTesting conversion...")
converted_count = 0
for record in db_rebates[:5]:  # Test first 5
    try:
        record_dict = {str(k): v for k, v in record.items()}
        promo_data = db.convert_db_record_to_json_format(record_dict)
        converted_count += 1
        print(f"  Record {converted_count}: code={record.get('code', 'N/A')}")
    except Exception as e:
        print(f"  Error converting record: {e}")

print(f"Successfully converted {converted_count} of 5 test records")

# Test hybrid manager cache building
print("\nTesting hybrid manager cache building...")
mgr = HybridPromoDataManager()
# Clear cache to force fresh load
mgr._rebates_cache = {}
mgr._rebates_cache_timestamp = None

rebates = mgr.get_all_rebates()
print(f"Hybrid manager returned: {len(rebates)} rebates")

# Check if workflow data is interfering
workflow_data = mgr._load_workflow_data()
print(f"Workflow data contains {len(workflow_data)} entries")
