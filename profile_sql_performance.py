import cProfile
import pstats
import time
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.abspath('.'))

from data.storage import PromoDataManager
from promo.builders import generate_promo_eligibility_sql

def profile_sql_generation():
    """Profile SQL generation to identify bottlenecks"""
    
    # Initialize data manager
    data_manager = PromoDataManager()
    
    # Get all promos to test with
    all_promos = data_manager.get_all_promos()
    
    if not all_promos:
        print("No promotions found to profile!")
        return
    
    # Get a sample promo for profiling
    sample_promo_code = list(all_promos.keys())[0]
    sample_promo_data = all_promos[sample_promo_code]
    
    print(f"Profiling SQL generation for promo: {sample_promo_code}")
    print(f"Promo data size: {len(sample_promo_data)} fields")
    
    # Profile the SQL generation function
    profiler = cProfile.Profile()
    
    # Time the overall execution
    start_time = time.time()
    
    profiler.enable()
    sql_result = generate_promo_eligibility_sql(sample_promo_data)
    profiler.disable()
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\nTotal execution time: {total_time:.4f} seconds")
    print(f"Generated SQL length: {len(sql_result)} characters")
    
    # Save profile results
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    
    # Print top time-consuming functions
    print("\n" + "="*80)
    print("TOP TIME-CONSUMING FUNCTIONS")
    print("="*80)
    stats.print_stats(20)  # Top 20 functions
    
    # Save detailed profile to file
    profile_filename = f"sql_generation_profile_{int(time.time())}.prof"
    stats.dump_stats(profile_filename)
    print(f"\nDetailed profile saved to: {profile_filename}")
    
    return {
        'total_time': total_time,
        'sql_length': len(sql_result),
        'promo_code': sample_promo_code,
        'promo_data_size': len(sample_promo_data)
    }

def analyze_data_volume():
    """Analyze the volume of data being processed"""
    
    data_manager = PromoDataManager()
    all_promos = data_manager.get_all_promos()
    
    print("\n" + "="*80)
    print("DATA VOLUME ANALYSIS")
    print("="*80)
    
    print(f"Total number of promotions: {len(all_promos)}")
    
    # Analyze each promo
    for promo_code, promo_data in list(all_promos.items())[:5]:  # Analyze first 5 promos
        print(f"\nPromo: {promo_code}")
        print(f"  Fields: {len(promo_data)}")
        
        # Check for uploaded files
        upload_dir = os.path.join('data', 'uploads', 'promotions', promo_code)
        if os.path.exists(upload_dir):
            files = os.listdir(upload_dir)
            print(f"  Uploaded files: {len(files)}")
            
            for file in files:
                file_path = os.path.join(upload_dir, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    print(f"    {file}: {size:,} bytes")
        
        # Check for large field values
        large_fields = []
        for key, value in promo_data.items():
            if isinstance(value, str) and len(value) > 1000:
                large_fields.append((key, len(value)))
        
        if large_fields:
            print(f"  Large fields:")
            for field, size in large_fields:
                print(f"    {field}: {size:,} characters")

def profile_individual_functions():
    """Profile individual SQL generation functions"""
    
    data_manager = PromoDataManager()
    all_promos = data_manager.get_all_promos()
    
    if not all_promos:
        print("No promotions found!")
        return
    
    sample_promo_data = list(all_promos.values())[0]
    
    print("\n" + "="*80)
    print("INDIVIDUAL FUNCTION PROFILING")
    print("="*80)
    
    # Import the function components
    from promo.builders import generate_promo_eligibility_sql
    
    # We'll need to modify the builders.py to extract individual functions for profiling
    # For now, let's time the main function multiple times
    
    times = []
    for i in range(5):
        start_time = time.time()
        sql_result = generate_promo_eligibility_sql(sample_promo_data)
        end_time = time.time()
        execution_time = end_time - start_time
        times.append(execution_time)
        print(f"Run {i+1}: {execution_time:.4f} seconds")
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"\nAverage time: {avg_time:.4f} seconds")
    print(f"Min time: {min_time:.4f} seconds")
    print(f"Max time: {max_time:.4f} seconds")
    print(f"Time variance: {max_time - min_time:.4f} seconds")

if __name__ == "__main__":
    print("Starting SQL Generation Performance Analysis")
    print("="*80)
    
    try:
        # 1. Profile overall SQL generation
        result = profile_sql_generation()
        
        # 2. Analyze data volume
        analyze_data_volume()
        
        # 3. Profile individual functions
        profile_individual_functions()
        
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total execution time: {result['total_time']:.4f} seconds")
        print(f"SQL output size: {result['sql_length']:,} characters")
        print(f"Tested promo: {result['promo_code']}")
        
        if result['total_time'] > 5.0:
            print("⚠️  WARNING: SQL generation is taking longer than 5 seconds!")
        elif result['total_time'] > 2.0:
            print("⚠️  NOTICE: SQL generation is taking longer than 2 seconds")
        else:
            print("✅ SQL generation performance appears acceptable")
        
    except Exception as e:
        print(f"Error during profiling: {str(e)}")
        import traceback
        traceback.print_exc()
