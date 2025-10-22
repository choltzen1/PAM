#!/usr/bin/env python
"""Test the email formatting with promo details"""
from dotenv import load_dotenv
load_dotenv()

from data.storage import PromoDataManager

# Get a promo code to test with
dm = PromoDataManager()
all_promos = dm.get_all_promos()

if all_promos:
    first_promo_code = list(all_promos.keys())[0]
    promo_data = all_promos[first_promo_code]
    
    print("✓ Sample Promo Data:")
    print(f"  Code: {first_promo_code}")
    print(f"  Name: {promo_data.get('bill_facing_name', 'N/A')}")
    print(f"  Version: {promo_data.get('version_number', promo_data.get('version', '1'))}")
    
    # Simulate the email formatting
    bill_facing_name = promo_data.get('bill_facing_name', 'Unknown')
    version_number = promo_data.get('version_number', promo_data.get('version', '1'))
    desired_execution = 'Device Finance & Revenue Accounting'
    
    subject = f'{desired_execution} Approval request - {first_promo_code} - {bill_facing_name} - Version #{version_number}'
    body = f'''Hello All,

Please review and provide {desired_execution.lower()} for {first_promo_code} - {bill_facing_name} - Version #{version_number}.

PDT - Promotions Delivery Tool

Please provide approval prior to {promo_data.get('approval_date', 'the specified deadline')}. Please let me know if there are any questions and concerns.

Thank you!'''
    
    print(f"\n✓ Formatted Email:\n")
    print(f"Subject: {subject}")
    print(f"\nBody:\n{body}")
    
else:
    print("✗ No promos found in database")
