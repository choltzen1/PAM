import pandas as pd
import os
from datetime import datetime, timedelta
import json
# import schedule  # Temporarily commented out for testing
import time
from pathlib import Path

class DeviceMappingUpdater:
    def __init__(self, excel_file=None):
        if excel_file is None:
            # Determine the correct path based on where the script is run from
            if os.path.exists('data/Z0MATERIAL_ATTRB_REP01_00000.xlsx'):
                excel_file = 'data/Z0MATERIAL_ATTRB_REP01_00000.xlsx'
            elif os.path.exists('../data/Z0MATERIAL_ATTRB_REP01_00000.xlsx'):
                excel_file = '../data/Z0MATERIAL_ATTRB_REP01_00000.xlsx'
            else:
                excel_file = 'Z0MATERIAL_ATTRB_REP01_00000.xlsx'  # fallback
        
        self.excel_file = excel_file
        
        # Set other file paths relative to Excel file location
        excel_dir = os.path.dirname(excel_file)
        if excel_dir:
            data_dir = excel_dir
        else:
            data_dir = 'data' if os.path.exists('data') else '.'
            
        self.mapping_file = os.path.join(data_dir, 'device_alias_mapping.csv')
        self.state_file = os.path.join(data_dir, 'mapping_state.json')
        
        # Output files go to temp directory
        temp_dir = 'temp/alerts' if os.path.exists('temp/alerts') else '.'
        self.new_devices_file = os.path.join(temp_dir, 'new_devices_detected.csv')
        self.unmapped_devices_file = os.path.join(temp_dir, 'unmapped_devices.csv')
        
    def load_current_state(self):
        """Load the current state of device mapping"""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'last_update': None,
                'total_devices': 0,
                'mapped_devices': 0,
                'unmapped_devices': 0,
                'last_excel_size': 0,
                'known_devices': []
            }
    
    def save_current_state(self, state):
        """Save the current state of device mapping"""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def get_excel_file_info(self):
        """Get Excel file modification time and size"""
        try:
            stat = os.stat(self.excel_file)
            return {
                'modified_time': stat.st_mtime,
                'size': stat.st_size,
                'modified_datetime': datetime.fromtimestamp(stat.st_mtime)
            }
        except FileNotFoundError:
            return None
    
    def load_current_devices(self):
        """Load current devices from Excel file"""
        try:
            excel_df = pd.read_excel(self.excel_file, header=7)
            filtered_df = excel_df[
                (excel_df['SKU Type'].isin(['A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'])) &
                (excel_df['Handset Brand'].isin(['T-MOBILE', 'SPRINT', 'UNIVERSAL']))
            ]
            
            # Get unique devices
            unique_devices = filtered_df['Model(External)'].dropna().unique().tolist()
            return unique_devices, filtered_df
        except Exception as e:
            print(f"Error loading Excel file: {e}")
            return [], pd.DataFrame()
    
    def detect_new_devices(self):
        """Detect new devices compared to last known state"""
        print("🔍 Checking for new devices...")
        
        # Load current state
        state = self.load_current_state()
        
        # Get Excel file info
        excel_info = self.get_excel_file_info()
        if not excel_info:
            print("❌ Excel file not found!")
            return None
        
        # Check if Excel file has been modified
        if state['last_update'] and excel_info['modified_time'] <= state['last_update']:
            print("✅ Excel file hasn't been updated since last check")
            return None
        
        print(f"📊 Excel file last modified: {excel_info['modified_datetime']}")
        
        # Load current devices
        current_devices, current_df = self.load_current_devices()
        
        if not current_devices:
            print("❌ No devices found in Excel file")
            return None
        
        # Find new devices
        known_devices = set(state.get('known_devices', []))
        current_devices_set = set(current_devices)
        new_devices = current_devices_set - known_devices
        
        print(f"📈 Total devices in Excel: {len(current_devices)}")
        print(f"📋 Previously known devices: {len(known_devices)}")
        print(f"🆕 New devices detected: {len(new_devices)}")
        
        # Update state
        state.update({
            'last_update': excel_info['modified_time'],
            'total_devices': len(current_devices),
            'last_excel_size': excel_info['size'],
            'known_devices': current_devices
        })
        
        if new_devices:
            # Save new devices to file
            new_devices_df = current_df[current_df['Model(External)'].isin(new_devices)]
            new_devices_df.to_csv(self.new_devices_file, index=False)
            print(f"💾 New devices saved to: {self.new_devices_file}")
            
            # Log new devices
            print("🆕 New devices found:")
            for device in sorted(new_devices)[:10]:  # Show first 10
                print(f"   - {device}")
            if len(new_devices) > 10:
                print(f"   ... and {len(new_devices) - 10} more")
        
        self.save_current_state(state)
        return new_devices, current_df
    
    def classify_new_devices(self, new_devices):
        """Classify new devices as mappable or unmappable"""
        from create_correct_comprehensive_mapping import get_base_model
        
        mappable_devices = []
        unmappable_devices = []
        
        for device in new_devices:
            base_model = get_base_model(device)
            
            # If get_base_model returns the original device name, it's unmappable
            if base_model == device:
                unmappable_devices.append(device)
            else:
                mappable_devices.append((device, base_model))
        
        return mappable_devices, unmappable_devices
    
    def update_mapping_automatically(self):
        """Automatically update device mapping with new devices"""
        print("🔄 Starting automatic mapping update...")
        
        detection_result = self.detect_new_devices()
        if not detection_result:
            return
        
        new_devices, current_df = detection_result
        
        if not new_devices:
            print("✅ No new devices to process")
            return
        
        # Classify new devices
        mappable_devices, unmappable_devices = self.classify_new_devices(new_devices)
        
        print(f"✅ Mappable devices: {len(mappable_devices)}")
        print(f"⚠️  Unmappable devices: {len(unmappable_devices)}")
        
        # Save unmappable devices for manual review
        if unmappable_devices:
            unmappable_df = current_df[current_df['Model(External)'].isin(unmappable_devices)]
            unmappable_df.to_csv(self.unmapped_devices_file, index=False)
            print(f"⚠️  Unmappable devices saved to: {self.unmapped_devices_file}")
            print("📝 These devices need manual mapping rules added to the code")
        
        # If we have mappable devices, regenerate the mapping
        if mappable_devices:
            print("🔄 Regenerating device mapping...")
            try:
                from create_correct_comprehensive_mapping import create_comprehensive_mapping
                create_comprehensive_mapping()
                print("✅ Device mapping updated successfully!")
            except Exception as e:
                print(f"❌ Error updating mapping: {e}")
        
        # Update state
        state = self.load_current_state()
        state.update({
            'mapped_devices': len(mappable_devices),
            'unmapped_devices': len(unmappable_devices),
            'last_auto_update': datetime.now().timestamp()
        })
        self.save_current_state(state)
        
        # Generate report
        self.generate_update_report(mappable_devices, unmappable_devices)
        
        # Create alert if there are unmappable devices
        if unmappable_devices:
            self.create_manual_attention_alert(len(mappable_devices), len(unmappable_devices))
    
    def create_manual_attention_alert(self, mappable_count, unmappable_count):
        """Create alert file for manual attention"""
        try:
            from notification_system import NotificationSystem
            notifier = NotificationSystem()
            
            # Create alert file
            alert_file = notifier.create_alert_file(
                unmapped_count=unmappable_count,
                new_count=mappable_count + unmappable_count
            )
            
            # Try desktop notification
            notifier.create_desktop_alert(
                f"{unmappable_count} devices need manual mapping rules!",
                "Device Mapping Alert"
            )
            
        except Exception as e:
            print(f"⚠️  Could not create alert: {e}")
    
    def generate_update_report(self, mappable_devices, unmappable_devices):
        """Generate a report of the update process"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"update_report_{timestamp}.txt"
        
        with open(report_file, 'w') as f:
            f.write(f"Device Mapping Update Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"="*50 + "\n\n")
            
            f.write(f"Summary:\n")
            f.write(f"- New mappable devices: {len(mappable_devices)}\n")
            f.write(f"- New unmappable devices: {len(unmappable_devices)}\n\n")
            
            if mappable_devices:
                f.write(f"Mappable Devices (automatically added):\n")
                for device, base_model in mappable_devices:
                    f.write(f"  {device} -> {base_model}\n")
                f.write("\n")
            
            if unmappable_devices:
                f.write(f"Unmappable Devices (require manual attention):\n")
                for device in unmappable_devices:
                    f.write(f"  {device}\n")
                f.write("\n")
                f.write("Action Required:\n")
                f.write("- Add mapping rules for unmappable devices in create_correct_comprehensive_mapping.py\n")
                f.write("- Update the get_base_model() function with new device patterns\n")
        
        print(f"📋 Update report saved to: {report_file}")
    
    def schedule_daily_updates(self):
        """Schedule daily updates at 10:15 AM (15 minutes after Excel update)"""
        print("⚠️  Schedule module not available. For scheduling, install: pip install schedule")
        print("⏰ For now, run manually: python device_mapping_updater.py --check")
        return
    
    def manual_update_check(self):
        """Run a manual update check"""
        print("🔍 Running manual update check...")
        self.update_mapping_automatically()

def main():
    import sys
    
    updater = DeviceMappingUpdater()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--schedule':
            updater.schedule_daily_updates()
        elif sys.argv[1] == '--check':
            updater.manual_update_check()
        elif sys.argv[1] == '--detect':
            updater.detect_new_devices()
        else:
            print("Usage:")
            print("  python device_mapping_updater.py --schedule  # Run scheduled updates")
            print("  python device_mapping_updater.py --check    # Manual update check")
            print("  python device_mapping_updater.py --detect   # Just detect new devices")
    else:
        print("Device Mapping Updater")
        print("Usage:")
        print("  python device_mapping_updater.py --schedule  # Run scheduled updates")
        print("  python device_mapping_updater.py --check    # Manual update check")
        print("  python device_mapping_updater.py --detect   # Just detect new devices")

if __name__ == "__main__":
    main()
