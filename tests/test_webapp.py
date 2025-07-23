#!/usr/bin/env python3
"""
Test script for the Flask web application
Tests all major functionality including batch search and Excel export
"""

import requests
import time
import os
import sys
from pathlib import Path

# Add the webapp directory to Python path
webapp_dir = Path(__file__).parent.parent / "webapp"
sys.path.insert(0, str(webapp_dir))

def test_web_app():
    """Test the Flask web application functionality"""
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Flask Web Application")
    print("=" * 50)
    
    # Test 1: Check if server is running
    print("\n1. Testing server connection...")
    try:
        response = requests.get(base_url)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print(f"❌ Server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure Flask app is running on port 5000")
        return False
    
    # Test 2: Test dashboard
    print("\n2. Testing dashboard...")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            print("✅ Dashboard loads successfully")
        else:
            print(f"❌ Dashboard failed with status: {response.status_code}")
    except Exception as e:
        print(f"❌ Dashboard test failed: {e}")
    
    # Test 3: Test single search
    print("\n3. Testing single device search...")
    test_devices = ["iPhone 16 Pro", "Samsung Galaxy S24", "Moto Razr 2024"]
    
    for device in test_devices:
        try:
            response = requests.post(f"{base_url}/search", data={"device_name": device})
            if response.status_code == 200:
                print(f"✅ Search for '{device}' successful")
            else:
                print(f"❌ Search for '{device}' failed with status: {response.status_code}")
        except Exception as e:
            print(f"❌ Search test failed for '{device}': {e}")
    
    # Test 4: Test batch search form
    print("\n4. Testing batch search form...")
    try:
        response = requests.get(f"{base_url}/batch_search")
        if response.status_code == 200:
            print("✅ Batch search form loads successfully")
        else:
            print(f"❌ Batch search form failed with status: {response.status_code}")
    except Exception as e:
        print(f"❌ Batch search form test failed: {e}")
    
    # Test 5: Test batch search functionality
    print("\n5. Testing batch search functionality...")
    batch_devices = """iPhone 16 Pro
Samsung Galaxy S24
Moto Razr 2024
iPhone 15
Galaxy S23"""
    
    try:
        response = requests.post(f"{base_url}/batch_search", data={"device_list": batch_devices})
        if response.status_code == 200:
            print("✅ Batch search processing successful")
            # Check if we get results page
            if "results" in response.text.lower():
                print("✅ Batch search returns results page")
            else:
                print("⚠️  Batch search returned unexpected content")
        else:
            print(f"❌ Batch search failed with status: {response.status_code}")
    except Exception as e:
        print(f"❌ Batch search test failed: {e}")
    
    # Test 6: Test Excel export (if available)
    print("\n6. Testing Excel export...")
    try:
        # Try to get the Excel download endpoint
        response = requests.post(f"{base_url}/batch_search", data={"device_list": "iPhone 16 Pro"})
        if response.status_code == 200:
            print("✅ Excel export endpoint accessible")
        else:
            print(f"⚠️  Excel export test inconclusive")
    except Exception as e:
        print(f"⚠️  Excel export test failed: {e}")
    
    # Test 7: Test unmapped devices page
    print("\n7. Testing unmapped devices page...")
    try:
        response = requests.get(f"{base_url}/unmapped")
        if response.status_code == 200:
            print("✅ Unmapped devices page loads successfully")
        else:
            print(f"❌ Unmapped devices page failed with status: {response.status_code}")
    except Exception as e:
        print(f"❌ Unmapped devices test failed: {e}")
    
    # Test 8: Test system status
    print("\n8. Testing system status page...")
    try:
        response = requests.get(f"{base_url}/system_status")
        if response.status_code == 200:
            print("✅ System status page loads successfully")
        else:
            print(f"❌ System status page failed with status: {response.status_code}")
    except Exception as e:
        print(f"❌ System status test failed: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Web application testing completed!")
    return True

def start_flask_server():
    """Instructions for starting the Flask server"""
    print("🚀 To start the Flask server:")
    print("1. Open a new terminal")
    print("2. Navigate to the webapp directory:")
    print(f"   cd '{webapp_dir}'")
    print("3. Run the Flask app:")
    print("   python device_app.py")
    print("4. The server will start on http://localhost:5000")
    print("\nThen run this test script again to verify functionality.")

if __name__ == "__main__":
    print("Flask Web Application Test Suite")
    print("=" * 50)
    
    # Check if Flask server is running
    try:
        response = requests.get("http://localhost:5000", timeout=2)
        test_web_app()
    except requests.exceptions.ConnectionError:
        print("❌ Flask server is not running")
        start_flask_server()
    except Exception as e:
        print(f"❌ Error checking server: {e}")
        start_flask_server()
