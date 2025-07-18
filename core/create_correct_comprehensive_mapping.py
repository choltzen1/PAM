import pandas as pd
import re

def create_comprehensive_mapping():
    """
    Create a comprehensive mapping where each marketing alias maps to ALL variants of that device.
    For example, "iPhone 15" should map to ALL iPhone 15 variants (128GB, 256GB, 512GB).
    """
    
    # Load Excel file
    excel_df = pd.read_excel('Z0MATERIAL_ATTRB_REP01_00000.xlsx', header=7)
    filtered_df = excel_df[
        (excel_df['SKU Type'].isin(['A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'])) &
        (excel_df['Handset Brand'].isin(['T-MOBILE', 'SPRINT', 'UNIVERSAL']))
    ]
    
    print(f"Processing {len(filtered_df)} total devices...")
    
    # Create comprehensive mapping
    comprehensive_aliases = []
    
    # Group devices by their base model using Long Description
    device_groups = group_devices_by_model(filtered_df)
    
    for base_model, device_rows in device_groups.items():
        marketing_aliases = generate_marketing_aliases(base_model)
        
        # Map each marketing alias to ALL variants of that device
        for alias in marketing_aliases:
            for _, device_row in device_rows.iterrows():
                manufacturer_name = device_row['Model(External)']
                comprehensive_aliases.append((alias, manufacturer_name))
    
    # Convert to DataFrame
    df = pd.DataFrame(comprehensive_aliases, columns=['marketing_alias', 'manufacturer_name'])
    
    # Remove duplicates
    df = df.drop_duplicates()
    
    # Save the mapping
    df.to_csv('device_alias_mapping.csv', index=False)
    
    print(f"Created comprehensive mapping with {len(df)} aliases")
    print(f"Covering {len(device_groups)} device models")
    print(f"Total unique devices: {len(df['manufacturer_name'].unique())}")

def group_devices_by_model(filtered_df):
    """Group device rows by their base model, ignoring memory/storage variants"""
    device_groups = {}
    
    for _, row in filtered_df.iterrows():
        device_name = row['Model(External)']
        base_model = get_base_model(device_name)
        
        if base_model not in device_groups:
            device_groups[base_model] = []
        device_groups[base_model].append(row)
    
    # Convert lists to DataFrames for easier processing
    for base_model in device_groups:
        device_groups[base_model] = pd.DataFrame(device_groups[base_model])
    
    return device_groups

