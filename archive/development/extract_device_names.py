import pandas as pd

EXCEL_FILE = 'Z0MATERIAL_ATTRB_REP01_00000.xlsx'
SKU_TYPES = {'A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'}
BRANDS = {'Tmobile', 'Sprint', 'Universal'}

# Load and filter the Excel file
def get_unique_device_names():
    df = pd.read_excel(EXCEL_FILE, header=7)
    df.columns = [str(c).strip() for c in df.columns]
    print('Available columns:', list(df.columns))
    # Uncomment the next line after identifying the correct column names
    # df = df[df['SKU TYPE'].isin(SKU_TYPES) & df['Handset brand'].isin(BRANDS)]
    # Use only 'Model(External)' as the device name column
    device_col = 'Model(External)'
    if device_col not in df.columns:
        raise Exception(f"Column '{device_col}' not found in Excel file! Available columns: {list(df.columns)}")
    unique_names = sorted(df[device_col].dropna().unique())
    print(f"Found {len(unique_names)} unique device names in column '{device_col}'")
    for name in unique_names:
        print(name)

if __name__ == "__main__":
    get_unique_device_names()
