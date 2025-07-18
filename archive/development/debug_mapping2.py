import pandas as pd

# Test the exact load_mapping function
def load_mapping(mapping_file):
    df = pd.read_csv(mapping_file)
    # Normalize alias for case-insensitive matching
    df['marketing_alias_norm'] = df['marketing_alias'].str.strip().str.lower()
    return df.groupby('marketing_alias_norm')['manufacturer_name'].apply(list).to_dict()

mapping = load_mapping('device_alias_mapping.csv')
print("Total mappings:", len(mapping))
print("Looking for 'pixel 9a':")
result = mapping.get('pixel 9a')
print(result)
