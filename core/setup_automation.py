import os
import sys
from pathlib import Path

def setup_automation():
    """Set up the automated device mapping update system"""
    
    print("🚀 Setting up Device Mapping Automation System")
    print("=" * 50)
    
    # Check if all required files exist
    required_files = [
        'Z0MATERIAL_ATTRB_REP01_00000.xlsx',
        'device_alias_mapping.csv',
        'create_correct_comprehensive_mapping.py',
        'device_mapping_updater.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n💡 Please ensure all required files are in the current directory")
        return False
    
    print("✅ All required files found")
    
    # Create initial state if it doesn't exist
    if not os.path.exists('mapping_state.json'):
        print("📝 Creating initial mapping state...")
        from device_mapping_updater import DeviceMappingUpdater
        updater = DeviceMappingUpdater()
        updater.detect_new_devices()
        print("✅ Initial state created")
    
    # Test the system
    print("\n🔍 Testing the update system...")
    from device_mapping_updater import DeviceMappingUpdater
    updater = DeviceMappingUpdater()
    
    try:
        updater.detect_new_devices()
        print("✅ Update system test passed")
    except Exception as e:
        print(f"❌ Update system test failed: {e}")
        return False
    
    print("\n🎯 Setup Complete!")
    print("\nNext steps:")
    print("1. Run manual check: python device_mapping_updater.py --check")
    print("2. Start scheduled updates: python device_mapping_updater.py --schedule")
    print("3. Set up Windows Task Scheduler or cron job for production")
    
    return True

def create_batch_file():
    """Create a Windows batch file for easy scheduling"""
    batch_content = f"""@echo off
cd /d "{os.getcwd()}"
python device_mapping_updater.py --check
echo Update completed at %date% %time%
"""
    
    with open('update_device_mapping.bat', 'w') as f:
        f.write(batch_content)
    
    print("📝 Created update_device_mapping.bat for Windows Task Scheduler")

def create_service_script():
    """Create a service script for continuous monitoring"""
    service_content = f"""#!/usr/bin/env python3
import sys
import os
sys.path.append('{os.getcwd()}')

from device_mapping_updater import DeviceMappingUpdater

if __name__ == "__main__":
    updater = DeviceMappingUpdater()
    updater.schedule_daily_updates()
"""
    
    with open('device_mapping_service.py', 'w') as f:
        f.write(service_content)
    
    print("📝 Created device_mapping_service.py for background service")

if __name__ == "__main__":
    if setup_automation():
        create_batch_file()
        create_service_script()
        print("\n🎉 Automation setup complete!")
    else:
        print("\n❌ Setup failed. Please resolve the issues and try again.")
