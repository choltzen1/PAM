"""
Query Microsoft Fabric Data Warehouse
"""
import pyodbc
import struct
from azure.identity import ClientSecretCredential
import os
from dotenv import load_dotenv
import warnings

# Suppress SSL warnings
warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv()

# Disable SSL verification for corporate networks
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['CURL_CA_BUNDLE'] = ''

def query_fabric(sql):
    """Execute a query against Fabric Data Warehouse"""
    
    # Get credentials from environment
    tenant_id = os.getenv('FABRIC_TENANT_ID')
    client_id = os.getenv('FABRIC_CLIENT_ID')
    client_secret = os.getenv('FABRIC_CLIENT_SECRET')
    server = os.getenv('FABRIC_SERVER')
    database = os.getenv('FABRIC_DATABASE')
    
    print(f"🔌 Connecting to Fabric Data Warehouse...")
    
    # Build connection string with Service Principal authentication
    connection_string = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server},1433;"
        f"DATABASE={database};"
        f"Authentication=ActiveDirectoryServicePrincipal;"
        f"UID={client_id};"
        f"PWD={client_secret};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=yes;"
        f"Connection Timeout=30;"
    )
    
    # Connect with service principal authentication (no token needed, ODBC handles it)
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    
    print(f"📊 Executing query:")
    print(f"   {sql}")
    print("="*80)
    
    # Execute query
    cursor.execute(sql)
    
    # Get column names
    columns = [column[0] for column in cursor.description]
    
    # Print header
    print("\n" + " | ".join(columns))
    print("-" * 80)
    
    # Fetch and display results
    rows = cursor.fetchall()
    for row in rows:
        values = []
        for val in row:
            if val is None:
                values.append("NULL")
            elif isinstance(val, str):
                values.append(val[:50])  # Truncate long strings
            else:
                values.append(str(val))
        print(" | ".join(values))
    
    print(f"\n✅ Returned {len(rows)} row(s)")
    
    # Clean up
    cursor.close()
    conn.close()

if __name__ == "__main__":
    # Example query
    sql = "SELECT TOP 5 * FROM dbo.ORBIT_Reporting_Table"
    query_fabric(sql)
