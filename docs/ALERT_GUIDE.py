"""
DEVICE MAPPING ALERTS & NOTIFICATIONS - COMPLETE GUIDE
======================================================

This guide shows you exactly where alerts come from and how to review them.

💡 TL;DR: Check your folder daily for files starting with 🚨 or "unmapped_devices.csv"

ALERT SOURCES:
==============

1. 🖥️  CONSOLE OUTPUT (When script runs)
   ────────────────────────────────────────
   You'll see this in your terminal window:
   
   🔍 Checking for new devices...
   📊 Excel file last modified: 2025-07-17 10:00:15
   📈 Total devices in Excel: 1,552
   🆕 New devices detected: 12
   ✅ Mappable devices: 10
   ⚠️  Unmappable devices: 2          👈 THIS MEANS ACTION NEEDED!
   
   ⚠️  Unmapped devices saved to: unmapped_devices.csv
   📝 These devices need manual mapping rules added to the code
   
   📋 Update report saved to: update_report_20250717_101500.txt

2. 🚨 ALERT FILES (Created when manual attention needed)
   ────────────────────────────────────────────────────
   File name pattern: 🚨_MANUAL_ATTENTION_NEEDED_YYYYMMDD_HHMMSS.txt
   
   Contents:
   ┌─────────────────────────────────────────────────────┐
   │ 🚨 DEVICE MAPPING ALERT 🚨                          │
   │ ===================================                 │
   │                                                     │
   │ 📊 Summary:                                         │
   │    • New devices found: 12                          │
   │    • Devices needing manual mapping: 2             │
   │                                                     │
   │ 📋 What to do:                                      │
   │    1. Open unmapped_devices.csv in Excel           │
   │    2. Review the device names                       │
   │    3. Add new patterns to mapping code              │
   │    4. Run the system again                          │
   └─────────────────────────────────────────────────────┘

3. 📄 CSV FILES (Detailed data)
   ────────────────────────────
   
   📁 unmapped_devices.csv          👈 MOST IMPORTANT!
   ┌─────────────────────────────────────────────────────┐
   │ This file contains the exact devices that need      │
   │ your attention. Open in Excel to see:              │
   │                                                     │
   │ • Model(External) - Device names                   │
   │ • SKU Type - Device category                       │
   │ • Handset Brand - T-Mobile/Sprint/etc.            │
   │ • Full Excel row data                              │
   └─────────────────────────────────────────────────────┘
   
   📁 new_devices_detected.csv
   ┌─────────────────────────────────────────────────────┐
   │ Contains ALL new devices found (mapped + unmapped)  │
   │ Good for overall visibility of what's new           │
   └─────────────────────────────────────────────────────┘

4. 📋 REPORT FILES (Summary)
   ──────────────────────────
   Pattern: update_report_YYYYMMDD_HHMMSS.txt
   
   Contains:
   • Summary of what was processed
   • List of mappable devices (auto-handled)
   • List of unmappable devices (need attention)
   • Action items for manual review

HOW TO REVIEW ALERTS:
====================

DAILY ROUTINE:
1. Run: python daily_check.py
   - Shows summary of all alerts
   - Tells you if action is needed

2. If alerts exist:
   - Look for 🚨_MANUAL_ATTENTION_NEEDED_*.txt files
   - Open unmapped_devices.csv in Excel
   - Review device names in Model(External) column

3. For each unmapped device:
   - Determine if it's iPhone/Samsung/Motorola
   - Add pattern to create_correct_comprehensive_mapping.py
   - Test with: python device_mapping_updater.py --check

EXAMPLE REVIEW SESSION:
======================

You find unmapped_devices.csv with:
┌─────────────────────────────────────────────────────┐
│ Model(External)                                     │
│ ───────────────────────────────────────────────────│
│ iPhone 17 Pro Max 1TB Space Black                  │
│ SAMSUNG_GALAXY_S26_ULTRA_512GB_PHANTOM_SILVER     │
│ MYSTERY_DEVICE_XYZ123                              │
└─────────────────────────────────────────────────────┘

Actions:
1. iPhone 17 Pro Max → Should auto-map, check iPhone patterns
2. Samsung Galaxy S26 → Should auto-map, check Samsung patterns  
3. MYSTERY_DEVICE → Completely new, needs new pattern

AUTOMATION SETUP:
================

For beginners, I recommend:

1. 📅 DAILY MANUAL CHECK (Easiest)
   - Run: python daily_check.py every morning
   - Check for alert files in your folder
   - Review unmapped_devices.csv if it exists

2. 🔄 SCHEDULED AUTOMATION (Advanced)
   - Windows Task Scheduler runs daily at 10:15 AM
   - Check folder for new files after 10:15 AM
   - System creates alert files automatically

3. 📧 EMAIL NOTIFICATIONS (Future)
   - Can be added to email you when alerts occur
   - Requires email server configuration

QUICK COMMANDS:
==============

python daily_check.py              # Check for alerts
python device_mapping_updater.py --check    # Manual update check
python device_mapping_updater.py --detect   # Just detect new devices
python setup_automation.py         # Initial setup

TROUBLESHOOTING:
===============

Q: I don't see any alerts but I know there are new devices
A: Run: python device_mapping_updater.py --detect

Q: The system says devices are mappable but I want to review them
A: Check new_devices_detected.csv for all new devices

Q: I want to be notified immediately when new devices arrive
A: Set up Windows Task Scheduler to run hourly checks

Q: How do I know if my manual mapping worked?
A: Run: python device_mapping_updater.py --check
   - Should show 0 unmapped devices
   - unmapped_devices.csv should be deleted or empty

Remember: The system is designed to be SAFE. It won't auto-map anything 
it's not 100% sure about. When in doubt, it flags for manual review.
"""

print(__doc__)
