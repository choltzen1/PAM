import pandas as pd
import re

def clean_alias_mapping():
    """
    Clean the alias mapping to prevent cross-contamination between device variants.
    Each alias should map to only ONE specific device variant.
    """
    
    # Load existing mapping
    df = pd.read_csv('device_alias_mapping.csv')
    
    print(f"Original mapping size: {len(df)}")
    
    # Create a new clean mapping
    clean_aliases = []
    
    # Load Excel file to get actual device names
    excel_df = pd.read_excel('Z0MATERIAL_ATTRB_REP01_00000.xlsx', header=7)
    filtered_df = excel_df[
        (excel_df['SKU Type'].isin(['A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'])) &
        (excel_df['Handset Brand'].isin(['T-MOBILE', 'SPRINT', 'UNIVERSAL']))
    ]
    
    unique_devices = filtered_df['Model(External)'].dropna().unique()
    
    print(f"Processing {len(unique_devices)} unique devices...")
    
    # Process each device and create precise aliases
    for device in unique_devices:
        aliases = generate_precise_aliases(device)
        for alias in aliases:
            clean_aliases.append((alias, device))
    
    # Convert to DataFrame
    clean_df = pd.DataFrame(clean_aliases, columns=['marketing_alias', 'manufacturer_name'])
    
    # Remove duplicates but keep first occurrence (most specific match)
    clean_df = clean_df.drop_duplicates(subset=['marketing_alias'], keep='first')
    
    # Save the cleaned mapping
    clean_df.to_csv('device_alias_mapping.csv', index=False)
    
    print(f"Cleaned mapping size: {len(clean_df)}")
    print(f"Removed {len(df) - len(clean_df)} duplicate/conflicting aliases")

def generate_precise_aliases(device_name):
    """
    Generate precise aliases that don't cross-contaminate variants.
    Each alias should map to exactly ONE device variant.
    """
    aliases = set()
    device_name = str(device_name).strip()
    
    # Samsung Galaxy S series - be very specific about variants
    if device_name.startswith('SAM ') and 'GS2' in device_name:
        aliases.update(generate_precise_samsung_aliases(device_name))
    
    # Apple iPhone series - be very specific about variants
    elif device_name.startswith('APL ') and 'IPHONE' in device_name:
        aliases.update(generate_precise_apple_aliases(device_name))
    
    # Google Pixel series - be very specific about variants
    elif device_name.startswith('GGL ') and 'PIXEL' in device_name:
        aliases.update(generate_precise_google_aliases(device_name))
    
    # Motorola series - be very specific about variants
    elif device_name.startswith('MOT ') and 'RAZR' in device_name:
        aliases.update(generate_precise_motorola_aliases(device_name))
    
    # OnePlus series
    elif device_name.startswith('OP '):
        aliases.update(generate_precise_oneplus_aliases(device_name))
    
    # T-Mobile REVVL series
    elif device_name.startswith('TMO ') and 'REVVL' in device_name:
        aliases.update(generate_precise_tmo_aliases(device_name))
    
    # Add the exact device name as an alias
    aliases.add(device_name)
    
    return list(aliases)

