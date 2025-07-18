import pandas as pd

df = pd.read_excel('Z0MATERIAL_ATTRB_REP01_00000.xlsx', header=7)
df.columns = [str(c).strip() for c in df.columns]

print("Unique SKU Type values:")
print(df['SKU Type'].value_counts())
print("\nUnique Handset Brand values:")
print(df['Handset Brand'].value_counts())
