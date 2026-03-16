"""
build_catalog_hierarchy.py
Queries all rows from PAM.Trade_Catalog_Assurant and builds a hierarchy JSON
grouping every catalog variant under its root parent model name.

Output: tradeCatalogManufacturerDeviceHierarchy.json
"""

import json
import os
import re

import pyodbc
from dotenv import load_dotenv

load_dotenv()

CATALOG_TABLE = "PAM.Trade_Catalog_Assurant"

# Use the same connection parameters as the Flask app (PAM_DB_* vars)
_server   = os.getenv("PAM_DB_SERVER")
_database = os.getenv("PAM_DB_DATABASE")
_username = os.getenv("PAM_DB_USERNAME")
_password = os.getenv("PAM_DB_PASSWORD")
_driver   = os.getenv("PAM_DB_DRIVER", "ODBC Driver 17 for SQL Server")
_encrypt  = os.getenv("PAM_DB_ENCRYPT", "no")
_trust    = os.getenv("PAM_DB_TRUST_CERT", "yes")

PAM_CONN_STR = (
    f"DRIVER={{{_driver}}};"
    f"SERVER={_server};"
    f"DATABASE={_database};"
    f"UID={_username};"
    f"PWD={_password};"
    f"Encrypt={_encrypt};"
    f"TrustServerCertificate={_trust};"
)
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "tradeCatalogManufacturerDeviceHierarchy.json")


def _normalize(name: str) -> str:
    """Insert space between 2+ consecutive letters and an immediately following digit.
    Matches the same logic used in lists/routes.py so hierarchy is consistent."""
    return re.sub(r"([A-Za-z]{2,})(\d)", r"\1 \2", name)


def _find_root_parent(name: str, norm: str, existing_parents: dict) -> str | None:
    """Return the longest existing parent whose normalized name is a prefix of norm."""
    best = None
    best_len = 0
    for parent, parent_norm in existing_parents.items():
        if norm == parent_norm or norm.startswith(parent_norm + " "):
            if len(parent_norm) > best_len:
                best = parent
                best_len = len(parent_norm)
    return best


def build_hierarchy() -> dict:
    print(f"Connecting to SQL Server...")
    with pyodbc.connect(PAM_CONN_STR) as conn:
        cur = conn.cursor()
        print(f"Querying {CATALOG_TABLE}...")
        cur.execute(f"""
            SELECT DISTINCT MAXVALUE_MFG, MARKETING_NAME
            FROM {CATALOG_TABLE} WITH (NOLOCK)
            WHERE MAXVALUE_MFG  IS NOT NULL
              AND MARKETING_NAME IS NOT NULL
              AND MARKETING_NAME NOT LIKE '%Demo%'
              AND MARKETING_NAME NOT LIKE '%Dummy%'
            ORDER BY MAXVALUE_MFG, MARKETING_NAME
        """)
        rows = cur.fetchall()

    print(f"Retrieved {len(rows)} catalog entries across all brands")

    # Group raw names by brand
    by_brand: dict[str, list[str]] = {}
    for mfg, name in rows:
        by_brand.setdefault(mfg.strip(), []).append(name.strip())

    hierarchy: dict[str, dict[str, list[str]]] = {}

    for brand, names in sorted(by_brand.items()):
        # Sort by normalized length so shorter (more general) names are processed first
        names_sorted = sorted(names, key=lambda n: (len(_normalize(n)), _normalize(n)))

        # parent_name -> normalized form (for prefix matching)
        parent_norms: dict[str, str] = {}
        # parent_name -> list of variant catalog names (including itself)
        groups: dict[str, list[str]] = {}

        for name in names_sorted:
            norm = _normalize(name).lower()
            parent = _find_root_parent(name, norm, parent_norms)
            if parent:
                groups[parent].append(name)
            else:
                # This name is its own root parent
                parent_norms[name] = norm
                groups[name] = [name]

        hierarchy[brand] = groups

    return hierarchy


def main():
    if not _server or not _database:
        raise RuntimeError("PAM_DB_SERVER / PAM_DB_DATABASE not set in .env")

    hierarchy = build_hierarchy()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(hierarchy, f, indent=2, ensure_ascii=False)

    brand_count = len(hierarchy)
    parent_count = sum(len(v) for v in hierarchy.values())
    variant_count = sum(len(variants) for brand in hierarchy.values() for variants in brand.values())

    print(f"\nWritten to: {OUTPUT_FILE}")
    print(f"  {brand_count} brands")
    print(f"  {parent_count} parent models")
    print(f"  {variant_count} total catalog entries")


if __name__ == "__main__":
    main()
