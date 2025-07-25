#!/usr/bin/env python3
"""
Test script to demonstrate the date fixing for SQL generation.
Shows the before/after behavior of date handling.
"""

from datetime import datetime, timedelta

def fmt_date_old(date_str, is_end_date=False):
    """Old date formatting function that had the bug"""
    if not date_str:
        return 'NULL'
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        if is_end_date:
            # OLD BUG: Added one day and set time to 05:00:00
            date_obj = date_obj + timedelta(days=1)
            time_str = '05:00:00'
        else:
            # OLD BUG: Used same date with 20:00:00
            time_str = '20:00:00'
        
        formatted_date = date_obj.strftime('%Y-%m-%d')
        return f"to_date('{formatted_date} {time_str}','YYYY-MM-DD HH24:MI:SS')"
    except ValueError:
        return 'NULL'

def fmt_date_new(date_str, date_type='display'):
    """
    NEW FIXED date formatting function:
    - 'display': Use exact date with 20:00:00 (for DISPLAY_PROMO_START_DATE, DISPLAY_PROMO_END_DATE)
    - 'start': Subtract one day and use 20:00:00 (for PROMO_START_DATE, EFFECTIVE_DATE)
    - 'end': Add one day and use 05:00:00 (for PROMO_END_DATE, EXPIRATION_DATE)
    """
    if not date_str:
        return 'NULL'
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        if date_type == 'start':
            # For start dates: subtract one day and set time to 20:00:00
            date_obj = date_obj - timedelta(days=1)
            time_str = '20:00:00'
        elif date_type == 'end':
            # For end dates: add one day and set time to 05:00:00
            date_obj = date_obj + timedelta(days=1)
            time_str = '05:00:00'
        else:  # 'display' or default
            # For display dates: use exact date with 20:00:00
            time_str = '20:00:00'
        
        formatted_date = date_obj.strftime('%Y-%m-%d')
        return f"to_date('{formatted_date} {time_str}','YYYY-MM-DD HH24:MI:SS')"
    except ValueError:
        return 'NULL'

def test_date_conversion():
    # Test with sample dates from your promotion
    promo_start = "2025-07-01"
    promo_end = "2025-08-01"
    
    print("=== DATE CONVERSION TEST ===")
    print(f"Form Input: Start Date = {promo_start}, End Date = {promo_end}")
    print()
    
    print("OLD BEHAVIOR (Before Fix):")
    print(f"  PROMO_START_DATE:        {fmt_date_old(promo_start, False)}")
    print(f"  PROMO_END_DATE:          {fmt_date_old(promo_end, True)}")
    print(f"  EFFECTIVE_DATE:          {fmt_date_old(promo_start, False)}")
    print(f"  EXPIRATION_DATE:         {fmt_date_old(promo_end, True)}")
    print(f"  DISPLAY_PROMO_START_DATE: {fmt_date_old(promo_start, False)}")
    print(f"  DISPLAY_PROMO_END_DATE:   {fmt_date_old(promo_end, True)}")
    print()
    
    print("NEW BEHAVIOR (After Fix):")
    print(f"  PROMO_START_DATE:        {fmt_date_new(promo_start, 'start')}")
    print(f"  PROMO_END_DATE:          {fmt_date_new(promo_end, 'end')}")
    print(f"  EFFECTIVE_DATE:          {fmt_date_new(promo_start, 'start')}")
    print(f"  EXPIRATION_DATE:         {fmt_date_new(promo_end, 'end')}")
    print(f"  DISPLAY_PROMO_START_DATE: {fmt_date_new(promo_start, 'display')}")
    print(f"  DISPLAY_PROMO_END_DATE:   {fmt_date_new(promo_end, 'display')}")
    print()
    
    print("SUMMARY OF CHANGES:")
    print("- PROMO_START_DATE & EFFECTIVE_DATE: Now one day EARLIER with 20:00:00")
    print("- PROMO_END_DATE & EXPIRATION_DATE: Now one day LATER with 05:00:00") 
    print("- DISPLAY dates: Now use EXACT dates with 20:00:00")

if __name__ == "__main__":
    test_date_conversion()
