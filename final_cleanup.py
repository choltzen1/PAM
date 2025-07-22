#!/usr/bin/env python3
"""
Clean up duplicate/empty files after organization
"""

import os
import shutil

def cleanup_duplicates():
    """Remove empty files and duplicates from root directory"""
    
    print("🧹 Cleaning up duplicate/empty files...")
    
    # Files that should only exist in organized folders
    files_to_remove = [
        # Core files (should be in core/)
        'create_correct_comprehensive_mapping.py',
        'device_mapping_updater.py',
        'batch_device_search.py',
        'excel_batch_search.py',
        'notification_system.py',
        'setup_automation.py',
        
        # Data files (should be in data/)
        'device_alias_mapping.csv',
        'mapping_state.json',
        
        # Automation files (should be in automation/)
        'daily_check.py',
        
        # Development files (should be archived)
        'debug_excel.py',
        'debug_mapping.py',
        'debug_mapping2.py',
        'debug_values.py',
        'demo_alerts.py',
        'check_aliases.py',
        'check_s24_plus.py',
        'add_missing_aliases.py',
        'fix_alias_contamination.py',
        'create_comprehensive_mapping.py',
        'comprehensive_alias_generator.py',
        'generate_device_aliases.py',
        'extract_device_names.py',
        'example_devices.txt',
        
        # Old Excel files
        'ORBIT26035_071725.xlsx'
    ]
    
    removed_count = 0
    for file in files_to_remove:
        if os.path.exists(file):
            try:
                # Check if file is empty or very small (likely a leftover)
                file_size = os.path.getsize(file)
                if file_size < 100:  # Less than 100 bytes = likely empty/leftover
                    os.remove(file)
                    print(f"   🗑️ Removed empty: {file}")
                    removed_count += 1
                else:
                    # Check if organized version exists
                    organized_paths = [
                        f'core/{file}',
                        f'data/{file}', 
                        f'automation/{file}',
                        f'archive/development/{file}',
                        f'archive/testing/{file}'
                    ]
                    
                    organized_exists = any(os.path.exists(path) for path in organized_paths)
                    
                    if organized_exists:
                        # Move to archive instead of deleting
                        archive_path = f'archive/duplicates/{file}'
                        os.makedirs('archive/duplicates', exist_ok=True)
                        shutil.move(file, archive_path)
                        print(f"   📦 Archived duplicate: {file} -> archive/duplicates/")
                        removed_count += 1
                    else:
                        print(f"   ⚠️ Keeping: {file} (no organized version found)")
                        
            except Exception as e:
                print(f"   ❌ Error with {file}: {e}")
    
    # Remove cleanup scripts
    cleanup_scripts = [
        'cleanup_plan.py',
        'cleanup_workspace.py', 
        'preview_cleanup.py'
    ]
    
    for script in cleanup_scripts:
        if os.path.exists(script):
            os.remove(script)
            print(f"   🗑️ Removed cleanup script: {script}")
            removed_count += 1
    
    print(f"\n✅ Cleanup complete! Removed {removed_count} duplicate/empty files")
    
    # Show current root directory
    print(f"\n📁 Current root directory:")
    root_files = [f for f in os.listdir('.') if os.path.isfile(f)]
    for file in sorted(root_files):
        print(f"   📄 {file}")

if __name__ == "__main__":
    cleanup_duplicates()
