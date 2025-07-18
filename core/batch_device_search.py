import pandas as pd
import sys
import os

def load_device_mapping():
    """Load the device alias mapping from CSV file"""
    try:
        mapping_df = pd.read_csv('device_alias_mapping.csv')
        return mapping_df
    except FileNotFoundError:
        print("Error: device_alias_mapping.csv not found. Please run create_correct_comprehensive_mapping.py first.")
        return None

def find_devices_by_alias(alias, mapping_df):
    """Find all devices matching a given alias"""
    # Convert alias to lowercase for case-insensitive matching
    alias_lower = alias.lower()
    
    # Find matching aliases (case-insensitive)
    matching_aliases = mapping_df[
        mapping_df['marketing_alias'].str.lower() == alias_lower
    ]
    
    if matching_aliases.empty:
        return []
    
    # Get the manufacturer names for these aliases
    manufacturer_names = matching_aliases['manufacturer_name'].tolist()
    return manufacturer_names

def load_excel_data():
    """Load and filter the Excel data"""
    try:
        excel_df = pd.read_excel('Z0MATERIAL_ATTRB_REP01_00000.xlsx', header=7)
        filtered_df = excel_df[
            (excel_df['SKU Type'].isin(['A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'])) &
            (excel_df['Handset Brand'].isin(['T-MOBILE', 'SPRINT', 'UNIVERSAL']))
        ]
        return filtered_df
    except FileNotFoundError:
        print("Error: Excel file not found.")
        return None

def batch_device_search(device_list, output_file='batch_device_results.csv'):
    """
    Search for multiple devices and compile results into one spreadsheet
    
    Args:
        device_list: List of device names to search for
        output_file: Output CSV filename
    
    Returns:
        DataFrame with all results
    """
    
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
        
        # Find manufacturer names for this device
        manufacturer_names = find_devices_by_alias(device_name, mapping_df)
        
        if not manufacturer_names:
            print(f"  No mapping found for: {device_name}")
            search_summary.append({
                'Search_Term': device_name,
                'Status': 'No mapping found',
                'Devices_Found': 0
            })
            continue
        
        # Find matching devices in Excel data
        device_matches = excel_df[
            excel_df['Model(External)'].isin(manufacturer_names)
        ].copy()
        
        if device_matches.empty:
            print(f"  No devices found for: {device_name}")
            search_summary.append({
                'Search_Term': device_name,
                'Status': 'No devices found',
                'Devices_Found': 0
            })
            continue
        
        # Add the search term to each row for reference
        device_matches['Search_Term'] = device_name
        
        all_results.append(device_matches)
        
        print(f"  Found {len(device_matches)} devices for: {device_name}")
        search_summary.append({
            'Search_Term': device_name,
            'Status': 'Success',
            'Devices_Found': len(device_matches)
        })
    
    # Combine all results
    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)
        
        # Reorder columns to put Search_Term first
        cols = ['Search_Term'] + [col for col in combined_df.columns if col != 'Search_Term']
        combined_df = combined_df[cols]
        
        # Save to CSV
        combined_df.to_csv(output_file, index=False)
        
        # Create summary report
        summary_df = pd.DataFrame(search_summary)
        summary_file = output_file.replace('.csv', '_summary.csv')
        summary_df.to_csv(summary_file, index=False)
        
        print(f"\nResults saved to: {output_file}")
        print(f"Summary saved to: {summary_file}")
        print(f"Total devices found: {len(combined_df)}")
        
        return combined_df
    else:
        print("No devices found for any of the search terms.")
        return None

def read_device_list_from_file(filename):
    """Read device list from a text file (one device per line)"""
    try:
        with open(filename, 'r') as f:
            devices = [line.strip() for line in f.readlines() if line.strip()]
        return devices
    except FileNotFoundError:
        print(f"Error: File {filename} not found.")
        return None

def main():
    """Main function to handle command line arguments"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python batch_device_search.py 'device1,device2,device3'")
        print("  python batch_device_search.py --file device_list.txt")
        print("  python batch_device_search.py --interactive")
        return
    
    if sys.argv[1] == '--file':
        if len(sys.argv) < 3:
            print("Please provide a filename after --file")
            return
        
        device_list = read_device_list_from_file(sys.argv[2])
        if device_list is None:
            return
        
        output_file = sys.argv[3] if len(sys.argv) > 3 else 'batch_device_results.csv'
        
    elif sys.argv[1] == '--interactive':
        device_list = []
        print("Enter device names (press Enter twice to finish):")
        while True:
            device = input("Device name: ").strip()
            if not device:
                break
            device_list.append(device)
        
        if not device_list:
            print("No devices entered.")
            return
        
        output_file = input("Output filename (default: batch_device_results.csv): ").strip()
        if not output_file:
            output_file = 'batch_device_results.csv'
    
    else:
        # Parse comma-separated device list
        device_list = [device.strip() for device in sys.argv[1].split(',')]
        output_file = sys.argv[2] if len(sys.argv) > 2 else 'batch_device_results.csv'
    
    # Run the batch search
    result = batch_device_search(device_list, output_file)
    
    if result is not None:
        print(f"\nSearch completed successfully!")
        print(f"Found devices for {len(result['Search_Term'].unique())} different search terms")

if __name__ == "__main__":
    main()
