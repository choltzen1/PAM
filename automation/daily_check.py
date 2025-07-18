#!/usr/bin/env python3
"""
Daily Alert Checker - Run this to see if there are any devices needing manual attention
"""

import os
from datetime import datetime
from notification_system import NotificationSystem

def main():
    """Check for alerts and provide quick summary"""
    
    print("📋 Daily Device Mapping Alert Check")
    print("=" * 40)
    print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check for alert files
    notifier = NotificationSystem()
    has_alerts = notifier.check_for_alerts()
    
    print()
    
    # Check for unmapped devices file
    if os.path.exists('unmapped_devices.csv'):
        print("⚠️  Found unmapped_devices.csv - Manual attention needed!")
        
        # Count lines in file
        with open('unmapped_devices.csv', 'r') as f:
            lines = f.readlines()
            device_count = len(lines) - 1  # Subtract header
            
        print(f"   📊 {device_count} devices need mapping rules")
        print(f"   📁 Review: unmapped_devices.csv")
    else:
        print("✅ No unmapped_devices.csv found")
    
    print()
    
    # Check for recent update reports
    report_files = [f for f in os.listdir('.') if f.startswith('update_report_')]
    if report_files:
        latest_report = sorted(report_files)[-1]
        print(f"📄 Latest report: {latest_report}")
        
        # Show file age
        file_time = os.path.getmtime(latest_report)
        file_age = datetime.now().timestamp() - file_time
        hours_old = file_age / 3600
        
        if hours_old < 24:
            print(f"   🕐 {hours_old:.1f} hours old")
        else:
            print(f"   📅 {hours_old/24:.1f} days old")
    else:
        print("❓ No update reports found")
    
    print()
    
    # Check state file
    if os.path.exists('mapping_state.json'):
        import json
        with open('mapping_state.json', 'r') as f:
            state = json.load(f)
        
        print("📊 System Status:")
        print(f"   📈 Total devices: {state.get('total_devices', 'Unknown')}")
        print(f"   📅 Last update: {datetime.fromtimestamp(state.get('last_update', 0)).strftime('%Y-%m-%d %H:%M:%S') if state.get('last_update') else 'Never'}")
        print(f"   ✅ Mapped devices: {state.get('mapped_devices', 'Unknown')}")
        print(f"   ⚠️  Unmapped devices: {state.get('unmapped_devices', 'Unknown')}")
    else:
        print("❓ No system state found - run setup first")
    
    print()
    print("🔄 Quick Commands:")
    print("   python device_mapping_updater.py --check    # Manual check")
    print("   python device_mapping_updater.py --detect   # Detect only")
    print("   python setup_automation.py                  # Initial setup")
    
    if has_alerts or os.path.exists('unmapped_devices.csv'):
        print()
        print("🚨 ACTION REQUIRED: Manual attention needed!")
        return False
    else:
        print()
        print("✅ All good! No manual attention required.")
        return True

if __name__ == "__main__":
    main()
