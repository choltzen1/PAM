import pandas as pd
import re

def create_comprehensive_mapping():
    """
    Create a comprehensive mapping where each marketing alias maps to ALL variants of that device.
    For example, "Samsung S24+" should map to both 256GB and 512GB variants.
    """
    
    # Load Excel file
    excel_df = pd.read_excel('Z0MATERIAL_ATTRB_REP01_00000.xlsx', header=7)
    filtered_df = excel_df[
        (excel_df['SKU Type'].isin(['A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'])) &
        (excel_df['Handset Brand'].isin(['T-MOBILE', 'SPRINT', 'UNIVERSAL']))
    ]
    
    unique_devices = filtered_df['Model(External)'].dropna().unique()
    
    print(f"Processing {len(unique_devices)} unique devices...")
    
    # Create comprehensive mapping
    comprehensive_aliases = []
    
    # Group devices by their base model
    device_groups = group_devices_by_model(unique_devices)
    
    for base_model, variants in device_groups.items():
        marketing_aliases = generate_marketing_aliases(base_model)
        
        # Map each marketing alias to ALL variants of that device
        for alias in marketing_aliases:
            for variant in variants:
                comprehensive_aliases.append((alias, variant))
    
    # Convert to DataFrame
    df = pd.DataFrame(comprehensive_aliases, columns=['marketing_alias', 'manufacturer_name'])
    
    # Remove duplicates
    df = df.drop_duplicates()
    
    # Save the mapping
    df.to_csv('device_alias_mapping.csv', index=False)
    
    print(f"Created comprehensive mapping with {len(df)} aliases")
    print(f"Covering {len(device_groups)} device models")

def group_devices_by_model(devices):
    """Group devices by their base model, ignoring memory/storage variants"""
    device_groups = {}
    
    for device in devices:
        base_model = get_base_model(device)
        if base_model not in device_groups:
            device_groups[base_model] = []
        device_groups[base_model].append(device)
    
    return device_groups

def get_base_model(device_name):
    """Extract the base model name, ignoring memory/storage variants"""
    device_name = str(device_name).strip()
    
    # Samsung Galaxy S series
    if 'SAM S921U GS24 5G EUREKA1' in device_name:
        return 'Samsung Galaxy S24'
    elif 'SAM S926U GS24+ 5G EUREKA2' in device_name:
        return 'Samsung Galaxy S24+'
    elif 'SAM S928U GS24 ULT 5G EU3' in device_name:
        return 'Samsung Galaxy S24 Ultra'
    elif 'SAM S721U GS24 FE 5G' in device_name:
        return 'Samsung Galaxy S24 FE'
    elif 'SAM S931U GS25 5G' in device_name:
        return 'Samsung Galaxy S25'
    elif 'SAM S936U GS25+ 5G' in device_name:
        return 'Samsung Galaxy S25+'
    elif 'SAM S938U GS25 ULT 5G' in device_name:
        return 'Samsung Galaxy S25 Ultra'
    elif 'SAM S731U GS25 FE' in device_name:
        return 'Samsung Galaxy S25 FE'
    
    # Samsung Z Flip series
    elif 'SAM F741U Z FLIP6' in device_name:
        return 'Samsung Galaxy Z Flip6'
    elif 'SAM F766U Z FLIP7' in device_name:
        return 'Samsung Galaxy Z Flip7'
    
    # Samsung Z Fold series
    elif 'SAM F956U Z FOLD6' in device_name:
        return 'Samsung Galaxy Z Fold6'
    elif 'SAM F966U Z FOLD7' in device_name:
        return 'Samsung Galaxy Z Fold7'
    
    # Apple iPhone series
    elif 'APL IPHONE 15 128G' in device_name and 'PRO' not in device_name and 'PLUS' not in device_name:
        return 'Apple iPhone 15'
    elif 'APL IPHONE 15 PLUS' in device_name:
        return 'Apple iPhone 15 Plus'
    elif 'APL IPHONE 15 PRO MAX' in device_name:
        return 'Apple iPhone 15 Pro Max'
    elif 'APL IPHONE 15 PRO' in device_name and 'MAX' not in device_name:
        return 'Apple iPhone 15 Pro'
    elif 'APL IPHONE 16 128G' in device_name and 'PRO' not in device_name and 'PLUS' not in device_name:
        return 'Apple iPhone 16'
    elif 'APL IPHONE 16 PLUS' in device_name:
        return 'Apple iPhone 16 Plus'
    elif 'APL IPHONE 16 PRO MAX' in device_name:
        return 'Apple iPhone 16 Pro Max'
    elif 'APL IPHONE 16 PRO' in device_name and 'MAX' not in device_name:
        return 'Apple iPhone 16 Pro'
    
    # Google Pixel series
    elif 'GGL PIXEL 9 5G TK4' in device_name and 'PRO' not in device_name:
        return 'Google Pixel 9'
    elif 'GGL PIXEL 9 PRO XL' in device_name:
        return 'Google Pixel 9 Pro XL'
    elif 'GGL PIXEL 9 PRO' in device_name and 'XL' not in device_name:
        return 'Google Pixel 9 Pro'
    elif 'GGL PIXEL 9A' in device_name:
        return 'Google Pixel 9a'
    
    # T-Mobile REVVL series
    elif 'TMO REVVL 8 PRO' in device_name:
        return 'T-Mobile REVVL 8 Pro'
    elif 'TMO REVVL 8 5G' in device_name and 'PRO' not in device_name:
        return 'T-Mobile REVVL 8'
    elif 'TMO REVVL 7 PRO' in device_name:
        return 'T-Mobile REVVL 7 Pro'
    elif 'TMO REVVL 7 5G' in device_name and 'PRO' not in device_name:
        return 'T-Mobile REVVL 7'
    
    # Default: use the device name as-is
    return device_name

