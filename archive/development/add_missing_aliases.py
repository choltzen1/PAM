import pandas as pd

# Add comprehensive marketing aliases based on real-world usage
missing_aliases = [
    # Samsung Galaxy S24 series
    ('Samsung Galaxy S24', 'SAM S921U GS24 5G EUREKA1 128G'),
    ('Samsung S24', 'SAM S921U GS24 5G EUREKA1 128G'),
    ('Galaxy S24', 'SAM S921U GS24 5G EUREKA1 128G'),
    ('Samsung GS24', 'SAM S921U GS24 5G EUREKA1 128G'),
    ('GS24', 'SAM S921U GS24 5G EUREKA1 128G'),
    ('S24', 'SAM S921U GS24 5G EUREKA1 128G'),
    
    ('Samsung Galaxy S24+', 'SAM S926U GS24+ 5G EUREKA2 256'),
    ('Samsung S24+', 'SAM S926U GS24+ 5G EUREKA2 256'),
    ('Galaxy S24+', 'SAM S926U GS24+ 5G EUREKA2 256'),
    ('Samsung S24 Plus', 'SAM S926U GS24+ 5G EUREKA2 256'),
    ('Galaxy S24 Plus', 'SAM S926U GS24+ 5G EUREKA2 256'),
    ('S24+', 'SAM S926U GS24+ 5G EUREKA2 256'),
    ('S24 Plus', 'SAM S926U GS24+ 5G EUREKA2 256'),
    
    ('Samsung Galaxy S24 Ultra', 'SAM S928U GS24 ULT 5G EU3 256G'),
    ('Samsung S24 Ultra', 'SAM S928U GS24 ULT 5G EU3 256G'),
    ('Galaxy S24 Ultra', 'SAM S928U GS24 ULT 5G EU3 256G'),
    ('Samsung S24U', 'SAM S928U GS24 ULT 5G EU3 256G'),
    ('S24 Ultra', 'SAM S928U GS24 ULT 5G EU3 256G'),
    ('S24U', 'SAM S928U GS24 ULT 5G EU3 256G'),
    
    # Samsung Galaxy S25 series
    ('Samsung Galaxy S25', 'SAM S931U GS25 5G 128G'),
    ('Samsung S25', 'SAM S931U GS25 5G 128G'),
    ('Galaxy S25', 'SAM S931U GS25 5G 128G'),
    ('Samsung GS25', 'SAM S931U GS25 5G 128G'),
    ('GS25', 'SAM S931U GS25 5G 128G'),
    ('S25', 'SAM S931U GS25 5G 128G'),
    
    ('Samsung Galaxy S25+', 'SAM S936U GS25+ 5G 256G'),
    ('Samsung S25+', 'SAM S936U GS25+ 5G 256G'),
    ('Galaxy S25+', 'SAM S936U GS25+ 5G 256G'),
    ('Samsung S25 Plus', 'SAM S936U GS25+ 5G 256G'),
    ('Galaxy S25 Plus', 'SAM S936U GS25+ 5G 256G'),
    ('S25+', 'SAM S936U GS25+ 5G 256G'),
    ('S25 Plus', 'SAM S936U GS25+ 5G 256G'),
    
    ('Samsung Galaxy S25 Ultra', 'SAM S938U GS25 ULT 5G 256G'),
    ('Samsung S25 Ultra', 'SAM S938U GS25 ULT 5G 256G'),
    ('Galaxy S25 Ultra', 'SAM S938U GS25 ULT 5G 256G'),
    ('Samsung S25U', 'SAM S938U GS25 ULT 5G 256G'),
    ('S25 Ultra', 'SAM S938U GS25 ULT 5G 256G'),
    ('S25U', 'SAM S938U GS25 ULT 5G 256G'),
    
    # Samsung Z Flip series
    ('Samsung Galaxy Z Flip6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Samsung Z Flip6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Galaxy Z Flip6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Samsung Flip6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Galaxy Flip6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Z Flip6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Flip6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Samsung Galaxy Z Flip 6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Galaxy Z Flip 6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Samsung Flip 6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Z Flip 6', 'SAM F741U Z FLIP6 5G B6 256G'),
    ('Flip 6', 'SAM F741U Z FLIP6 5G B6 256G'),
    
    ('Samsung Galaxy Z Flip7', 'SAM F766U Z FLIP7 256G'),
    ('Samsung Z Flip7', 'SAM F766U Z FLIP7 256G'),
    ('Galaxy Z Flip7', 'SAM F766U Z FLIP7 256G'),
    ('Samsung Flip7', 'SAM F766U Z FLIP7 256G'),
    ('Galaxy Flip7', 'SAM F766U Z FLIP7 256G'),
    ('Z Flip7', 'SAM F766U Z FLIP7 256G'),
    ('Flip7', 'SAM F766U Z FLIP7 256G'),
    ('Samsung Galaxy Z Flip 7', 'SAM F766U Z FLIP7 256G'),
    ('Galaxy Z Flip 7', 'SAM F766U Z FLIP7 256G'),
    ('Samsung Flip 7', 'SAM F766U Z FLIP7 256G'),
    ('Z Flip 7', 'SAM F766U Z FLIP7 256G'),
    ('Flip 7', 'SAM F766U Z FLIP7 256G'),
    
    # Samsung Z Fold series
    ('Samsung Galaxy Z Fold6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Samsung Z Fold6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Galaxy Z Fold6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Samsung Fold6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Galaxy Fold6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Z Fold6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Fold6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Samsung Galaxy Z Fold 6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Galaxy Z Fold 6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Samsung Fold 6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Z Fold 6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    ('Fold 6', 'SAM F956U Z FOLD6 5G Q6 256G'),
    
    ('Samsung Galaxy Z Fold7', 'SAM F966U Z FOLD7 256G'),
    ('Samsung Z Fold7', 'SAM F966U Z FOLD7 256G'),
    ('Galaxy Z Fold7', 'SAM F966U Z FOLD7 256G'),
    ('Samsung Fold7', 'SAM F966U Z FOLD7 256G'),
    ('Galaxy Fold7', 'SAM F966U Z FOLD7 256G'),
    ('Z Fold7', 'SAM F966U Z FOLD7 256G'),
    ('Fold7', 'SAM F966U Z FOLD7 256G'),
    ('Samsung Galaxy Z Fold 7', 'SAM F966U Z FOLD7 256G'),
    ('Galaxy Z Fold 7', 'SAM F966U Z FOLD7 256G'),
    ('Samsung Fold 7', 'SAM F966U Z FOLD7 256G'),
    ('Z Fold 7', 'SAM F966U Z FOLD7 256G'),
    ('Fold 7', 'SAM F966U Z FOLD7 256G'),
    
    # Google Pixel series
    ('Google Pixel 9', 'GGL PIXEL 9 5G TK4 128G'),
    ('Pixel 9', 'GGL PIXEL 9 5G TK4 128G'),
    ('Google Pixel9', 'GGL PIXEL 9 5G TK4 128G'),
    ('Pixel9', 'GGL PIXEL 9 5G TK4 128G'),
    ('P9', 'GGL PIXEL 9 5G TK4 128G'),
    
    ('Google Pixel 9 Pro', 'GGL PIXEL 9 PRO 5G CM4 256G'),
    ('Pixel 9 Pro', 'GGL PIXEL 9 PRO 5G CM4 256G'),
    ('Google Pixel9 Pro', 'GGL PIXEL 9 PRO 5G CM4 256G'),
    ('Pixel9 Pro', 'GGL PIXEL 9 PRO 5G CM4 256G'),
    ('P9 Pro', 'GGL PIXEL 9 PRO 5G CM4 256G'),
    ('Pixel 9Pro', 'GGL PIXEL 9 PRO 5G CM4 256G'),
    
    ('Google Pixel 9 Pro XL', 'GGL PIXEL 9 PRO XL 5G KM4 256G'),
    ('Pixel 9 Pro XL', 'GGL PIXEL 9 PRO XL 5G KM4 256G'),
    ('Google Pixel9 Pro XL', 'GGL PIXEL 9 PRO XL 5G KM4 256G'),
    ('Pixel9 Pro XL', 'GGL PIXEL 9 PRO XL 5G KM4 256G'),
    ('P9 Pro XL', 'GGL PIXEL 9 PRO XL 5G KM4 256G'),
    ('Pixel 9 ProXL', 'GGL PIXEL 9 PRO XL 5G KM4 256G'),
    
    ('Google Pixel 9a', 'GGL PIXEL 9A 128G'),
    ('Pixel 9a', 'GGL PIXEL 9A 128G'),
    ('Google Pixel9a', 'GGL PIXEL 9A 128G'),
    ('Pixel9a', 'GGL PIXEL 9A 128G'),
    ('P9a', 'GGL PIXEL 9A 128G'),
    ('Pixel 9A', 'GGL PIXEL 9A 128G'),
    ('Google Pixel 9A', 'GGL PIXEL 9A 128G'),
    
    # iPhone series
    ('iPhone 16', 'APL IPHONE 16 128G'),
    ('Apple iPhone 16', 'APL IPHONE 16 128G'),
    ('iPhone16', 'APL IPHONE 16 128G'),
    ('i16', 'APL IPHONE 16 128G'),
    
    ('iPhone 16 Pro', 'APL IPHONE 16 PRO 128G'),
    ('Apple iPhone 16 Pro', 'APL IPHONE 16 PRO 128G'),
    ('iPhone16 Pro', 'APL IPHONE 16 PRO 128G'),
    ('i16 Pro', 'APL IPHONE 16 PRO 128G'),
    ('iPhone 16Pro', 'APL IPHONE 16 PRO 128G'),
    
    ('iPhone 16 Pro Max', 'APL IPHONE 16 PRO MAX 256G'),
    ('Apple iPhone 16 Pro Max', 'APL IPHONE 16 PRO MAX 256G'),
    ('iPhone16 Pro Max', 'APL IPHONE 16 PRO MAX 256G'),
    ('i16 Pro Max', 'APL IPHONE 16 PRO MAX 256G'),
    ('iPhone 16 ProMax', 'APL IPHONE 16 PRO MAX 256G'),
    
    ('iPhone 15', 'APL IPHONE 15 128G'),
    ('Apple iPhone 15', 'APL IPHONE 15 128G'),
    ('iPhone15', 'APL IPHONE 15 128G'),
    ('i15', 'APL IPHONE 15 128G'),
    
    ('iPhone 15 Pro', 'APL IPHONE 15 PRO 128G'),
    ('Apple iPhone 15 Pro', 'APL IPHONE 15 PRO 128G'),
    ('iPhone15 Pro', 'APL IPHONE 15 PRO 128G'),
    ('i15 Pro', 'APL IPHONE 15 PRO 128G'),
    ('iPhone 15Pro', 'APL IPHONE 15 PRO 128G'),
    
    ('iPhone 15 Pro Max', 'APL IPHONE 15 PRO MAX 256G'),
    ('Apple iPhone 15 Pro Max', 'APL IPHONE 15 PRO MAX 256G'),
    ('iPhone15 Pro Max', 'APL IPHONE 15 PRO MAX 256G'),
    ('i15 Pro Max', 'APL IPHONE 15 PRO MAX 256G'),
    ('iPhone 15 ProMax', 'APL IPHONE 15 PRO MAX 256G'),
    
    # T-Mobile REVVL series
    ('REVVL 8 Pro', 'TMO REVVL 8 PRO 5G 256G'),
    ('T-Mobile REVVL 8 Pro', 'TMO REVVL 8 PRO 5G 256G'),
    ('TMO REVVL 8 Pro', 'TMO REVVL 8 PRO 5G 256G'),
    ('REVVL8 Pro', 'TMO REVVL 8 PRO 5G 256G'),
    ('REVVL 8Pro', 'TMO REVVL 8 PRO 5G 256G'),
    
    ('REVVL 8', 'TMO REVVL 8 5G 128G'),
    ('T-Mobile REVVL 8', 'TMO REVVL 8 5G 128G'),
    ('TMO REVVL 8', 'TMO REVVL 8 5G 128G'),
    ('REVVL8', 'TMO REVVL 8 5G 128G'),
    
    ('REVVL 7 Pro', 'TMO REVVL 7 PRO 5G 256G'),
    ('T-Mobile REVVL 7 Pro', 'TMO REVVL 7 PRO 5G 256G'),
    ('TMO REVVL 7 Pro', 'TMO REVVL 7 PRO 5G 256G'),
    ('REVVL7 Pro', 'TMO REVVL 7 PRO 5G 256G'),
    ('REVVL 7Pro', 'TMO REVVL 7 PRO 5G 256G'),
    
    ('REVVL 7', 'TMO REVVL 7 5G 128G'),
    ('T-Mobile REVVL 7', 'TMO REVVL 7 5G 128G'),
    ('TMO REVVL 7', 'TMO REVVL 7 5G 128G'),
    ('REVVL7', 'TMO REVVL 7 5G 128G'),
]

# Load existing mapping
df = pd.read_csv('device_alias_mapping.csv')

# Add missing aliases
for alias, manufacturer in missing_aliases:
    new_row = pd.DataFrame({'marketing_alias': [alias], 'manufacturer_name': [manufacturer]})
    df = pd.concat([df, new_row], ignore_index=True)

# Save updated mapping
df.to_csv('device_alias_mapping.csv', index=False)
print(f"Added {len(missing_aliases)} missing aliases for Samsung Flip 7")
