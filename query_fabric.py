"""Fabric Data Warehouse connection diagnostic + query runner.

Tries multiple Encrypt/TrustServerCertificate/Driver combinations so you can
pinpoint TLS/cert issues without changing the main app.

Troubleshooting checklist covered:
  - Encrypt=no  vs  Encrypt=yes
  - TrustServerCertificate=yes
  - Explicit port (FABRIC_PORT, default 1433)
  - ODBC Driver 17  vs  ODBC Driver 18
"""
import os
import struct
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Connection parameters from environment ─────────────────────────────────
SERVER   = os.getenv("FABRIC_SERVER", "").strip()
DATABASE = os.getenv("FABRIC_DATABASE", "").strip()
PORT     = os.getenv("FABRIC_PORT", "1433").strip()

TENANT_ID     = os.getenv("FABRIC_TENANT_ID", "")
CLIENT_ID     = os.getenv("FABRIC_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("FABRIC_CLIENT_SECRET", "")

# Override any single param at runtime via env if desired
FORCE_DRIVER  = os.getenv("FABRIC_DRIVER", "")        # blank = try both
FORCE_ENCRYPT = os.getenv("FABRIC_ENCRYPT", "")       # blank = try both


# ── Candidate connection variants (tried in order) ─────────────────────────
def _build_variants() -> list[dict]:
    drivers  = [FORCE_DRIVER] if FORCE_DRIVER else [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
    ]
    encrypts = [FORCE_ENCRYPT] if FORCE_ENCRYPT else ["yes", "no"]

    variants = []

    # Variant A: token injection (SQL_COPT_SS_ACCESS_TOKEN via attrs_before)
    for driver in drivers:
        for encrypt in encrypts:
            label = f"[token] Driver={driver}  Encrypt={encrypt}  TrustServerCertificate=yes  port={PORT}"
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={SERVER},{PORT};"
                f"DATABASE={DATABASE};"
                f"Encrypt={encrypt};"
                f"TrustServerCertificate=yes;"
                f"LoginTimeout=15;"
            )
            variants.append({"label": label, "conn_str": conn_str, "use_token": True})

    # Variant B: ActiveDirectoryServicePrincipal (UID=client_id@tenant_id, PWD=secret)
    # Same pattern as DATAVERSE_CONN_STR in .env — no token injection needed
    sp_uid = f"{CLIENT_ID}@{TENANT_ID}"
    for driver in drivers:
        for encrypt in encrypts:
            label = f"[sp] Driver={driver}  Encrypt={encrypt}  TrustServerCertificate=yes  port={PORT}"
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={SERVER},{PORT};"
                f"DATABASE={DATABASE};"
                f"Authentication=ActiveDirectoryServicePrincipal;"
                f"UID={sp_uid};"
                f"PWD={CLIENT_SECRET};"
                f"Encrypt={encrypt};"
                f"TrustServerCertificate=yes;"
                f"LoginTimeout=15;"
            )
            variants.append({"label": label, "conn_str": conn_str, "use_token": False})

    return variants


# ── OAuth token (Service Principal) ────────────────────────────────────────
def _get_token_struct() -> bytes | None:
    try:
        from azure.identity import ClientSecretCredential
        os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
        os.environ.setdefault("CURL_CA_BUNDLE", "")
        cred  = ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET,
                                       connection_verify=False)
        token = cred.get_token("https://database.windows.net/.default")
        tb    = token.token.encode("utf-16-le")
        return struct.pack(f"<I{len(tb)}s", len(tb), tb)
    except Exception as exc:
        logger.error(f"Token acquisition failed: {exc}")
        return None


# ── Probe each variant ──────────────────────────────────────────────────────
def find_working_connection(token_struct: bytes) -> tuple[str | None, object | None]:
    """Return (label, conn) for the first variant that connects, or (None, None)."""
    try:
        import pyodbc
    except ImportError:
        logger.error("pyodbc is not installed — run: pip install pyodbc")
        return None, None

    for v in _build_variants():
        logger.info(f"Trying: {v['label']}")
        try:
            if v["use_token"]:
                conn = pyodbc.connect(v["conn_str"], attrs_before={1256: token_struct})
            else:
                conn = pyodbc.connect(v["conn_str"])
            logger.info(f"  SUCCESS: {v['label']}")
            return v["label"], conn
        except Exception as exc:
            logger.warning(f"  FAILED : {exc}")

    return None, None


# ── Query runner ────────────────────────────────────────────────────────────
def query_fabric(sql: str, limit: int = 100) -> None:
    if not SERVER or not DATABASE:
        logger.error("FABRIC_SERVER or FABRIC_DATABASE not set in .env")
        sys.exit(1)

    logger.info(f"Server : {SERVER},{PORT}")
    logger.info(f"Database: {DATABASE}")
    print()

    token_struct = _get_token_struct()
    if not token_struct:
        sys.exit(1)

    label, conn = find_working_connection(token_struct)
    if not conn:
        logger.error("All connection variants failed — see warnings above.")
        logger.error("Next steps:")
        logger.error("  1. Verify FABRIC_SERVER/PORT are reachable (Test-NetConnection)")
        logger.error("  2. Check SQL Server error log for TLS/cert errors")
        logger.error("  3. Confirm TLS 1.2 is enabled on the server OS")
        logger.error("  4. Confirm ODBC Driver 17 or 18 is installed locally")
        sys.exit(1)

    print(f"\nConnected via: {label}")
    print(f"Query: {sql}")
    print("=" * 80)

    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        columns = [c[0] for c in cursor.description] if cursor.description else []
        rows    = cursor.fetchmany(max(1, limit))
    finally:
        cursor.close()
        conn.close()

    if not rows:
        print("Returned 0 row(s)")
        return

    print(" | ".join(columns))
    print("-" * 80)
    for row in rows:
        vals = []
        for v in row:
            if v is None:
                vals.append("NULL")
            elif isinstance(v, str):
                vals.append(v[:80])
            else:
                vals.append(str(v))
        print(" | ".join(vals))

    print(f"\nReturned {len(rows)} row(s)")


if __name__ == "__main__":
    sql = "SELECT TOP 5 * FROM dbo.ORBIT_Reporting_Table"
    query_fabric(sql, limit=100)