def generate_marketing_aliases(base_model):
    """Generate marketing aliases for a base model"""
    aliases = set()
    aliases.add(base_model)  # Add the base model itself
    
    # Samsung Galaxy S24 series
    if base_model == 'Samsung Galaxy S24':
        aliases.update([
            'Samsung Galaxy S24',
            'Samsung S24',
            'Galaxy S24',
            'Samsung GS24',
            'GS24',
            'S24'
        ])
    elif base_model == 'Samsung Galaxy S24+':
        aliases.update([
            'Samsung Galaxy S24+',
            'Samsung S24+',
            'Galaxy S24+',
            'Samsung S24 Plus',
            'Galaxy S24 Plus',
            'S24+',
            'S24 Plus'
        ])
    elif base_model == 'Samsung Galaxy S24 Ultra':
        aliases.update([
            'Samsung Galaxy S24 Ultra',
            'Samsung S24 Ultra',
            'Galaxy S24 Ultra',
            'Samsung S24U',
            'S24 Ultra',
            'S24U'
        ])
    elif base_model == 'Samsung Galaxy S24 FE':
        aliases.update([
            'Samsung Galaxy S24 FE',
            'Samsung S24 FE',
            'Galaxy S24 FE',
            'Samsung GS24 FE',
            'GS24 FE',
            'S24 FE'
        ])
    
    # Samsung Galaxy S25 series
    elif base_model == 'Samsung Galaxy S25':
        aliases.update([
            'Samsung Galaxy S25',
            'Samsung S25',
            'Galaxy S25',
            'Samsung GS25',
            'GS25',
            'S25'
        ])
    elif base_model == 'Samsung Galaxy S25+':
        aliases.update([
            'Samsung Galaxy S25+',
            'Samsung S25+',
            'Galaxy S25+',
            'Samsung S25 Plus',
            'Galaxy S25 Plus',
            'S25+',
            'S25 Plus'
        ])
    elif base_model == 'Samsung Galaxy S25 Ultra':
        aliases.update([
            'Samsung Galaxy S25 Ultra',
            'Samsung S25 Ultra',
            'Galaxy S25 Ultra',
            'Samsung S25U',
            'S25 Ultra',
            'S25U'
        ])
    elif base_model == 'Samsung Galaxy S25 FE':
        aliases.update([
            'Samsung Galaxy S25 FE',
            'Samsung S25 FE',
            'Galaxy S25 FE',
            'Samsung GS25 FE',
            'GS25 FE',
            'S25 FE'
        ])
    
    # Samsung Z Flip series
    elif base_model == 'Samsung Galaxy Z Flip6':
        aliases.update([
            'Samsung Galaxy Z Flip6',
            'Samsung Z Flip6',
            'Galaxy Z Flip6',
            'Samsung Flip6',
            'Galaxy Flip6',
            'Z Flip6',
            'Flip6',
            'Samsung Galaxy Z Flip 6',
            'Samsung Z Flip 6',
            'Galaxy Z Flip 6',
            'Samsung Flip 6',
            'Galaxy Flip 6',
            'Z Flip 6',
            'Flip 6'
        ])
    elif base_model == 'Samsung Galaxy Z Flip7':
        aliases.update([
            'Samsung Galaxy Z Flip7',
            'Samsung Z Flip7',
            'Galaxy Z Flip7',
            'Samsung Flip7',
            'Galaxy Flip7',
            'Z Flip7',
            'Flip7',
            'Samsung Galaxy Z Flip 7',
            'Samsung Z Flip 7',
            'Galaxy Z Flip 7',
            'Samsung Flip 7',
            'Galaxy Flip 7',
            'Z Flip 7',
            'Flip 7'
        ])
    
    # Samsung Z Fold series
    elif base_model == 'Samsung Galaxy Z Fold6':
        aliases.update([
            'Samsung Galaxy Z Fold6',
            'Samsung Z Fold6',
            'Galaxy Z Fold6',
            'Samsung Fold6',
            'Galaxy Fold6',
            'Z Fold6',
            'Fold6',
            'Samsung Galaxy Z Fold 6',
            'Samsung Z Fold 6',
            'Galaxy Z Fold 6',
            'Samsung Fold 6',
            'Galaxy Fold 6',
            'Z Fold 6',
            'Fold 6'
        ])
    elif base_model == 'Samsung Galaxy Z Fold7':
        aliases.update([
            'Samsung Galaxy Z Fold7',
            'Samsung Z Fold7',
            'Galaxy Z Fold7',
            'Samsung Fold7',
            'Galaxy Fold7',
            'Z Fold7',
            'Fold7',
            'Samsung Galaxy Z Fold 7',
            'Samsung Z Fold 7',
            'Galaxy Z Fold 7',
            'Samsung Fold 7',
            'Galaxy Fold 7',
            'Z Fold 7',
            'Fold 7'
        ])
    
    # Apple iPhone series
    elif base_model == 'Apple iPhone 15':
        aliases.update([
            'iPhone 15',
            'Apple iPhone 15',
            'iPhone15',
            'i15'
        ])
    elif base_model == 'Apple iPhone 15 Plus':
        aliases.update([
            'iPhone 15 Plus',
            'Apple iPhone 15 Plus',
            'iPhone15 Plus',
            'i15 Plus',
            'iPhone 15+'
        ])
    elif base_model == 'Apple iPhone 15 Pro':
        aliases.update([
            'iPhone 15 Pro',
            'Apple iPhone 15 Pro',
            'iPhone15 Pro',
            'i15 Pro',
            'iPhone 15Pro'
        ])
    elif base_model == 'Apple iPhone 15 Pro Max':
        aliases.update([
            'iPhone 15 Pro Max',
            'Apple iPhone 15 Pro Max',
            'iPhone15 Pro Max',
            'i15 Pro Max',
            'iPhone 15 ProMax'
        ])
    elif base_model == 'Apple iPhone 16':
        aliases.update([
            'iPhone 16',
            'Apple iPhone 16',
            'iPhone16',
            'i16'
        ])
    elif base_model == 'Apple iPhone 16 Plus':
        aliases.update([
            'iPhone 16 Plus',
            'Apple iPhone 16 Plus',
            'iPhone16 Plus',
            'i16 Plus',
            'iPhone 16+'
        ])
    elif base_model == 'Apple iPhone 16 Pro':
        aliases.update([
            'iPhone 16 Pro',
            'Apple iPhone 16 Pro',
            'iPhone16 Pro',
            'i16 Pro',
            'iPhone 16Pro'
        ])
    elif base_model == 'Apple iPhone 16 Pro Max':
        aliases.update([
            'iPhone 16 Pro Max',
            'Apple iPhone 16 Pro Max',
            'iPhone16 Pro Max',
            'i16 Pro Max',
            'iPhone 16 ProMax'
        ])
    
    # Google Pixel series
    elif base_model == 'Google Pixel 9':
        aliases.update([
            'Google Pixel 9',
            'Pixel 9',
            'Google Pixel9',
            'Pixel9',
            'P9'
        ])
    elif base_model == 'Google Pixel 9 Pro':
        aliases.update([
            'Google Pixel 9 Pro',
            'Pixel 9 Pro',
            'Google Pixel9 Pro',
            'Pixel9 Pro',
            'P9 Pro',
            'Pixel 9Pro'
        ])
    elif base_model == 'Google Pixel 9 Pro XL':
        aliases.update([
            'Google Pixel 9 Pro XL',
            'Pixel 9 Pro XL',
            'Google Pixel9 Pro XL',
            'Pixel9 Pro XL',
            'P9 Pro XL',
            'Pixel 9 ProXL'
        ])
    elif base_model == 'Google Pixel 9a':
        aliases.update([
            'Google Pixel 9a',
            'Pixel 9a',
            'Google Pixel9a',
            'Pixel9a',
            'P9a',
            'Pixel 9A',
            'Google Pixel 9A'
        ])
    
    # T-Mobile REVVL series
    elif base_model == 'T-Mobile REVVL 8':
        aliases.update([
            'REVVL 8',
            'T-Mobile REVVL 8',
            'TMO REVVL 8',
            'REVVL8'
        ])
    elif base_model == 'T-Mobile REVVL 8 Pro':
        aliases.update([
            'REVVL 8 Pro',
            'T-Mobile REVVL 8 Pro',
            'TMO REVVL 8 Pro',
            'REVVL8 Pro',
            'REVVL 8Pro'
        ])
    elif base_model == 'T-Mobile REVVL 7':
        aliases.update([
            'REVVL 7',
            'T-Mobile REVVL 7',
            'TMO REVVL 7',
            'REVVL7'
        ])
    elif base_model == 'T-Mobile REVVL 7 Pro':
        aliases.update([
            'REVVL 7 Pro',
            'T-Mobile REVVL 7 Pro',
            'TMO REVVL 7 Pro',
            'REVVL7 Pro',
            'REVVL 7Pro'
        ])
    
    return list(aliases)

if __name__ == "__main__":
    create_comprehensive_mapping()
