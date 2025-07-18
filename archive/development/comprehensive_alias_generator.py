import pandas as pd
import re
from collections import defaultdict

def generate_comprehensive_aliases():
    """Generate comprehensive marketing aliases for ALL devices in the Excel file"""
    
    # Load Excel file
    df = pd.read_excel('Z0MATERIAL_ATTRB_REP01_00000.xlsx', header=7)
    
    # Filter data
    filtered_df = df[
        (df['SKU Type'].isin(['A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'])) &
        (df['Handset Brand'].isin(['T-MOBILE', 'SPRINT', 'UNIVERSAL']))
    ]
    
    # Get unique devices
    unique_devices = filtered_df['Model(External)'].dropna().unique()
    
    # Load existing mapping
    existing_df = pd.read_csv('device_alias_mapping.csv')
    
    # Create new aliases list
    new_aliases = []
    
    for device in unique_devices:
        aliases = generate_device_aliases(device)
        for alias in aliases:
            new_aliases.append((alias, device))
    
    print(f"Generated {len(new_aliases)} new aliases for {len(unique_devices)} devices")
    
    # Combine with existing aliases
    for alias, manufacturer in new_aliases:
        new_row = pd.DataFrame({'marketing_alias': [alias], 'manufacturer_name': [manufacturer]})
        existing_df = pd.concat([existing_df, new_row], ignore_index=True)
    
    # Remove duplicates
    existing_df = existing_df.drop_duplicates(subset=['marketing_alias', 'manufacturer_name'])
    
    # Save updated mapping
    existing_df.to_csv('device_alias_mapping.csv', index=False)
    print(f"Total aliases in mapping: {len(existing_df)}")

def generate_device_aliases(device_name):
    """Generate marketing aliases for a single device"""
    aliases = set()
    device_name = str(device_name).strip()
    
    # Samsung Galaxy devices
    if device_name.startswith('SAM '):
        aliases.update(generate_samsung_aliases(device_name))
    
    # Apple devices
    elif device_name.startswith('APL '):
        aliases.update(generate_apple_aliases(device_name))
    
    # Google Pixel devices
    elif device_name.startswith('GGL '):
        aliases.update(generate_google_aliases(device_name))
    
    # Motorola devices
    elif device_name.startswith('MOT '):
        aliases.update(generate_motorola_aliases(device_name))
    
    # OnePlus devices
    elif device_name.startswith('OP '):
        aliases.update(generate_oneplus_aliases(device_name))
    
    # T-Mobile REVVL devices
    elif device_name.startswith('TMO '):
        aliases.update(generate_tmo_aliases(device_name))
    
    # LG devices
    elif device_name.startswith('LG '):
        aliases.update(generate_lg_aliases(device_name))
    
    # HTC devices
    elif device_name.startswith('HTC '):
        aliases.update(generate_htc_aliases(device_name))
    
    # TCL devices
    elif device_name.startswith('TCL '):
        aliases.update(generate_tcl_aliases(device_name))
    
    # Alcatel devices
    elif device_name.startswith('ALC '):
        aliases.update(generate_alcatel_aliases(device_name))
    
    # Generic aliases for any device
    aliases.update(generate_generic_aliases(device_name))
    
    return list(aliases)

