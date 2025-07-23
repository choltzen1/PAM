#!/usr/bin/env python3
"""
DEVICE MAPPING QUICK START GUIDE
=================================

Updated commands for the organized folder structure.
Run these from the main promo-app directory.

"""

print("""
🚀 DEVICE MAPPING SYSTEM - QUICK COMMANDS
==========================================

📍 Make sure you're in: promo-app/ directory
📍 Activate virtual environment: .\\venv\\Scripts\\activate

🔄 DAILY OPERATIONS:
───────────────────
python automation/daily_check.py              # Check for alerts (run this daily)
python core/device_mapping_updater.py --check  # Manual update check
python core/device_mapping_updater.py --detect # Just detect new devices

🔍 DEVICE SEARCH:
────────────────
python core/batch_device_search.py            # Search for specific devices
python core/excel_batch_search.py             # Batch search from Excel/file

🛠️ SYSTEM MAINTENANCE:
─────────────────────
python core/create_correct_comprehensive_mapping.py  # Regenerate all mappings
python core/setup_automation.py                      # Initial system setup

📁 FILE LOCATIONS:
─────────────────
📊 Data Files:        data/
📋 Alerts & Reports:  temp/alerts/, temp/reports/
🔧 Core Scripts:      core/
🤖 Automation:       automation/
🌐 Web Interface:     webapp/

🚨 WHEN YOU SEE ALERTS:
──────────────────────
1. Run: python automation/daily_check.py
2. Check: temp/alerts/ folder for new files
3. Review: unmapped_devices.csv if it exists
4. Edit: core/create_correct_comprehensive_mapping.py to add new patterns
5. Test: python core/device_mapping_updater.py --check

💡 COMMON WORKFLOW:
─────────────────
1. Morning: python automation/daily_check.py
2. If alerts: Review temp/alerts/unmapped_devices.csv
3. Add patterns: Edit core/create_correct_comprehensive_mapping.py
4. Test fix: python core/device_mapping_updater.py --check
5. Verify: python automation/daily_check.py (should show no alerts)

🌐 WEB INTERFACE (Future):
─────────────────────────
python webapp/device_app.py                   # Start web interface
Visit: http://localhost:5000                  # Team-friendly interface

✅ SYSTEM STATUS CHECK:
─────────────────────
All commands work from main directory with organized folder structure!
""")

if __name__ == "__main__":
    import os
    print(f"\n📍 Current directory: {os.getcwd()}")
    print("✅ Ready to run device mapping commands!")
