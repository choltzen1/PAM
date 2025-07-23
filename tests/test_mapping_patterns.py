#!/usr/bin/env python3
"""
Test device mapping patterns to see how they work
"""

import sys
import os
sys.path.append('.')

def test_device_mappings():
    """Test how devices get mapped"""
    
    # Import the mapping function
    from core.create_correct_comprehensive_mapping import get_base_model
    
    # Test devices
    test_devices = [
        "iPhone 16 Pro",
        "Samsung Galaxy S24",
        "Google Pixel 9", 
        "Motorola Edge 2024",
        "iPhone 15 Plus",
        "Galaxy S24 Ultra",
        "Pixel 8 Pro",
        "OnePlus 12",
        "Moto Razr 2024",
        "iPhone 16 Pro Max",
        # Add some edge cases
        "APL IPHONE 16 PRO 128G BLK",
        "SAMSUNG GALAXY S24 ULTRA 512GB",
        "GOOGLE PIXEL 9 PRO 256GB",
        "MOTOROLA MOTO G POWER 2024 64GB",
        "ONEPLUS 12 PRO 512GB FLOWY EMERALD"
    ]
    
    print("🧪 DEVICE MAPPING TEST RESULTS")
    print("=" * 60)
    print(f"{'Device Name':<40} {'Mapped To':<20} {'Status'}")
    print("-" * 60)
    
    mappable_count = 0
    unmappable_count = 0
    
    for device in test_devices:
        try:
            mapped_result = get_base_model(device)
            
            # Check if it's mappable (mapped result is different from input)
            if mapped_result != device:
                status = "✅ Mappable"
                mappable_count += 1
            else:
                status = "⚠️ Unmappable"
                unmappable_count += 1
            
            # Truncate long names for display
            device_display = device[:38] + ".." if len(device) > 40 else device
            mapped_display = mapped_result[:18] + ".." if len(mapped_result) > 20 else mapped_result
            
            print(f"{device_display:<40} {mapped_display:<20} {status}")
            
        except Exception as e:
            print(f"{device[:38]:<40} {'ERROR':<20} ❌ Error: {e}")
            unmappable_count += 1
    
    print("-" * 60)
    print(f"📊 SUMMARY:")
    print(f"   ✅ Mappable devices: {mappable_count}")
    print(f"   ⚠️ Unmappable devices: {unmappable_count}")
    print(f"   📈 Success rate: {mappable_count/(mappable_count+unmappable_count)*100:.1f}%")
    
    print(f"\n💡 INTERPRETATION:")
    print(f"   • Mappable = System knows how to handle this device")
    print(f"   • Unmappable = Needs manual attention/new patterns")
    print(f"   • High success rate = Good coverage of device types")

if __name__ == "__main__":
    test_device_mappings()
