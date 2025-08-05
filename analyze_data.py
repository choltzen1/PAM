import json
import time
import os

def analyze_promo_data():
    """Analyze the promotion data to identify potential bottlenecks"""
    
    print("Analyzing promotion data for performance bottlenecks...")
    print("="*80)
    
    # Load the promotions data
    try:
        with open('data/promotions.json', 'r') as f:
            all_promos = json.load(f)
    except Exception as e:
        print(f"Error loading promotions.json: {e}")
        return
    
    print(f"Total promotions: {len(all_promos)}")
    
    # Analyze data size and complexity
    total_fields = 0
    large_promos = []
    file_analysis = []
    
    for promo_code, promo_data in all_promos.items():
        field_count = len(promo_data)
        total_fields += field_count
        
        if field_count > 50:  # Flag promos with many fields
            large_promos.append((promo_code, field_count))
        
        # Check for uploaded files
        upload_dir = os.path.join('data', 'uploads', 'promotions', promo_code)
        if os.path.exists(upload_dir):
            files = []
            total_size = 0
            
            for file in os.listdir(upload_dir):
                file_path = os.path.join(upload_dir, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    total_size += size
                    files.append((file, size))
            
            if files:
                file_analysis.append((promo_code, files, total_size))
    
    avg_fields = total_fields / len(all_promos) if all_promos else 0
    
    print(f"Average fields per promo: {avg_fields:.1f}")
    print(f"Promos with many fields (>50): {len(large_promos)}")
    
    if large_promos:
        print("\nLargest promotions by field count:")
        for promo_code, field_count in sorted(large_promos, key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {promo_code}: {field_count} fields")
    
    print(f"\nPromos with uploaded files: {len(file_analysis)}")
    
    if file_analysis:
        print("\nFile analysis:")
        total_file_size = 0
        largest_files = []
        
        for promo_code, files, total_size in file_analysis:
            total_file_size += total_size
            print(f"  {promo_code}: {len(files)} files, {total_size:,} bytes")
            
            for file, size in files:
                if size > 50000:  # Files larger than 50KB
                    largest_files.append((promo_code, file, size))
                print(f"    {file}: {size:,} bytes")
        
        print(f"\nTotal file storage: {total_file_size:,} bytes")
        
        if largest_files:
            print("\nLarge files (>50KB):")
            for promo_code, file, size in sorted(largest_files, key=lambda x: x[2], reverse=True):
                print(f"  {promo_code}/{file}: {size:,} bytes")
    
    # Analyze specific promo fields that could cause slowdowns
    print("\n" + "="*80)
    print("POTENTIAL BOTTLENECK ANALYSIS")
    print("="*80)
    
    # Sample a few promos for detailed analysis
    sample_promos = list(all_promos.items())[:3]
    
    for promo_code, promo_data in sample_promos:
        print(f"\nDetailed analysis for {promo_code}:")
        print(f"  Total fields: {len(promo_data)}")
        
        # Check for complex fields
        large_fields = []
        for key, value in promo_data.items():
            if isinstance(value, str) and len(value) > 500:
                large_fields.append((key, len(value)))
        
        if large_fields:
            print("  Large text fields:")
            for field, length in large_fields:
                print(f"    {field}: {length:,} characters")
        
        # Check for trade-in or tiered data
        trade_fields = [k for k in promo_data.keys() if 'trade' in k.lower()]
        tier_fields = [k for k in promo_data.keys() if 'tier' in k.lower()]
        
        if trade_fields:
            print(f"  Trade-in fields: {len(trade_fields)}")
        if tier_fields:
            print(f"  Tier fields: {len(tier_fields)}")
        
        # Check for file references
        file_fields = [k for k in promo_data.keys() if 'file' in k.lower() or 'excel' in k.lower()]
        if file_fields:
            print(f"  File-related fields: {len(file_fields)}")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    # Provide recommendations based on analysis
    if len(file_analysis) > 10:
        print("⚠️  Many promotions have uploaded files - file I/O could be a bottleneck")
    
    large_files_exist = any(total_size > 100000 for _, _, total_size in file_analysis)
    if large_files_exist:
        print("⚠️  Some Excel files are very large - consider file size limits or lazy loading")
    
    if avg_fields > 60:
        print("⚠️  Promotions have many fields - consider data structure optimization")
    
    if len(all_promos) > 100:
        print("⚠️  Large number of promotions - consider pagination or lazy loading")
    
    print("\n✅ Analysis complete. Run the app and check browser developer tools for frontend performance.")

if __name__ == "__main__":
    os.chdir('c:/Users/CHoltze1/Documents/promo-app')
    analyze_promo_data()
