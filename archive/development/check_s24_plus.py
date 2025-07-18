import pandas as pd

# Check current S24+ aliases
df = pd.read_csv('device_alias_mapping.csv')
s24_plus_aliases = df[df['marketing_alias'].str.contains('S24\\+', case=False, na=False, regex=True)]
print('Current S24+ aliases:')
for _, row in s24_plus_aliases.iterrows():
    print(f'  {row["marketing_alias"]} -> {row["manufacturer_name"]}')
print(f'\nTotal S24+ aliases: {len(s24_plus_aliases)}')

print('\n' + '='*60 + '\n')

# Check what S24+ devices exist in Excel
excel_df = pd.read_excel('Z0MATERIAL_ATTRB_REP01_00000.xlsx', header=7)
filtered_df = excel_df[
    (excel_df['SKU Type'].isin(['A-STOCK', 'WARRANTY', 'PRWARRANTY', 'REFURB SKU'])) &
    (excel_df['Handset Brand'].isin(['T-MOBILE', 'SPRINT', 'UNIVERSAL']))
]

s24_plus_devices = filtered_df[filtered_df['Model(External)'].str.contains('S926U GS24\\+', na=False, regex=True)]
unique_s24_plus = s24_plus_devices['Model(External)'].unique()

print('All S24+ devices in Excel:')
for device in unique_s24_plus:
    print(f'  {device}')
print(f'\nTotal S24+ device variants: {len(unique_s24_plus)}')
