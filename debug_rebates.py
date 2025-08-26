from data.database import DatabaseManager

print("=== Sample Rebate Records ===")

db = DatabaseManager()
rebates = db.get_all_rebates()

print(f"Total rebates: {len(rebates)}")
print("\nSample record fields:")
if rebates:
    sample = rebates[0]
    for key, value in sample.items():
        print(f"  {key}: {value}")

print("\nLooking for non-NULL identifiers in first 10 records:")
for i, record in enumerate(rebates[:10]):
    identifiers = []
    for field in ['code', 'orbit_id', 'Orbit_ID', 'id', 'ID']:
        value = record.get(field)
        if value is not None and str(value) != 'NULL' and str(value).strip():
            identifiers.append(f"{field}={value}")
    print(f"  Record {i+1}: {', '.join(identifiers) if identifiers else 'No valid identifiers found'}")