def get_base_model(device_name):
    """Extract the base model name, ignoring memory/storage variants"""
    device_name = str(device_name).strip()
    
    # Samsung Galaxy S series - EXACT matching to prevent cross-contamination
    # Must check Ultra and + variants FIRST before base models
    if 'SAM S928U' in device_name:  # S24 Ultra
        return 'Samsung Galaxy S24 Ultra'
    elif 'SAM S926U' in device_name:  # S24+
        return 'Samsung Galaxy S24+'
    elif 'SAM S921U' in device_name:  # S24
        return 'Samsung Galaxy S24'
    elif 'SAM S721U' in device_name:  # S24 FE
        return 'Samsung Galaxy S24 FE'
    elif 'SAM S938U' in device_name:  # S25 Ultra
        return 'Samsung Galaxy S25 Ultra'
    elif 'SAM S936U' in device_name:  # S25+
        return 'Samsung Galaxy S25+'
    elif 'SAM S931U' in device_name:  # S25
        return 'Samsung Galaxy S25'
    elif 'SAM S731U' in device_name:  # S25 FE
        return 'Samsung Galaxy S25 FE'
    elif 'SAM S918U' in device_name:  # S23 Ultra
        return 'Samsung Galaxy S23 Ultra'
    elif 'SAM S916U' in device_name:  # S23+
        return 'Samsung Galaxy S23+'
    elif 'SAM S911U' in device_name:  # S23
        return 'Samsung Galaxy S23'
    elif 'SAM S711U' in device_name:  # S23 FE
        return 'Samsung Galaxy S23 FE'
    
    # Samsung Z Flip series
    elif 'SAM F741U' in device_name:
        return 'Samsung Galaxy Z Flip6'
    elif 'SAM F766U' in device_name:
        return 'Samsung Galaxy Z Flip7'
    
    # Samsung Z Fold series
    elif 'SAM F956U' in device_name:
        return 'Samsung Galaxy Z Fold6'
    elif 'SAM F966U' in device_name:
        return 'Samsung Galaxy Z Fold7'
    
    # Apple iPhone series - EXACT matching to prevent cross-contamination
    # Must check Pro Max FIRST before Pro to avoid incorrect matches
    if 'APL IPHONE 15 PRO MAX' in device_name:
        return 'Apple iPhone 15 Pro Max'
    elif 'APL IPHONE 15 PRO' in device_name and 'MAX' not in device_name:
        return 'Apple iPhone 15 Pro'
    elif 'APL IPHONE 15 PLUS' in device_name:
        return 'Apple iPhone 15 Plus'
    elif 'APL IPHONE 15' in device_name and 'PRO' not in device_name and 'PLUS' not in device_name:
        return 'Apple iPhone 15'
    elif 'APL IPHONE 16 PRO MAX' in device_name:
        return 'Apple iPhone 16 Pro Max'
    elif 'APL IPHONE 16 PRO' in device_name and 'MAX' not in device_name:
        return 'Apple iPhone 16 Pro'
    elif 'APL IPHONE 16 PLUS' in device_name:
        return 'Apple iPhone 16 Plus'
    elif 'APL IPHONE 16' in device_name and 'PRO' not in device_name and 'PLUS' not in device_name:
        return 'Apple iPhone 16'
    elif 'APL IPHONE 14 PRO MAX' in device_name:
        return 'Apple iPhone 14 Pro Max'
    elif 'APL IPHONE 14 PRO' in device_name and 'MAX' not in device_name:
        return 'Apple iPhone 14 Pro'
    elif 'APL IPHONE 14 PLUS' in device_name:
        return 'Apple iPhone 14 Plus'
    elif 'APL IPHONE 14' in device_name and 'PRO' not in device_name and 'PLUS' not in device_name:
        return 'Apple iPhone 14'
    elif 'APL IPHONE 13 PRO MAX' in device_name:
        return 'Apple iPhone 13 Pro Max'
    elif 'APL IPHONE 13 PRO' in device_name and 'MAX' not in device_name:
        return 'Apple iPhone 13 Pro'
    elif 'APL IPHONE 13 MINI' in device_name:
        return 'Apple iPhone 13 Mini'
    elif 'APL IPHONE 13' in device_name and 'PRO' not in device_name and 'MINI' not in device_name:
        return 'Apple iPhone 13'
    
    # Google Pixel series - EXACT matching to prevent cross-contamination
    elif 'GGL PIXEL 9 PRO XL' in device_name:
        return 'Google Pixel 9 Pro XL'
    elif 'GGL PIXEL 9 PRO' in device_name and 'XL' not in device_name:
        return 'Google Pixel 9 Pro'
    elif 'GGL PIXEL 9A' in device_name:
        return 'Google Pixel 9a'
    elif 'GGL PIXEL 9' in device_name and 'PRO' not in device_name and 'A' not in device_name:
        return 'Google Pixel 9'
    elif 'GGL PIXEL 8 PRO' in device_name:
        return 'Google Pixel 8 Pro'
    elif 'GGL PIXEL 8A' in device_name:
        return 'Google Pixel 8a'
    elif 'GGL PIXEL 8' in device_name and 'PRO' not in device_name and 'A' not in device_name:
        return 'Google Pixel 8'
    
    # T-Mobile REVVL series
    elif 'TMO REVVL 8 PRO' in device_name:
        return 'T-Mobile REVVL 8 Pro'
    elif 'TMO REVVL 8 5G' in device_name and 'PRO' not in device_name:
        return 'T-Mobile REVVL 8'
    elif 'TMO REVVL 7 PRO' in device_name:
        return 'T-Mobile REVVL 7 Pro'
    elif 'TMO REVVL 7 5G' in device_name and 'PRO' not in device_name:
        return 'T-Mobile REVVL 7'
    
    # Motorola devices - EXACT matching to prevent cross-contamination
    # NEVER include DUMMY devices - they are test/placeholder entries
    # Year is first two digits after XT (e.g., XT25533 = 2025, XT24533 = 2024)
    
    # Skip ALL DUMMY devices
    elif 'DUMMY' in device_name:
        return device_name  # Return as-is but won't get aliases
    
    # Motorola Razr series (folding phones)
    elif 'MOT XT25' in device_name and 'RAZR' in device_name:
        if 'ULTRA' in device_name:
            return 'Motorola Razr Ultra 2025'
        elif 'RAZR+' in device_name or 'RAZR +' in device_name:
            return 'Motorola Razr+ 2025'
        else:
            return 'Motorola Razr 2025'
    elif 'MOT XT24' in device_name and 'RAZR' in device_name:
        if 'ULTRA' in device_name:
            return 'Motorola Razr Ultra 2024'
        elif 'RAZR+' in device_name or 'RAZR +' in device_name:
            return 'Motorola Razr+ 2024'
        else:
            return 'Motorola Razr 2024'
    elif 'MOT XT23' in device_name and 'RAZR' in device_name:
        if 'ULTRA' in device_name:
            return 'Motorola Razr Ultra 2023'
        elif 'RAZR+' in device_name or 'RAZR +' in device_name:
            return 'Motorola Razr+ 2023'
        else:
            return 'Motorola Razr 2023'
    elif 'MOT XT22' in device_name and 'RAZR' in device_name:
        if 'ULTRA' in device_name:
            return 'Motorola Razr Ultra 2022'
        elif 'RAZR+' in device_name or 'RAZR +' in device_name:
            return 'Motorola Razr+ 2022'
        else:
            return 'Motorola Razr 2022'
    
    # Motorola Edge series
    elif 'MOT XT25' in device_name and 'EDGE' in device_name:
        if 'EDGE+' in device_name or 'EDGE +' in device_name:
            return 'Motorola Edge+ 2025'
        else:
            return 'Motorola Edge 2025'
    elif 'MOT XT24' in device_name and 'EDGE' in device_name:
        if 'EDGE+' in device_name or 'EDGE +' in device_name:
            return 'Motorola Edge+ 2024'
        else:
            return 'Motorola Edge 2024'
    elif 'MOT XT23' in device_name and 'EDGE' in device_name:
        if 'EDGE+' in device_name or 'EDGE +' in device_name:
            return 'Motorola Edge+ 2023'
        else:
            return 'Motorola Edge 2023'
    elif 'MOT XT22' in device_name and 'EDGE' in device_name:
        if 'EDGE+' in device_name or 'EDGE +' in device_name:
            return 'Motorola Edge+ 2022'
        else:
            return 'Motorola Edge 2022'
    
    # Moto G series
    elif 'MOT XT25' in device_name and ('G ' in device_name or 'GPOWER' in device_name or 'G STYLUS' in device_name or 'GPLAY' in device_name):
        if 'GPOWER' in device_name or 'G POWER' in device_name:
            return 'Moto G Power 2025'
        elif 'G STYLUS' in device_name or 'GSTYLUS' in device_name:
            return 'Moto G Stylus 2025'
        elif 'GPLAY' in device_name or 'G PLAY' in device_name:
            return 'Moto G Play 2025'
        else:
            return 'Moto G 2025'
    elif 'MOT XT24' in device_name and ('G ' in device_name or 'GPOWER' in device_name or 'G STYLUS' in device_name or 'GPLAY' in device_name):
        if 'GPOWER' in device_name or 'G POWER' in device_name:
            return 'Moto G Power 2024'
        elif 'G STYLUS' in device_name or 'GSTYLUS' in device_name:
            return 'Moto G Stylus 2024'
        elif 'GPLAY' in device_name or 'G PLAY' in device_name:
            return 'Moto G Play 2024'
        else:
            return 'Moto G 2024'
    elif 'MOT XT23' in device_name and ('G ' in device_name or 'GPOWER' in device_name or 'G STYLUS' in device_name or 'GPLAY' in device_name):
        if 'GPOWER' in device_name or 'G POWER' in device_name:
            return 'Moto G Power 2023'
        elif 'G STYLUS' in device_name or 'GSTYLUS' in device_name:
            return 'Moto G Stylus 2023'
        elif 'GPLAY' in device_name or 'G PLAY' in device_name:
            return 'Moto G Play 2023'
        else:
            return 'Moto G 2023'
    elif 'MOT XT22' in device_name and ('G ' in device_name or 'GPOWER' in device_name or 'G STYLUS' in device_name or 'GPLAY' in device_name):
        if 'GPOWER' in device_name or 'G POWER' in device_name:
            return 'Moto G Power 2022'
        elif 'G STYLUS' in device_name or 'GSTYLUS' in device_name:
            return 'Moto G Stylus 2022'
        elif 'GPLAY' in device_name or 'G PLAY' in device_name:
            return 'Moto G Play 2022'
        else:
            return 'Moto G 2022'
    
    # Default: return the original device name
    return device_name

