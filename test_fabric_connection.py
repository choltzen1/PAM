"""
Test script for Microsoft Fabric Data Warehouse connection using Service Principal
"""
import pyodbc
import struct
from azure.identity import ClientSecretCredential
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_fabric_connection():
    """
    Test connection to Microsoft Fabric Data Warehouse using Service Principal authentication
    """
    # Service Principal credentials
    tenant_id = os.getenv('FABRIC_TENANT_ID', 'be0f980b-dd99-4b19-bd7b-bc71a09b026c')
    client_id = os.getenv('FABRIC_CLIENT_ID', 'fe804f58-c827-4906-8754-8c8fe7863341')
    client_secret = os.getenv('FABRIC_CLIENT_SECRET')  # You'll need to add this to .env
    
    # Fabric Data Warehouse connection details
    server = os.getenv('FABRIC_SERVER', 'boma7puz3umuxpl3xry2bgycnq-pfqzvh7fituunjrpjqi5xkzyii.datawarehouse.fabric.microsoft.com')
    database = os.getenv('FABRIC_DATABASE', '55c3885d-ecc6-47a2-9ab5-839c7a60f6c6')
    port = '1433'
    
    print("=" * 80)
    print("Testing Microsoft Fabric Data Warehouse Connection")
    print("=" * 80)
    print(f"Server: {server}")
    print(f"Database: {database}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {'*' * 10 if client_secret else 'NOT SET'}")
    print("=" * 80)
    
    if not client_secret:
        print("\n❌ ERROR: FABRIC_CLIENT_SECRET not found in environment variables")
        print("Please add it to your .env file")
        return None
    
    try:
        # Get access token using Service Principal
        print("\n🔐 Authenticating with Service Principal...")
        
        # Disable SSL verification for corporate networks with self-signed certs
        os.environ['REQUESTS_CA_BUNDLE'] = ''
        os.environ['CURL_CA_BUNDLE'] = ''
        
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            connection_verify=False  # Disable SSL verification
        )
        
        # Get token for SQL Database scope
        token = credential.get_token("https://database.windows.net/.default")
        print("✅ Successfully obtained access token")
        
        # Small delay to ensure token is fully ready
        time.sleep(1)
        
        # Convert token to the format needed by pyodbc
        token_bytes = token.token.encode('utf-16-le')
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        
        # Build connection string
        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={server},{port};"
            f"DATABASE={database};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=yes;"
            f"Connection Timeout=60;"
            f"Login Timeout=60;"
        )
        
        print(f"\n🔌 Connecting to Fabric Data Warehouse...")
        print(f"Connection String: {connection_string}")
        
        # Connect using the token
        conn = pyodbc.connect(
            connection_string,
            attrs_before={1256: token_struct}  # SQL_COPT_SS_ACCESS_TOKEN
        )
        
        print("✅ Successfully connected to Fabric Data Warehouse!")
        
        # Test the connection with a simple query
        print("\n📊 Testing query execution...")
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION AS Version")
        version = cursor.fetchone()
        print(f"Database Version: {version[0]}")
        
        # Query ORBIT_Reporting_Table
        print("\n📋 Querying ORBIT_Reporting_Table...")
        cursor.execute("SELECT TOP 5 * FROM dbo.ORBIT_Reporting_Table")
        
        # Get column names
        columns = [column[0] for column in cursor.description]
        print(f"\nColumns: {', '.join(columns)}")
        print("=" * 80)
        
        # Fetch and display results
        rows = cursor.fetchall()
        if rows:
            print(f"\nFound {len(rows)} rows:")
            for i, row in enumerate(rows, 1):
                print(f"\n--- Row {i} ---")
                for col, val in zip(columns, row):
                    # Truncate long values for display
                    if val is None:
                        display_val = "NULL"
                    elif isinstance(val, str) and len(val) > 100:
                        display_val = val[:100] + "..."
                    else:
                        display_val = str(val)
                    print(f"  {col}: {display_val}")
        else:
            print("No data found in ORBIT_Reporting_Table")
        
        cursor.close()
        
        print("\n" + "=" * 80)
        print("✅ CONNECTION TEST SUCCESSFUL!")
        print("=" * 80)
        
        return conn
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ CONNECTION TEST FAILED")
        print("=" * 80)
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        
        if "azure.identity" in str(type(e)):
            print("\n💡 Authentication Error - Check your credentials:")
            print("   - Verify Tenant ID, Client ID, and Client Secret")
            print("   - Ensure Service Principal has proper permissions")
        elif "ODBC" in str(e):
            print("\n💡 ODBC Driver Error:")
            print("   - Ensure 'ODBC Driver 18 for SQL Server' is installed")
            print("   - Run: brew install msodbcsql18 (on macOS)")
        elif "timeout" in str(e).lower():
            print("\n💡 Connection Timeout:")
            print("   - Check network connectivity")
            print("   - Verify firewall rules allow connection")
        
        return None

if __name__ == "__main__":
    conn = get_fabric_connection()
    
    if conn:
        # Keep connection open for manual testing if needed
        print("\n✨ Connection is ready for use!")
        print("Closing connection...")
        conn.close()
        print("Connection closed.")
    else:
        print("\n❌ Failed to establish connection")
        print("\nPlease ensure:")
        print("1. FABRIC_CLIENT_SECRET is set in your .env file")
        print("2. The azure-identity package is installed: pip install azure-identity")
        print("3. ODBC Driver 18 for SQL Server is installed")
