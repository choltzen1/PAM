#!/usr/bin/env python3
"""Show remaining ambiguous fields one by one."""
import sys
import warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
warnings.filterwarnings('ignore')

from data.fabric_database import FabricDatabaseManager

def main():
    fabric = FabricDatabaseManager()
    conn = fabric._get_connection()
    if not conn:
        print("Connection failed")
        return
    cursor = conn.cursor()

    # 4. START DATE
    print("=" * 70)
    print("4. START DATE - Which one to use?")
    print("=" * 70)
    cursor.execute("""
        SELECT TOP 5 cat_billname, cat_startdate, cat_requestedlaunchdate, 
               cat_committedlaunchdate, cat_actuallaunchdate
        FROM dbo.ORBIT_Reporting_Table
        WHERE cat_billname IS NOT NULL AND cat_billname != ''
          AND cat_startdate IS NOT NULL
        ORDER BY modifiedon DESC
    """)
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"\nExample {i}: {row[0][:50]}")
        print(f"  cat_startdate:           {row[1]}")
        print(f"  cat_requestedlaunchdate: {row[2]}")
        print(f"  cat_committedlaunchdate: {row[3]}")
        print(f"  cat_actuallaunchdate:    {row[4]}")
    
    # 5. LIMIT PER BAN
    print("\n" + "=" * 70)
    print("5. LIMIT PER BAN - Which one to use?")
    print("=" * 70)
    cursor.execute("""
        SELECT TOP 5 cat_billname, cat_offerlimits, cat_offerlimitstfbban
        FROM dbo.ORBIT_Reporting_Table
        WHERE cat_billname IS NOT NULL AND cat_billname != ''
          AND (cat_offerlimits IS NOT NULL OR cat_offerlimitstfbban IS NOT NULL)
        ORDER BY modifiedon DESC
    """)
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"\nExample {i}: {row[0][:50]}")
        print(f"  cat_offerlimits:       {row[1]}")
        print(f"  cat_offerlimitstfbban: {row[2]}")
    
    # 6. SEGMENT
    print("\n" + "=" * 70)
    print("6. SEGMENT - Which one to use?")
    print("=" * 70)
    cursor.execute("""
        SELECT TOP 5 cat_billname, cat_customersegment, cat_targetaudiencesegment_display
        FROM dbo.ORBIT_Reporting_Table
        WHERE cat_billname IS NOT NULL AND cat_billname != ''
          AND (cat_customersegment IS NOT NULL OR cat_targetaudiencesegment_display IS NOT NULL)
        ORDER BY modifiedon DESC
    """)
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"\nExample {i}: {row[0][:50]}")
        print(f"  cat_customersegment:               {row[1]}")
        print(f"  cat_targetaudiencesegment_display: {row[2]}")
    
    # 7. NOTES
    print("\n" + "=" * 70)
    print("7. NOTES - Which one to use (or combine)?")
    print("=" * 70)
    cursor.execute("""
        SELECT TOP 5 cat_billname, cat_productnotes, cat_marketingnotes, cat_triagenotes
        FROM dbo.ORBIT_Reporting_Table
        WHERE cat_billname IS NOT NULL AND cat_billname != ''
          AND (cat_productnotes IS NOT NULL OR cat_marketingnotes IS NOT NULL OR cat_triagenotes IS NOT NULL)
        ORDER BY modifiedon DESC
    """)
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"\nExample {i}: {row[0][:50]}")
        pn = str(row[1])[:80] + "..." if row[1] and len(str(row[1])) > 80 else row[1]
        mn = str(row[2])[:80] + "..." if row[2] and len(str(row[2])) > 80 else row[2]
        tn = str(row[3])[:80] + "..." if row[3] and len(str(row[3])) > 80 else row[3]
        print(f"  cat_productnotes:   {pn}")
        print(f"  cat_marketingnotes: {mn}")
        print(f"  cat_triagenotes:    {tn}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
