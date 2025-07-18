import pandas as pd
import sys

EXCEL_FILE = 'Z0MATERIAL_ATTRB_REP01_00000.xlsx'
MAPPING_FILE = 'device_alias_mapping.csv'
SKU_TYPES = {'A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'}
BRANDS = {'T-MOBILE', 'SPRINT', 'UNIVERSAL'}

def load_mapping(mapping_file):
    df = pd.read_csv(mapping_file)
    # Normalize alias for case-insensitive matching
    df['marketing_alias_norm'] = df['marketing_alias'].str.strip().str.lower()
    return df.groupby('marketing_alias_norm')['manufacturer_name'].apply(list).to_dict()

def filter_excel(excel_file):
    df = pd.read_excel(excel_file, header=7)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df['SKU Type'].isin(SKU_TYPES) & df['Handset Brand'].isin(BRANDS)]
    return df

def match_and_export(input_aliases, mapping, df, export_file='matched_devices.csv'):
    all_matches = pd.DataFrame()
    for alias in input_aliases:
        key = alias.strip().lower()
        manufacturer_names = mapping.get(key)
        if manufacturer_names:
            for mname in manufacturer_names:
                matches = df[df['Model(External)'].str.strip().str.lower() == mname.strip().lower()]
                if not matches.empty:
                    all_matches = pd.concat([all_matches, matches], ignore_index=True)
        else:
            print(f"No mapping found for alias: {alias}")
    if not all_matches.empty:
        all_matches.to_csv(export_file, index=False)
        print(f"Exported {len(all_matches)} rows to {export_file}")
    else:
        print("No matches found for the given aliases.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python device_matcher.py \"alias1,alias2,...\"")
        sys.exit(1)
    input_aliases = [a.strip() for a in sys.argv[1].split(',')]
    mapping = load_mapping(MAPPING_FILE)
    df = filter_excel(EXCEL_FILE)
    match_and_export(input_aliases, mapping, df)
