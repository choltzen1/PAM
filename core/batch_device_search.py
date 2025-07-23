import pandas as pd
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import MAPPING_FILE, EXCEL_FILE, FILTER_CRITERIA, RESULTS_DIR

def load_device_mapping():
    """Load the device alias mapping from CSV file"""
    try:
        mapping_path = PROJECT_ROOT / MAPPING_FILE
        if not mapping_path.exists():
            print(f"❌ Device mapping not found: {mapping_path}")
            print("Run: python run.py mapping")
            return None
            
        mapping_df = pd.read_csv(mapping_path)
        print(f"✅ Loaded device mapping from: {mapping_path}")
        return mapping_df
        
    except Exception as e:
        print(f"❌ Error loading device mapping: {e}")
        return None

def find_devices_by_alias(alias, mapping_df, excel_df):
    """Find all devices matching a given alias"""
    # Convert alias to lowercase for case-insensitive matching
    alias_lower = alias.lower()
    
    # Find matching aliases (case-insensitive)
    matching_aliases = mapping_df[
        mapping_df['marketing_alias'].str.lower() == alias_lower
    ]
    
    if len(matching_aliases) == 0:
        return pd.DataFrame()
    
    # Get the manufacturer names for these aliases
    manufacturer_names = matching_aliases['manufacturer_name'].tolist()
    
    # Find devices in Excel data that match these manufacturer names
    matching_devices = excel_df[excel_df['Model(External)'].isin(manufacturer_names)]
    
    return matching_devices

def load_excel_data():
    """Load and filter the Excel data"""
    try:
        excel_path = PROJECT_ROOT / EXCEL_FILE
        if not excel_path.exists():
            print(f"❌ Excel file not found: {excel_path}")
            return None
            
        excel_df = pd.read_excel(excel_path, header=7)
        # Use proper DataFrame filtering with .isin() and handle NaN values
        filtered_df = excel_df[
            (excel_df['SKU Type'].fillna('').isin(FILTER_CRITERIA['SKU Type'])) &
            (excel_df['Handset Brand'].fillna('').isin(FILTER_CRITERIA['Handset Brand']))
        ]
        print(f"✅ Loaded Excel data from: {excel_path}")
        return filtered_df
        
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        return None

def batch_device_search(device_list, output_file=None):
    """
    Search for multiple devices and compile results into one spreadsheet
    
    Args:
        device_list: List of device names to search for
        output_file: Output CSV filename (will be saved to results folder)
    
    Returns:
        Dictionary with results info and file paths
    """
    
    # Generate default output filename if not provided
    if output_file is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f'batch_results_{timestamp}.csv'
    
    # Ensure results directory exists and use full path
    results_dir = PROJECT_ROOT / RESULTS_DIR
    results_dir.mkdir(exist_ok=True)
    output_path = results_dir / output_file
    
    # Load necessary data
    mapping_df = load_device_mapping()
    if mapping_df is None:
        return None
    
    excel_df = load_excel_data()
    if excel_df is None:
        return None
    
    all_results = []
    search_summary = []
    
    print(f"Processing {len(device_list)} devices...")
    
    for i, device_name in enumerate(device_list, 1):
        print(f"Processing {i}/{len(device_list)}: {device_name}")
        
        # Find devices for this alias
        device_matches = find_devices_by_alias(device_name, mapping_df, excel_df)
        
        if device_matches.empty:
            print(f"  No devices found for: {device_name}")
            search_summary.append({
                'Search_Term': device_name,
                'Status': 'No devices found',
                'Devices_Found': 0
            })
            continue
        
        # Add the search term to each row for reference
        device_matches = device_matches.copy()
        device_matches['Search_Term'] = device_name
        
        all_results.append(device_matches)
        
        print(f"  Found {len(device_matches)} devices for: {device_name}")
        search_summary.append({
            'Search_Term': device_name,
            'Status': 'Found',
            'Devices_Found': len(device_matches)
        })
    
    # Combine all results
    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)
        
        # Reorder columns to put Search_Term first
        cols = ['Search_Term'] + [col for col in combined_df.columns if col != 'Search_Term']
        combined_df = combined_df[cols]
        
        # Save to CSV in results folder
        combined_df.to_csv(output_path, index=False)
        
        # Create summary
        summary_data = []
        for device in device_list:
            device_results = combined_df[combined_df['Search_Term'] == device]
            summary_data.append({
                'Device_Searched': device,
                'Results_Found': len(device_results)
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_path = output_path.with_stem(output_path.stem + '_summary')
        summary_df.to_csv(summary_path, index=False)
        
        print(f"\n✅ Results saved to: {output_path}")
        print(f"📊 Summary saved to: {summary_path}")
        
        return {
            'results_file': str(output_path),
            'summary_file': str(summary_path),
            'total_results': len(combined_df),
            'devices_searched': len(device_list)
        }
    else:
        print("❌ No devices found for any of the search terms.")
        
        # Create empty results files
        empty_df = pd.DataFrame(columns=['Search_Term', 'Message'])
        for device in device_list:
            empty_df = pd.concat([empty_df, pd.DataFrame({
                'Search_Term': [device],
                'Message': ['No matching devices found']
            })], ignore_index=True)
        
        empty_df.to_csv(output_path, index=False)
        
        # Create empty summary
        summary_data = []
        for device in device_list:
            summary_data.append({
                'Device_Searched': device,
                'Results_Found': 0
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_path = output_path.with_stem(output_path.stem + '_summary')
        summary_df.to_csv(summary_path, index=False)
        
        print(f"📁 Empty results saved to: {output_path}")
        print(f"📊 Summary saved to: {summary_path}")
        
        return {
            'results_file': str(output_path),
            'summary_file': str(summary_path),
            'total_results': 0,
            'devices_searched': len(device_list)
        }

def search_single_device(device_name):
    """Search for a single device and return results"""
    mapping_df = load_device_mapping()
    excel_df = load_excel_data()
    
    if mapping_df is None or excel_df is None:
        return None
    
    results = find_devices_by_alias(device_name, mapping_df, excel_df)
    return results

def main(input_data, output_file=None):
    """Main function for batch search"""
    try:
        # Parse input - could be comma-separated list or file path
        if isinstance(input_data, str):
            if input_data.endswith('.txt') and Path(input_data).exists():
                # Read from file
                with open(input_data, 'r') as f:
                    device_list = [line.strip() for line in f.readlines() if line.strip()]
            else:
                # Parse comma-separated list
                device_list = [device.strip() for device in input_data.split(',')]
        else:
            device_list = input_data
        
        if not device_list:
            print("❌ No devices to search for.")
            return None
        
        print(f"🔍 Searching for {len(device_list)} devices...")
        result = batch_device_search(device_list, output_file)
        print(f"✅ Batch search completed!")
        return result
        
    except Exception as e:
        print(f"❌ Error in batch search: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python batch_device_search.py 'device1,device2,device3'")
        print("  python batch_device_search.py device_list.txt")
        sys.exit(1)
    
    main(sys.argv[1])
