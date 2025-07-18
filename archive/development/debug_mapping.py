import pandas as pd

# Debug the mapping file
df = pd.read_csv('device_alias_mapping.csv')
print("Total rows in mapping:", len(df))
print("\nFirst few rows:")
print(df.head())
print("\nLooking for 'pixel 9a':")
pixel_matches = df[df['marketing_alias'].str.contains('pixel 9a', case=False, na=False)]
print(pixel_matches)
print("\nNormalized test:")
df['marketing_alias_norm'] = df['marketing_alias'].str.strip().str.lower()
print("Looking for 'pixel 9a' normalized:")
pixel_matches_norm = df[df['marketing_alias_norm'] == 'pixel 9a']
print(pixel_matches_norm)