def generate_samsung_aliases(device_name):
    """Generate Samsung-specific aliases"""
    aliases = set()
    
    # Galaxy S series
    if 'GS2' in device_name:
        number = extract_number_after('GS', device_name)
        if number:
            aliases.update([
                f'Samsung Galaxy S{number}',
                f'Samsung S{number}',
                f'Galaxy S{number}',
                f'Samsung GS{number}',
                f'GS{number}',
                f'S{number}'
            ])
            
            # Handle + variants
            if '+' in device_name:
                aliases.update([
                    f'Samsung Galaxy S{number}+',
                    f'Samsung S{number}+',
                    f'Galaxy S{number}+',
                    f'Samsung S{number} Plus',
                    f'Galaxy S{number} Plus',
                    f'S{number}+',
                    f'S{number} Plus'
                ])
            
            # Handle Ultra variants
            if 'ULT' in device_name:
                aliases.update([
                    f'Samsung Galaxy S{number} Ultra',
                    f'Samsung S{number} Ultra',
                    f'Galaxy S{number} Ultra',
                    f'Samsung S{number}U',
                    f'S{number} Ultra',
                    f'S{number}U'
                ])
    
    # Z Flip series
    elif 'Z FLIP' in device_name:
        number = extract_number_after('FLIP', device_name)
        if number:
            aliases.update([
                f'Samsung Galaxy Z Flip{number}',
                f'Samsung Z Flip{number}',
                f'Galaxy Z Flip{number}',
                f'Samsung Flip{number}',
                f'Galaxy Flip{number}',
                f'Z Flip{number}',
                f'Flip{number}',
                f'Samsung Galaxy Z Flip {number}',
                f'Samsung Z Flip {number}',
                f'Galaxy Z Flip {number}',
                f'Samsung Flip {number}',
                f'Galaxy Flip {number}',
                f'Z Flip {number}',
                f'Flip {number}'
            ])
    
    # Z Fold series
    elif 'Z FOLD' in device_name:
        number = extract_number_after('FOLD', device_name)
        if number:
            aliases.update([
                f'Samsung Galaxy Z Fold{number}',
                f'Samsung Z Fold{number}',
                f'Galaxy Z Fold{number}',
                f'Samsung Fold{number}',
                f'Galaxy Fold{number}',
                f'Z Fold{number}',
                f'Fold{number}',
                f'Samsung Galaxy Z Fold {number}',
                f'Samsung Z Fold {number}',
                f'Galaxy Z Fold {number}',
                f'Samsung Fold {number}',
                f'Galaxy Fold {number}',
                f'Z Fold {number}',
                f'Fold {number}'
            ])
    
    # Galaxy Watch series
    elif 'GW' in device_name:
        number = extract_number_after('GW', device_name)
        if number:
            aliases.update([
                f'Samsung Galaxy Watch{number}',
                f'Samsung Watch{number}',
                f'Galaxy Watch{number}',
                f'Samsung Galaxy Watch {number}',
                f'Samsung Watch {number}',
                f'Galaxy Watch {number}',
                f'GW{number}'
            ])
            
            # Handle Ultra variants
            if 'ULTRA' in device_name:
                aliases.update([
                    f'Samsung Galaxy Watch{number} Ultra',
                    f'Samsung Watch{number} Ultra',
                    f'Galaxy Watch{number} Ultra',
                    f'Samsung Galaxy Watch {number} Ultra',
                    f'Samsung Watch {number} Ultra',
                    f'Galaxy Watch {number} Ultra'
                ])
    
    return aliases

def generate_apple_aliases(device_name):
    """Generate Apple-specific aliases"""
    aliases = set()
    
    # iPhone series
    if 'IPHONE' in device_name:
        # Extract iPhone model
        iphone_match = re.search(r'IPHONE (\d+|SE\d*|X[RS]?|X[RS]? MAX)', device_name)
        if iphone_match:
            model = iphone_match.group(1)
            
            # Base iPhone aliases
            aliases.update([
                f'iPhone {model}',
                f'Apple iPhone {model}',
                f'iPhone{model}',
                f'i{model}' if model.isdigit() else f'i{model}'
            ])
            
            # Handle Pro variants
            if 'PRO' in device_name:
                if 'MAX' in device_name:
                    aliases.update([
                        f'iPhone {model} Pro Max',
                        f'Apple iPhone {model} Pro Max',
                        f'iPhone{model} Pro Max',
                        f'i{model} Pro Max',
                        f'iPhone {model} ProMax'
                    ])
                else:
                    aliases.update([
                        f'iPhone {model} Pro',
                        f'Apple iPhone {model} Pro',
                        f'iPhone{model} Pro',
                        f'i{model} Pro',
                        f'iPhone {model}Pro'
                    ])
            
            # Handle Plus variants
            elif 'PLUS' in device_name:
                aliases.update([
                    f'iPhone {model} Plus',
                    f'Apple iPhone {model} Plus',
                    f'iPhone{model} Plus',
                    f'i{model} Plus',
                    f'iPhone {model}+'
                ])
            
            # Handle Mini variants
            elif 'MINI' in device_name:
                aliases.update([
                    f'iPhone {model} Mini',
                    f'Apple iPhone {model} Mini',
                    f'iPhone{model} Mini',
                    f'i{model} Mini'
                ])
    
    # iPad series
    elif 'IPAD' in device_name:
        # Extract iPad model info
        if 'PRO' in device_name:
            size_match = re.search(r'(\d+\.?\d*)', device_name)
            if size_match:
                size = size_match.group(1)
                aliases.update([
                    f'iPad Pro {size}',
                    f'Apple iPad Pro {size}',
                    f'iPad Pro {size}"',
                    f'iPad Pro {size} inch'
                ])
        elif 'AIR' in device_name:
            aliases.update([
                'iPad Air',
                'Apple iPad Air',
                'iPad Air 2024' if '2024' in device_name else 'iPad Air'
            ])
        elif 'MINI' in device_name:
            aliases.update([
                'iPad Mini',
                'Apple iPad Mini',
                'iPad Mini 2024' if '2024' in device_name else 'iPad Mini'
            ])
    
    # Apple Watch series
    elif 'WAT' in device_name:
        if 'SE' in device_name:
            aliases.update([
                'Apple Watch SE',
                'Apple Watch SE2',
                'Watch SE',
                'Apple Watch SE 2',
                'AW SE'
            ])
        elif 'ULT' in device_name:
            aliases.update([
                'Apple Watch Ultra',
                'Apple Watch Ultra 2',
                'Watch Ultra',
                'AW Ultra'
            ])
        else:
            # Series watches
            series_match = re.search(r'S(\d+)', device_name)
            if series_match:
                series = series_match.group(1)
                aliases.update([
                    f'Apple Watch Series {series}',
                    f'Apple Watch S{series}',
                    f'Watch Series {series}',
                    f'AW S{series}',
                    f'Apple Watch {series}'
                ])
    
    return aliases