def generate_precise_samsung_aliases(device_name):
    """Generate precise Samsung aliases that don't cross-contaminate"""
    aliases = set()
    
    # S24 series - be very specific
    if 'S921U GS24 5G EUREKA1' in device_name:
        # This is the BASE S24 model
        aliases.update([
            'Samsung Galaxy S24',
            'Samsung S24',
            'Galaxy S24',
            'Samsung GS24',
            'GS24',
            'S24'
        ])
    
    elif 'S926U GS24+ 5G EUREKA2' in device_name:
        # This is the S24+ model
        aliases.update([
            'Samsung Galaxy S24+',
            'Samsung S24+',
            'Galaxy S24+',
            'Samsung S24 Plus',
            'Galaxy S24 Plus',
            'S24+',
            'S24 Plus'
        ])
    
    elif 'S928U GS24 ULT 5G EU3' in device_name:
        # This is the S24 Ultra model
        aliases.update([
            'Samsung Galaxy S24 Ultra',
            'Samsung S24 Ultra',
            'Galaxy S24 Ultra',
            'Samsung S24U',
            'S24 Ultra',
            'S24U'
        ])
    
    elif 'S721U GS24 FE 5G' in device_name:
        # This is the S24 FE model
        aliases.update([
            'Samsung Galaxy S24 FE',
            'Samsung S24 FE',
            'Galaxy S24 FE',
            'Samsung GS24 FE',
            'GS24 FE',
            'S24 FE'
        ])
    
    # S25 series - be very specific
    elif 'S931U GS25 5G' in device_name:
        # This is the BASE S25 model
        aliases.update([
            'Samsung Galaxy S25',
            'Samsung S25',
            'Galaxy S25',
            'Samsung GS25',
            'GS25',
            'S25'
        ])
    
    elif 'S936U GS25+ 5G' in device_name:
        # This is the S25+ model
        aliases.update([
            'Samsung Galaxy S25+',
            'Samsung S25+',
            'Galaxy S25+',
            'Samsung S25 Plus',
            'Galaxy S25 Plus',
            'S25+',
            'S25 Plus'
        ])
    
    elif 'S938U GS25 ULT 5G' in device_name:
        # This is the S25 Ultra model
        aliases.update([
            'Samsung Galaxy S25 Ultra',
            'Samsung S25 Ultra',
            'Galaxy S25 Ultra',
            'Samsung S25U',
            'S25 Ultra',
            'S25U'
        ])
    
    elif 'S731U GS25 FE' in device_name:
        # This is the S25 FE model
        aliases.update([
            'Samsung Galaxy S25 FE',
            'Samsung S25 FE',
            'Galaxy S25 FE',
            'Samsung GS25 FE',
            'GS25 FE',
            'S25 FE'
        ])
    
    # Z Flip series - be very specific
    elif 'Z FLIP6' in device_name:
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
    
    elif 'Z FLIP7' in device_name:
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
    
    # Z Fold series - be very specific
    elif 'Z FOLD6' in device_name:
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
    
    elif 'Z FOLD7' in device_name:
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
    
    return aliases

def generate_precise_apple_aliases(device_name):
    """Generate precise Apple aliases that don't cross-contaminate"""
    aliases = set()
    
    # iPhone 15 series - be very specific
    if 'IPHONE 15 128G' in device_name and 'PRO' not in device_name and 'PLUS' not in device_name:
        # This is the BASE iPhone 15
        aliases.update([
            'iPhone 15',
            'Apple iPhone 15',
            'iPhone15',
            'i15'
        ])
    
    elif 'IPHONE 15 PLUS' in device_name:
        # This is the iPhone 15 Plus
        aliases.update([
            'iPhone 15 Plus',
            'Apple iPhone 15 Plus',
            'iPhone15 Plus',
            'i15 Plus',
            'iPhone 15+'
        ])
    
    elif 'IPHONE 15 PRO MAX' in device_name:
        # This is the iPhone 15 Pro Max
        aliases.update([
            'iPhone 15 Pro Max',
            'Apple iPhone 15 Pro Max',
            'iPhone15 Pro Max',
            'i15 Pro Max',
            'iPhone 15 ProMax'
        ])
    
    elif 'IPHONE 15 PRO' in device_name and 'MAX' not in device_name:
        # This is the iPhone 15 Pro
        aliases.update([
            'iPhone 15 Pro',
            'Apple iPhone 15 Pro',
            'iPhone15 Pro',
            'i15 Pro',
            'iPhone 15Pro'
        ])
    
    # iPhone 16 series - be very specific
    elif 'IPHONE 16 128G' in device_name and 'PRO' not in device_name and 'PLUS' not in device_name:
        # This is the BASE iPhone 16
        aliases.update([
            'iPhone 16',
            'Apple iPhone 16',
            'iPhone16',
            'i16'
        ])
    
    elif 'IPHONE 16 PLUS' in device_name:
        # This is the iPhone 16 Plus
        aliases.update([
            'iPhone 16 Plus',
            'Apple iPhone 16 Plus',
            'iPhone16 Plus',
            'i16 Plus',
            'iPhone 16+'
        ])
    
    elif 'IPHONE 16 PRO MAX' in device_name:
        # This is the iPhone 16 Pro Max
        aliases.update([
            'iPhone 16 Pro Max',
            'Apple iPhone 16 Pro Max',
            'iPhone16 Pro Max',
            'i16 Pro Max',
            'iPhone 16 ProMax'
        ])
    
    elif 'IPHONE 16 PRO' in device_name and 'MAX' not in device_name:
        # This is the iPhone 16 Pro
        aliases.update([
            'iPhone 16 Pro',
            'Apple iPhone 16 Pro',
            'iPhone16 Pro',
            'i16 Pro',
            'iPhone 16Pro'
        ])
    
    return aliases

