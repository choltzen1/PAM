#!/usr/bin/env python3
"""
Preview what will be cleaned up - no actual changes made
"""

import os
from pathlib import Path

def preview_cleanup():
    """Preview what files will be moved, archived, or deleted"""
    
    print("🔍 WORKSPACE CLEANUP PREVIEW")
    print("=" * 50)
    print("This shows what WILL happen - no files are changed yet\n")
    
    # Files that will be moved to organized folders
    moves = {
        'core/': [
            'create_correct_comprehensive_mapping.py',
            'device_mapping_updater.py',
            'batch_device_search.py', 
            'excel_batch_search.py',
            'notification_system.py',
            'setup_automation.py'
        ],
        'data/': [
            'Z0MATERIAL_ATTRB_REP01_00000.xlsx',
            'device_alias_mapping.csv',
            'mapping_state.json',
            'PCR CPO-15843-R043-NewPromo.sql'
        ],
        'automation/': [
            'update_device_mapping.bat',
            'device_mapping_service.py',
            'daily_check.py'
        ],
        'webapp/': [
            'app.py',
            'promo_engine.py',
            'device_matcher.py',
            '.flaskenv',
            'promo/',
            'services/',
            'static/',
            'templates/'
        ],
        'docs/': [
            'ALERT_GUIDE.py'
        ]
    }
    
    # Files that will be archived (not deleted)
    archives = {
        'archive/development/': [
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
            'device_mapping.json',
            'enhanced_device_mapping.json',
            'example_devices.txt',
            'unique_device_names.txt',
            'pdt_line.txt'
        ],
        'archive/testing/': [
            'test_results.csv',
            'test_results_summary.csv',
            'batch_device_results.csv',
            'batch_device_results_summary.csv',
            'matched_devices.csv',
            'new_devices_detected.csv'
        ],
        'archive/backups/': [
            'ORBIT26035_071725.xlsx'
        ]
    }
    
    # Files that will be deleted
    deletes = [
        '__pycache__/',
        'cleanup_plan.py',
        'cleanup_workspace.py',
        'demo_alerts.py'
    ]
    
    print("📦 FILES TO MOVE (Production files):")
    print("-" * 40)
    for folder, files in moves.items():
        print(f"  📁 {folder}")
        for file in files:
            status = "✅ exists" if os.path.exists(file) else "❌ missing"
            print(f"    {file} ({status})")
        print()
    
    print("📦 FILES TO ARCHIVE (Development files):")
    print("-" * 40)
    for folder, files in archives.items():
        print(f"  📁 {folder}")
        for file in files:
            status = "✅ exists" if os.path.exists(file) else "❌ missing"
            print(f"    {file} ({status})")
        print()
    
    print("🗑️ FILES TO DELETE (Cache/temp):")
    print("-" * 40)
    for file in deletes:
        status = "✅ exists" if os.path.exists(file) else "❌ missing"
        print(f"  {file} ({status})")
    
    print("\n📊 SUMMARY:")
    print("-" * 40)
    
    # Count existing files
    total_moves = 0
    total_archives = 0
    total_deletes = 0
    
    for folder, files in moves.items():
        total_moves += sum(1 for f in files if os.path.exists(f))
    
    for folder, files in archives.items():
        total_archives += sum(1 for f in files if os.path.exists(f))
    
    total_deletes = sum(1 for f in deletes if os.path.exists(f))
    
    print(f"  📦 Production files to organize: {total_moves}")
    print(f"  📦 Development files to archive: {total_archives}")
    print(f"  🗑️ Files to delete: {total_deletes}")
    
    print("\n🔧 WHAT HAPPENS NEXT:")
    print("-" * 40)
    print("1. 📁 Create organized folder structure")
    print("2. 📦 Move production files to appropriate folders")
    print("3. 📦 Archive development files (not deleted)")
    print("4. 🗑️ Delete cache and temporary files")
    print("5. 🔧 Update import paths in moved files")
    print("6. 📝 Create documentation")
    
    print("\n✅ SAFE CLEANUP:")
    print("-" * 40)
    print("• No production files are deleted")
    print("• All development files are archived")
    print("• Original files are preserved")
    print("• Easy to undo by moving files back")
    
    print("\n🚀 TO RUN ACTUAL CLEANUP:")
    print("-" * 40)
    print("python cleanup_workspace.py")

if __name__ == "__main__":
    preview_cleanup()
