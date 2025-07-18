import pandas as pd
import os

def batch_search_from_excel(input_file, device_column='Device_Name', output_file=None):
    """
    Search for devices from an Excel file and return results
    
    Args:
        input_file: Path to Excel file containing device names
        device_column: Column name containing device names (default: 'Device_Name')
        output_file: Output file name (default: auto-generated)
    
    Returns:
        DataFrame with results
    """
    
    try:
        # Read the Excel file
        input_df = pd.read_excel(input_file)
        
        if device_column not in input_df.columns:
            print(f"Error: Column '{device_column}' not found in Excel file.")
            print(f"Available columns: {list(input_df.columns)}")
            return None
        
        # Get device list from the specified column
        device_list = input_df[device_column].dropna().unique().tolist()
        
        if not device_list:
            print("No devices found in the specified column.")
            return None
        
        # Generate output filename if not provided
        if output_file is None:
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_file = f"{base_name}_device_results.csv"
        
        print(f"Found {len(device_list)} unique devices in Excel file")
        
        # Use the existing batch search function
        from batch_device_search import batch_device_search
        result = batch_device_search(device_list, output_file)
        
        return result
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None

def create_sample_excel():
    """Create a sample Excel file for testing"""
    sample_data = {
        'Device_Name': [
            'iPhone 15',
            'iPhone 16 Pro Max',
            'Samsung S24',
            'Samsung S24 Ultra',
            'Pixel 9',
            'Pixel 9 Pro XL',
            'Moto Razr 2025',
            'Galaxy Z Fold6',
            'iPhone 15 Pro'
        ],
        'Notes': [
            'Base iPhone 15',
            'Top iPhone 16 model',
            'Base Samsung S24',
            'Premium Samsung S24',
            'Base Pixel 9',
            'Large Pixel 9 Pro',
            'Foldable Motorola',
            'Samsung foldable',
            'iPhone 15 Pro'
        ]
    }
    
    df = pd.DataFrame(sample_data)
    filename = 'sample_device_list.xlsx'
    df.to_excel(filename, index=False)
    print(f"Sample Excel file created: {filename}")
    return filename

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python excel_batch_search.py input_file.xlsx [device_column] [output_file]")
        print("  python excel_batch_search.py --create-sample")
        print()
        print("Examples:")
        print("  python excel_batch_search.py devices.xlsx")
        print("  python excel_batch_search.py devices.xlsx 'Phone_Model' custom_output.csv")
        sys.exit(1)
    
    if sys.argv[1] == '--create-sample':
        create_sample_excel()
        sys.exit(0)
    
    input_file = sys.argv[1]
    device_column = sys.argv[2] if len(sys.argv) > 2 else 'Device_Name'
    output_file = sys.argv[3] if len(sys.argv) > 3 else None
    
    result = batch_search_from_excel(input_file, device_column, output_file)
    
    if result is not None:
        print("Excel batch search completed successfully!")
    else:
        print("Excel batch search failed.")
