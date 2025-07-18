import pandas as pd

SKU_TYPES = {'A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'}
BRANDS = {'Tmobile', 'Sprint', 'Universal'}

def filter_excel(excel_file):
    df = pd.read_excel(excel_file, header=7)
    df.columns = [str(c).strip() for c in df.columns]
    print("Columns:", df.columns.tolist())
    print("Total rows before filtering:", len(df))
    df = df[df['SKU Type'].isin(SKU_TYPES) & df['Handset Brand'].isin(BRANDS)]
    print("Total rows after filtering:", len(df))
    return df

df = filter_excel('Z0MATERIAL_ATTRB_REP01_00000.xlsx')
print("Looking for 'GGL PIXEL 9A' in Model(External):")
pixel_in_excel = df[df['Model(External)'].str.contains('GGL PIXEL 9A', case=False, na=False)]
print(pixel_in_excel['Model(External)'].unique())
