#!/usr/bin/env python3
"""
Automated workspace cleanup and organization script
"""

import os
import shutil
from pathlib import Path

def create_folder_structure():
    """Create the organized folder structure"""
    folders = [
        'core',
        'data', 
        'automation',
        'webapp',
        'archive/testing',
        'archive/development', 
        'archive/backups',
        'docs',
        'temp/reports',
        'temp/alerts',
        'temp/results'
    ]
    
    print("📁 Creating folder structure...")
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"   ✅ Created: {folder}/")

def move_production_files():
    """Move production files to organized folders"""
    
    # Core system files
    core_files = [
        'create_correct_comprehensive_mapping.py',
        'device_mapping_updater.py', 
        'batch_device_search.py',
        'excel_batch_search.py',
        'notification_system.py',
        'setup_automation.py'
    ]
    
    # Data files
    data_files = [
        'Z0MATERIAL_ATTRB_REP01_00000.xlsx',
        'device_alias_mapping.csv',
        'mapping_state.json',
        'PCR CPO-15843-R043-NewPromo.sql'
    ]
    
    # Automation files
    automation_files = [
        'update_device_mapping.bat',
        'device_mapping_service.py',
        'daily_check.py'
    ]
    
    # Webapp files
    webapp_files = [
        'app.py',
        'promo_engine.py', 
        'device_matcher.py',
        '.flaskenv'
    ]
    
    # Webapp folders
    webapp_folders = ['promo', 'services', 'static', 'templates']
    
    # Documentation files
    docs_files = ['ALERT_GUIDE.py']
    
    print("📦 Moving production files...")
    
    # Move core files
    for file in core_files:
        if os.path.exists(file):
            shutil.move(file, f'core/{file}')
            print(f"   ✅ Moved {file} -> core/")
    
    # Move data files  
    for file in data_files:
        if os.path.exists(file):
            shutil.move(file, f'data/{file}')
            print(f"   ✅ Moved {file} -> data/")
    
    # Move automation files
    for file in automation_files:
        if os.path.exists(file):
            shutil.move(file, f'automation/{file}')
            print(f"   ✅ Moved {file} -> automation/")
    
    # Move webapp files
    for file in webapp_files:
        if os.path.exists(file):
            shutil.move(file, f'webapp/{file}')
            print(f"   ✅ Moved {file} -> webapp/")
    
    # Move webapp folders
    for folder in webapp_folders:
        if os.path.exists(folder):
            shutil.move(folder, f'webapp/{folder}')
            print(f"   ✅ Moved {folder}/ -> webapp/")
    
    # Move documentation files
    for file in docs_files:
        if os.path.exists(file):
            shutil.move(file, f'docs/{file}')
            print(f"   ✅ Moved {file} -> docs/")

def archive_development_files():
    """Archive development and testing files instead of deleting"""
    
    # Development files to archive
    dev_files = [
        'debug_excel.py',
        'debug_mapping.py',
        'debug_mapping2.py', 
        'debug_values.py',
        'demo_alerts.py',
        'check_aliases.py',
        'check_s24_plus.py',
        'add_missing_aliases.py',
        'fix_alias_contamination.py'
    ]
    
    # Old mapping files
    old_mapping_files = [
        'create_comprehensive_mapping.py',
        'comprehensive_alias_generator.py',
        'generate_device_aliases.py',
        'extract_device_names.py'
    ]
    
    # Old data files
    old_data_files = [
        'device_mapping.json',
        'enhanced_device_mapping.json',
        'example_devices.txt',
        'unique_device_names.txt',
        'pdt_line.txt'
    ]
    
    # Test result files
    test_files = [
        'test_results.csv',
        'test_results_summary.csv',
        'batch_device_results.csv',
        'batch_device_results_summary.csv',
        'matched_devices.csv',
        'new_devices_detected.csv'
    ]
    
    # Old Excel files
    old_excel_files = [
        'ORBIT26035_071725.xlsx'
    ]
    
    print("📦 Archiving development files...")
    
    # Archive development files
    for file in dev_files:
        if os.path.exists(file):
            shutil.move(file, f'archive/development/{file}')
            print(f"   📦 Archived {file} -> archive/development/")
    
    # Archive old mapping files
    for file in old_mapping_files:
        if os.path.exists(file):
            shutil.move(file, f'archive/development/{file}')
            print(f"   📦 Archived {file} -> archive/development/")
    
    # Archive old data files
    for file in old_data_files:
        if os.path.exists(file):
            shutil.move(file, f'archive/development/{file}')
            print(f"   📦 Archived {file} -> archive/development/")
    
    # Archive test files
    for file in test_files:
        if os.path.exists(file):
            shutil.move(file, f'archive/testing/{file}')
            print(f"   📦 Archived {file} -> archive/testing/")
    
    # Archive old Excel files
    for file in old_excel_files:
        if os.path.exists(file):
            shutil.move(file, f'archive/backups/{file}')
            print(f"   📦 Archived {file} -> archive/backups/")