def generate_precise_google_aliases(device_name):
    """Generate precise Google aliases that don't cross-contaminate"""
    aliases = set()
    
    # Pixel 9 series - be very specific
    if 'PIXEL 9 5G TK4' in device_name and 'PRO' not in device_name:
        # This is the BASE Pixel 9
        aliases.update([
            'Google Pixel 9',
            'Pixel 9',
            'Google Pixel9',
            'Pixel9',
            'P9'
        ])
    
    elif 'PIXEL 9 PRO XL' in device_name:
        # This is the Pixel 9 Pro XL
        aliases.update([
            'Google Pixel 9 Pro XL',
            'Pixel 9 Pro XL',
            'Google Pixel9 Pro XL',
            'Pixel9 Pro XL',
            'P9 Pro XL',
            'Pixel 9 ProXL'
        ])
    
    elif 'PIXEL 9 PRO' in device_name and 'XL' not in device_name:
        # This is the Pixel 9 Pro
        aliases.update([
            'Google Pixel 9 Pro',
            'Pixel 9 Pro',
            'Google Pixel9 Pro',
            'Pixel9 Pro',
            'P9 Pro',
            'Pixel 9Pro'
        ])
    
    elif 'PIXEL 9A' in device_name:
        # This is the Pixel 9a
        aliases.update([
            'Google Pixel 9a',
            'Pixel 9a',
            'Google Pixel9a',
            'Pixel9a',
            'P9a',
            'Pixel 9A',
            'Google Pixel 9A'
        ])
    
    return aliases

def generate_precise_motorola_aliases(device_name):
    """Generate precise Motorola aliases that don't cross-contaminate"""
    aliases = set()
    
    # Razr series - be very specific
    if 'RAZR 5G VENUS' in device_name:
        # This is the BASE Razr
        aliases.update([
            'Motorola Razr',
            'Moto Razr',
            'Motorola Razr 5G',
            'Moto Razr 5G'
        ])
    
    elif 'RAZR+ 5G' in device_name or 'RAZR PLUS' in device_name:
        # This is the Razr+
        aliases.update([
            'Motorola Razr+',
            'Moto Razr+',
            'Motorola Razr Plus',
            'Moto Razr Plus',
            'Motorola Razr+ 5G',
            'Moto Razr+ 5G'
        ])
    
    elif 'RAZR ULTRA' in device_name:
        # This is the Razr Ultra
        aliases.update([
            'Motorola Razr Ultra',
            'Moto Razr Ultra',
            'Motorola Razr Ultra 5G',
            'Moto Razr Ultra 5G'
        ])
    
    return aliases

def generate_precise_oneplus_aliases(device_name):
    """Generate precise OnePlus aliases"""
    aliases = set()
    
    # Extract model number precisely
    if 'OP ' in device_name:
        # Look for specific model patterns
        if '10T' in device_name:
            aliases.update([
                'OnePlus 10T',
                'OnePlus10T',
                'OP 10T',
                '1+ 10T'
            ])
        elif '10 PRO' in device_name:
            aliases.update([
                'OnePlus 10 Pro',
                'OnePlus10 Pro',
                'OP 10 Pro',
                '1+ 10 Pro'
            ])
        elif '9 PRO' in device_name:
            aliases.update([
                'OnePlus 9 Pro',
                'OnePlus9 Pro',
                'OP 9 Pro',
                '1+ 9 Pro'
            ])
        elif '9 5G' in device_name and 'PRO' not in device_name:
            aliases.update([
                'OnePlus 9',
                'OnePlus9',
                'OP 9',
                '1+ 9'
            ])
    
    return aliases

def generate_precise_tmo_aliases(device_name):
    """Generate precise T-Mobile aliases"""
    aliases = set()
    
    # REVVL series - be very specific
    if 'REVVL 8 PRO' in device_name:
        aliases.update([
            'REVVL 8 Pro',
            'T-Mobile REVVL 8 Pro',
            'TMO REVVL 8 Pro',
            'REVVL8 Pro',
            'REVVL 8Pro'
        ])
    elif 'REVVL 8 5G' in device_name and 'PRO' not in device_name:
        aliases.update([
            'REVVL 8',
            'T-Mobile REVVL 8',
            'TMO REVVL 8',
            'REVVL8'
        ])
    elif 'REVVL 7 PRO' in device_name:
        aliases.update([
            'REVVL 7 Pro',
            'T-Mobile REVVL 7 Pro',
            'TMO REVVL 7 Pro',
            'REVVL7 Pro',
            'REVVL 7Pro'
        ])
    elif 'REVVL 7 5G' in device_name and 'PRO' not in device_name:
        aliases.update([
            'REVVL 7',
            'T-Mobile REVVL 7',
            'TMO REVVL 7',
            'REVVL7'
        ])
    
    return aliases

if __name__ == "__main__":
    clean_alias_mapping()
