"""Query Microsoft Fabric Data Warehouse (read-only).

Uses the same token-based path as the app's Fabric manager.
"""
import os

from dotenv import load_dotenv

from data.fabric_database import FabricDatabaseManager

# Load environment variables
load_dotenv()

# Confirmed Fabric endpoint defaults (can still be overridden by .env)
os.environ.setdefault(
    'FABRIC_SERVER',
    'boma7puz3umuxpl3xry2bgycnq-pfqzvh7fituunjrpjq5kxzvji.datawarehouse.fabric.microsoft.com'
)
os.environ.setdefault('FABRIC_DATABASE', 'ORBIT_Lakehouse')

# Match your C# pattern: DefaultAzureCredential -> SQL scope token
os.environ.setdefault('FABRIC_AUTH_MODE', 'default')


def query_fabric(sql: str, limit: int = 100):
    """Execute a read-only query against Fabric and print rows."""
    fabric = FabricDatabaseManager()

    print("🔌 Connecting to Fabric Data Warehouse...")
    print("📊 Executing query:")
    print(f"   {sql}")
    print("=" * 80)

    rows = fabric.execute_select(sql=sql, limit=limit)
    if not rows:
        print("\n✅ Returned 0 row(s)")
        return

    columns = list(rows[0].keys())
    print("\n" + " | ".join(columns))
    print("-" * 80)

    for row in rows:
        values = []
        for col in columns:
            val = row.get(col)
            if val is None:
                values.append("NULL")
            elif isinstance(val, str):
                values.append(val[:80])
            else:
                values.append(str(val))
        print(" | ".join(values))

    print(f"\n✅ Returned {len(rows)} row(s)")

if __name__ == "__main__":
    # Example query
    sql = "SELECT TOP 5 * FROM dbo.ORBIT_Reporting_Table"
    query_fabric(sql, limit=100)