def generate_google_aliases(device_name):
    """Generate Google Pixel aliases"""
    aliases = set()
    
    if 'PIXEL' in device_name:
        # Extract Pixel model
        pixel_match = re.search(r'PIXEL (\d+[A-Z]?)', device_name)
        if pixel_match:
            model = pixel_match.group(1)
            
            # Base Pixel aliases
            aliases.update([
                f'Google Pixel {model}',
                f'Pixel {model}',
                f'Google Pixel{model}',
                f'Pixel{model}',
                f'P{model}'
            ])
            
            # Handle Pro variants
            if 'PRO' in device_name:
                if 'XL' in device_name:
                    aliases.update([
                        f'Google Pixel {model} Pro XL',
                        f'Pixel {model} Pro XL',
                        f'Google Pixel{model} Pro XL',
                        f'Pixel{model} Pro XL',
                        f'P{model} Pro XL',
                        f'Pixel {model} ProXL'
                    ])
                else:
                    aliases.update([
                        f'Google Pixel {model} Pro',
                        f'Pixel {model} Pro',
                        f'Google Pixel{model} Pro',
                        f'Pixel{model} Pro',
                        f'P{model} Pro',
                        f'Pixel {model}Pro'
                    ])
    
    # Handle Pixel Watch
    elif 'PIXEL WATCH' in device_name:
        aliases.update([
            'Google Pixel Watch',
            'Pixel Watch',
            'Google Watch',
            'Pixel Watch 2',
            'Pixel Watch 3'
        ])
    
    return aliases

def generate_motorola_aliases(device_name):
    """Generate Motorola aliases"""
    aliases = set()
    
    # Moto G series
    if 'G ' in device_name or 'G5' in device_name:
        aliases.update([
            'Motorola Moto G',
            'Moto G',
            'Motorola G',
            'Moto G Power',
            'Moto G Stylus'
        ])
    
    # Moto Edge series
    elif 'EDGE' in device_name:
        aliases.update([
            'Motorola Edge',
            'Moto Edge',
            'Motorola Edge+',
            'Moto Edge+'
        ])
    
    # Razr series
    elif 'RAZR' in device_name:
        aliases.update([
            'Motorola Razr',
            'Moto Razr',
            'Motorola Razr+',
            'Moto Razr+',
            'Motorola Razr Plus',
            'Moto Razr Plus'
        ])
    
    return aliases

