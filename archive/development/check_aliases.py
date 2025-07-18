import pandas as pd

df = pd.read_csv('device_alias_mapping.csv')

# Check Samsung S24 related aliases
s24_aliases = df[df['marketing_alias'].str.contains('S24', case=False, na=False)]
print('Samsung S24 related aliases:')
for _, row in s24_aliases.head(20).iterrows():
    print(f'  {row["marketing_alias"]} -> {row["manufacturer_name"]}')
print('...')
print(f'Total S24 aliases: {len(s24_aliases)}')

print('\n' + '='*50 + '\n')

# Check Razr related aliases
razr_aliases = df[df['marketing_alias'].str.contains('Razr', case=False, na=False)]
print('Razr related aliases:')
for _, row in razr_aliases.head(20).iterrows():
    print(f'  {row["marketing_alias"]} -> {row["manufacturer_name"]}')
print('...')
print(f'Total Razr aliases: {len(razr_aliases)}')

print('\n' + '='*50 + '\n')

# Check iPhone 15 related aliases
iphone15_aliases = df[df['marketing_alias'].str.contains('iPhone 15', case=False, na=False)]
print('iPhone 15 related aliases:')
for _, row in iphone15_aliases.head(20).iterrows():
    print(f'  {row["marketing_alias"]} -> {row["manufacturer_name"]}')
print('...')
print(f'Total iPhone 15 aliases: {len(iphone15_aliases)}')