def delete_cache_files():
    """Delete cache and temporary files"""
    cache_items = ['__pycache__']
    
    print("🗑️ Cleaning cache files...")
    for item in cache_items:
        if os.path.exists(item):
            if os.path.isdir(item):
                shutil.rmtree(item)
                print(f"   🗑️ Deleted directory: {item}/")
            else:
                os.remove(item)
                print(f"   🗑️ Deleted file: {item}")

def update_imports():
    """Update import paths in files after reorganization"""
    print("🔧 Updating import paths...")
    
    # Files that need import updates
    files_to_update = [
        'automation/device_mapping_service.py',
        'automation/daily_check.py',
        'core/device_mapping_updater.py'
    ]
    
    for file_path in files_to_update:
        if os.path.exists(file_path):
            print(f"   🔧 Updating imports in {file_path}")
            update_file_imports(file_path)

def update_file_imports(file_path):
    """Update imports in a specific file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update imports
        content = content.replace(
            'from create_correct_comprehensive_mapping import',
            'from core.create_correct_comprehensive_mapping import'
        )
        content = content.replace(
            'from device_mapping_updater import',
            'from core.device_mapping_updater import'
        )
        content = content.replace(
            'from notification_system import',
            'from core.notification_system import'
        )
        
        # Update file paths
        content = content.replace(
            "excel_file='Z0MATERIAL_ATTRB_REP01_00000.xlsx'",
            "excel_file='data/Z0MATERIAL_ATTRB_REP01_00000.xlsx'"
        )
        content = content.replace(
            "'device_alias_mapping.csv'",
            "'data/device_alias_mapping.csv'"
        )
        content = content.replace(
            "'mapping_state.json'",
            "'data/mapping_state.json'"
        )
        
        with open(file_path, 'w') as f:
            f.write(content)
            
    except Exception as e:
        print(f"   ⚠️ Error updating {file_path}: {e}")

def create_documentation():
    """Create documentation files"""
    print("📝 Creating documentation...")
    
    # Create README.md
    readme_content = '''# Device Mapping Automation System

## Overview
Automated system for managing device aliases and mappings from T-Mobile Excel data.

## Folder Structure
- `core/` - Core production files
- `data/` - Data files and mappings
- `automation/` - Automation scripts
- `webapp/` - Flask web application
- `docs/` - Documentation
- `temp/` - Temporary files and reports
- `archive/` - Archived development files

## Quick Start
1. Run: `python core/setup_automation.py`
2. Test: `python automation/daily_check.py`
3. Manual check: `python core/device_mapping_updater.py --check`

## Daily Usage
- Check for alerts: `python automation/daily_check.py`
- Review `temp/alerts/` for manual attention files
- Update mappings in `core/create_correct_comprehensive_mapping.py`

## File Locations
- Excel data: `data/Z0MATERIAL_ATTRB_REP01_00000.xlsx`
- Device mappings: `data/device_alias_mapping.csv`
- System state: `data/mapping_state.json`
- Alerts: `temp/alerts/`
- Reports: `temp/reports/`
'''
    
    with open('docs/README.md', 'w') as f:
        f.write(readme_content)
    
    print("   📝 Created docs/README.md")

def main():
    """Main cleanup function"""
    print("🧹 Starting Workspace Cleanup & Organization")
    print("=" * 50)
    
    # Confirm before proceeding
    response = input("⚠️  This will reorganize your entire workspace. Continue? (y/N): ")
    if response.lower() != 'y':
        print("❌ Cleanup cancelled")
        return
    
    try:
        create_folder_structure()
        move_production_files()
        archive_development_files()
        delete_cache_files()
        update_imports()
        create_documentation()
        
        print("\n✅ Workspace cleanup complete!")
        print("\n📋 Next steps:")
        print("1. Test the system: python automation/daily_check.py")
        print("2. Update any remaining import paths if needed")
        print("3. Review docs/README.md for usage instructions")
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        print("You may need to manually fix some file locations")

if __name__ == "__main__":
    main()