def generate_oneplus_aliases(device_name):
    """Generate OnePlus aliases"""
    aliases = set()
    
    # Extract OnePlus model number
    op_match = re.search(r'(\d+[T]?)', device_name)
    if op_match:
        model = op_match.group(1)
        aliases.update([
            f'OnePlus {model}',
            f'OnePlus{model}',
            f'OP {model}',
            f'1+ {model}'
        ])
        
        # Handle Pro variants
        if 'PRO' in device_name:
            aliases.update([
                f'OnePlus {model} Pro',
                f'OnePlus{model} Pro',
                f'OP {model} Pro',
                f'1+ {model} Pro'
            ])
    
    # Handle Nord series
    elif 'NORD' in device_name:
        aliases.update([
            'OnePlus Nord',
            'OP Nord',
            'OnePlus Nord N10',
            'OnePlus Nord N20',
            'OnePlus Nord N30'
        ])
    
    return aliases

def generate_tmo_aliases(device_name):
    """Generate T-Mobile device aliases"""
    aliases = set()
    
    # REVVL series
    if 'REVVL' in device_name:
        revvl_match = re.search(r'REVVL (\d+)', device_name)
        if revvl_match:
            number = revvl_match.group(1)
            aliases.update([
                f'REVVL {number}',
                f'T-Mobile REVVL {number}',
                f'TMO REVVL {number}',
                f'REVVL{number}'
            ])
            
            # Handle Pro variants
            if 'PRO' in device_name:
                aliases.update([
                    f'REVVL {number} Pro',
                    f'T-Mobile REVVL {number} Pro',
                    f'TMO REVVL {number} Pro',
                    f'REVVL{number} Pro',
                    f'REVVL {number}Pro'
                ])
    
    return aliases

def generate_lg_aliases(device_name):
    """Generate LG aliases"""
    aliases = set()
    
    # LG G series
    if ' G' in device_name and any(x in device_name for x in ['G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'G8']):
        g_match = re.search(r'G(\d+)', device_name)
        if g_match:
            number = g_match.group(1)
            aliases.update([
                f'LG G{number}',
                f'LG G {number}',
                f'G{number}'
            ])
    
    # LG V series
    elif ' V' in device_name:
        v_match = re.search(r'V(\d+)', device_name)
        if v_match:
            number = v_match.group(1)
            aliases.update([
                f'LG V{number}',
                f'LG V {number}',
                f'V{number}'
            ])
    
    # LG Stylo series
    elif 'STYLO' in device_name:
        stylo_match = re.search(r'STYLO (\d+)', device_name)
        if stylo_match:
            number = stylo_match.group(1)
            aliases.update([
                f'LG Stylo {number}',
                f'LG Stylo{number}',
                f'Stylo {number}'
            ])
    
    return aliases

def generate_htc_aliases(device_name):
    """Generate HTC aliases"""
    aliases = set()
    
    # HTC One series
    if 'ONE' in device_name:
        aliases.update([
            'HTC One',
            'HTC One M8',
            'HTC One M9',
            'HTC One M10'
        ])
    
    return aliases

def generate_tcl_aliases(device_name):
    """Generate TCL aliases"""
    aliases = set()
    
    # Extract TCL model numbers
    tcl_match = re.search(r'(\d+)', device_name)
    if tcl_match:
        number = tcl_match.group(1)
        aliases.update([
            f'TCL {number}',
            f'TCL{number}'
        ])
    
    return aliases

def generate_alcatel_aliases(device_name):
    """Generate Alcatel aliases"""
    aliases = set()
    
    # Common Alcatel aliases
    aliases.update([
        'Alcatel',
        'Alcatel Go Flip',
        'Alcatel Joy Tab'
    ])
    
    return aliases

def generate_generic_aliases(device_name):
    """Generate generic aliases for any device"""
    aliases = set()
    
    # Remove common prefixes and generate simple aliases
    clean_name = device_name
    for prefix in ['SAM ', 'APL ', 'GGL ', 'MOT ', 'OP ', 'TMO ', 'LG ', 'HTC ', 'TCL ', 'ALC ']:
        clean_name = clean_name.replace(prefix, '')
    
    # Add the clean name as an alias
    if clean_name != device_name:
        aliases.add(clean_name)
    
    return aliases

def extract_number_after(prefix, text):
    """Extract number that comes after a prefix"""
    pattern = f'{prefix}(\d+)'
    match = re.search(pattern, text)
    return match.group(1) if match else None

if __name__ == "__main__":
    generate_comprehensive_aliases()