def generate_marketing_aliases(base_model):
    """Generate marketing aliases for a base model"""
    aliases = set()
    
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
            'Samsung ZFlip6',
            'Z Flip6',
            'ZFlip6'
        ])
    elif base_model == 'Samsung Galaxy Z Flip7':
        aliases.update([
            'Samsung Galaxy Z Flip7',
            'Samsung Z Flip7',
            'Galaxy Z Flip7',
            'Samsung ZFlip7',
            'Z Flip7',
            'ZFlip7'
        ])
    
    # Samsung Z Fold series
    elif base_model == 'Samsung Galaxy Z Fold6':
        aliases.update([
            'Samsung Galaxy Z Fold6',
            'Samsung Z Fold6',
            'Galaxy Z Fold6',
            'Samsung ZFold6',
            'Z Fold6',
            'ZFold6'
        ])
    elif base_model == 'Samsung Galaxy Z Fold7':
        aliases.update([
            'Samsung Galaxy Z Fold7',
            'Samsung Z Fold7',
            'Galaxy Z Fold7',
            'Samsung ZFold7',
            'Z Fold7',
            'ZFold7'
        ])
    
    # Apple iPhone series
    elif base_model.startswith('Apple iPhone'):
        # Extract model number and variant
        parts = base_model.split()
        if len(parts) >= 3:
            model_num = parts[2]  # e.g., "15"
            variant = ' '.join(parts[3:])  # e.g., "Pro Max"
            
            if variant == 'Pro Max':
                aliases.update([
                    f'Apple iPhone {model_num} Pro Max',
                    f'iPhone {model_num} Pro Max',
                    f'Apple iPhone{model_num} Pro Max',
                    f'iPhone{model_num} Pro Max',
                    f'i{model_num} Pro Max',
                    f'iPhone {model_num} ProMax'
                ])
            elif variant == 'Pro':
                aliases.update([
                    f'Apple iPhone {model_num} Pro',
                    f'iPhone {model_num} Pro',
                    f'Apple iPhone{model_num} Pro',
                    f'iPhone{model_num} Pro',
                    f'i{model_num} Pro'
                ])
            elif variant == 'Plus':
                aliases.update([
                    f'Apple iPhone {model_num} Plus',
                    f'iPhone {model_num} Plus',
                    f'Apple iPhone{model_num} Plus',
                    f'iPhone{model_num} Plus',
                    f'i{model_num} Plus',
                    f'iPhone {model_num}+'
                ])
            else:
                # Base model
                aliases.update([
                    f'Apple iPhone {model_num}',
                    f'iPhone {model_num}',
                    f'Apple iPhone{model_num}',
                    f'iPhone{model_num}',
                    f'i{model_num}'
                ])
    
    # Google Pixel series
    elif base_model == 'Google Pixel 9':
        aliases.update([
            'Google Pixel 9',
            'Pixel 9',
            'Google Pixel9',
            'Pixel9',
            'P9',
            'Pixel 9 5G'
        ])
    elif base_model == 'Google Pixel 9 Pro':
        aliases.update([
            'Google Pixel 9 Pro',
            'Pixel 9 Pro',
            'Google Pixel9 Pro',
            'Pixel9 Pro',
            'P9 Pro'
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
            'REVVL8 Pro'
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
            'REVVL7 Pro'
        ])
    
    # Motorola Razr series (folding phones)
    elif 'Motorola Razr' in base_model:
        if 'Ultra' in base_model:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Motorola Razr Ultra {year}',
                f'Moto Razr Ultra {year}',
                f'Razr Ultra {year}',
                f'Motorola Razr Ultra',
                f'Moto Razr Ultra',
                f'Razr Ultra'
            ])
        elif 'Razr+' in base_model:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Motorola Razr+ {year}',
                f'Moto Razr+ {year}',
                f'Razr+ {year}',
                f'Motorola Razr Plus {year}',
                f'Moto Razr Plus {year}',
                f'Razr Plus {year}',
                f'Motorola Razr+',
                f'Moto Razr+',
                f'Razr+',
                f'Motorola Razr Plus',
                f'Moto Razr Plus',
                f'Razr Plus'
            ])
        else:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Motorola Razr {year}',
                f'Moto Razr {year}',
                f'Razr {year}',
                f'Motorola Razr',
                f'Moto Razr',
                f'Razr'
            ])
    
    # Motorola Edge series
    elif 'Motorola Edge' in base_model:
        if 'Edge+' in base_model:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Motorola Edge+ {year}',
                f'Moto Edge+ {year}',
                f'Edge+ {year}',
                f'Motorola Edge Plus {year}',
                f'Moto Edge Plus {year}',
                f'Edge Plus {year}',
                f'Motorola Edge+',
                f'Moto Edge+',
                f'Edge+',
                f'Motorola Edge Plus',
                f'Moto Edge Plus',
                f'Edge Plus'
            ])
        else:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Motorola Edge {year}',
                f'Moto Edge {year}',
                f'Edge {year}',
                f'Motorola Edge',
                f'Moto Edge',
                f'Edge'
            ])
    
    # Moto G series
    elif 'Moto G' in base_model:
        if 'Power' in base_model:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Moto G Power {year}',
                f'Motorola G Power {year}',
                f'G Power {year}',
                f'Moto G Power',
                f'Motorola G Power',
                f'G Power'
            ])
        elif 'Stylus' in base_model:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Moto G Stylus {year}',
                f'Motorola G Stylus {year}',
                f'G Stylus {year}',
                f'Moto G Stylus',
                f'Motorola G Stylus',
                f'G Stylus'
            ])
        elif 'Play' in base_model:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Moto G Play {year}',
                f'Motorola G Play {year}',
                f'G Play {year}',
                f'Moto G Play',
                f'Motorola G Play',
                f'G Play'
            ])
        else:
            year = base_model.split()[-1]  # Extract year
            aliases.update([
                f'Moto G {year}',
                f'Motorola G {year}',
                f'G {year}',
                f'Moto G',
                f'Motorola G',
                f'G'
            ])
    
    # If no specific aliases found, use the base model itself
    if not aliases:
        aliases.add(base_model)
    
    return list(aliases)

if __name__ == "__main__":
    create_comprehensive_mapping()
