# Microsoft Fabric Integration Guide for PAM

## ✅ Status: **ENABLED AND WORKING!**

**PAM is now using LIVE ORBIT data from Microsoft Fabric Data Warehouse!**

The Microsoft Fabric Data Warehouse connection has been successfully tested and **is currently active** in your PAM application.

---

## 🎯 What's Changed

### Before (Fake/Test Data)
- PAM used local SQL Server for ORBIT data
- Data was fake/test data for development
- `USE_FABRIC_ORBIT=false` in .env

### After (LIVE Data) ✅
- **PAM now uses Microsoft Fabric Data Warehouse**
- **Data is REAL, LIVE promotion data**
- **`USE_FABRIC_ORBIT=true` in .env**

---

## 🔧 How It Works

### The Toggle System
Your codebase already had Fabric integration built in! We just enabled it:

1. **Environment Variable**: `USE_FABRIC_ORBIT=true` in `.env`
2. **Automatic Routing**: `OrbitDatabaseManager` checks this flag
3. **Smart Delegation**: If enabled, routes to `FabricDatabaseManager`
4. **Transparent Integration**: All existing code works without changes!

### Data Flow
```
User Action in PAM
    ↓
OrbitDatabaseManager.get_orbit_record(gtm_id)
    ↓
Checks USE_FABRIC_ORBIT flag
    ↓
Routes to FabricDatabaseManager (LIVE DATA!)
    ↓
Fetches from Microsoft Fabric Data Warehouse
    ↓
Returns real promotion data
    ↓
PAM saves to local database for configuration
```

---

## 📋 What Was Done

### 1. ✅ Tested Fabric Connection
- Service Principal authentication working
- OAuth token retrieval and caching (50-minute cache)
- Connection to Fabric SQL endpoint successful
- Query execution verified
- Token caching implemented for performance

### 2. ✅ Verified `fabric_database.py` Module
The module provides the following methods:

#### Core Methods:
- **`test_connection()`** - Test the connection to Fabric
- **`search_by_promo_code(promo_code)`** - Find promotion by promo code
- **`search_by_gtm_id(gtm_id)`** - Find promotion by GTM Entry ID
- **`get_all_promotions(limit=None)`** - Get all promotions (optionally limited)
- **`search_promotions(search_term, start_date, end_date, limit)`** - Search with filters
- **`get_last_error()`** - Get the last error message

### 3. ✅ Fixed Integration Bug
- Added `table` attribute to `OrbitDatabaseManager` when in Fabric mode
- Ensures compatibility with existing services like `orbit_search()`

### 4. ✅ Enabled LIVE Data
- Updated `.env` to set `USE_FABRIC_ORBIT=true`
- Verified all integration points work correctly

---

## 🧪 Test Results Summary

### All Tests Passing ✅

**Test 1: Connection Test**
```
✅ Connection test PASSED
✅ Retrieved OAuth token successfully
✅ Connected to Fabric Data Warehouse
```

**Test 2: Data Retrieval**
```
✅ Get All Promotions: PASSED (retrieved 5 records)
✅ Search by Promo Code: PASSED (found P042)
✅ Search by GTM ID: PASSED
✅ Search with Filters: PASSED (found 3 Apple promotions)
```

**Test 3: PAM Integration**
```
✅ OrbitDatabaseManager routes to Fabric
✅ Live ORBIT data fetched successfully (327 fields per record!)
✅ orbit_search() service working with Fabric data
```

---

## 🔐 Security & Configuration

### Required Environment Variables
All properly configured in your `.env`:

```bash
# Fabric Connection
FABRIC_TENANT_ID=be0f980b-dd99-4b19-bd7b-bc71a09b026c
FABRIC_CLIENT_ID=fe804f58-c827-4906-8754-8c8fe7863341
FABRIC_CLIENT_SECRET=<stored-in-azure-keyvault>
FABRIC_SERVER=boma7puz3umuxpl3xry2bgycnq-pfqzvh7fituunjrpjqi5xkzyii.datawarehouse.fabric.microsoft.com
FABRIC_DATABASE=55c3885d-ecc6-47a2-9ab5-839c7a60f6c6

# Toggle (CURRENTLY ENABLED FOR LIVE DATA!)
USE_FABRIC_ORBIT=true  
```

### Security Features
- ✅ Service Principal (client credentials flow)
- ✅ Tokens cached in memory only (not persisted)
- ✅ SSL/TLS encryption enabled
- ✅ Environment variables for credentials (.env file)

---

## 🚀 How to Use in PAM App

### PAM is Already Using It!

All existing PAM code automatically uses Fabric now. No changes needed!

**Example**: When generating promo codes
```python
# In api/routes.py - already working!
from data.orbit_database import OrbitDatabaseManager
odm = OrbitDatabaseManager()

# This now fetches from LIVE Fabric data!
orbit_row = odm.get_orbit_record(orbit_id)
```

**Example**: In services
```python
# In services/promo_codes_service.py - already working!
from services.promo_codes_service import orbit_search

# This now returns LIVE Fabric data!
result = orbit_search(gtm_id)
```

### Direct Fabric Access (Optional)

If you need direct access to Fabric features:

```python
from data.fabric_database import fabric_db

# Search by promo code (not just GTM ID)
promo = fabric_db.search_by_promo_code("R316")

# Advanced search with filters
results = fabric_db.search_promotions(
    search_term="Apple",
    start_date="2022-01-01",
    end_date="2023-12-31",
    limit=50
)
```

---

## 📊 Data Schema

The ORBIT_Reporting_Table in Fabric contains **327 fields** including:

### Key Fields:
- `cat_initiativename` - Promotion name
- `crffc_promocodeid` - Promo code
- `cat_gtmentryid` - GTM Entry ID (used as orbit_id)
- `cat_startdate` - Start date
- `cat_enddate` - End date
- `cat_billname` - Bill facing name
- `cat_description` - Description
- `cat_businessowner` - Owner
- `cat_totalofferspend` - Total offer spend
- `modifiedon` - Last modified timestamp
- ...and 317 more fields!

All fields are available in the returned dictionaries.

---

## ⚡ Performance Notes

1. **Token Caching**: Access tokens are cached for 50 minutes, so repeated calls don't re-authenticate
2. **Connection Management**: Each query creates a new connection (consider adding pooling if needed)
3. **Thread-Safe**: The token cache uses thread locks for safety
4. **Timeout Settings**: Connection timeout set to 60 seconds

---

## � How to Switch Between LIVE and TEST Data

### To Use LIVE Data (Current Setting ✅)
```bash
# In .env file:
USE_FABRIC_ORBIT=true
```

### To Use TEST Data (Local SQL Server)
```bash
# In .env file:
USE_FABRIC_ORBIT=false
```

**No code changes needed!** Just update the .env file and restart PAM.

---

## 📝 Testing

Run the test suites to verify everything:

```bash
# Test Fabric connection directly
python test_fabric_connection.py

# Test fabric_database module
python test_fabric_database_module.py

# Test Fabric integration toggle
python test_fabric_integration.py

# Test PAM with LIVE data
python test_pam_fabric_live.py
```

All tests passing! ✅

---

## 🎯 What Happens Now

### When Users Use PAM:

1. **Create Promo Code**
   - User enters GTM ID in PAM
   - PAM calls `OrbitDatabaseManager.get_orbit_record(gtm_id)`
   - **Routes to Fabric** (because `USE_FABRIC_ORBIT=true`)
   - Fetches **REAL promotion data** from Fabric
   - Returns 327 fields of LIVE data!

2. **Data Gets Saved**
   - PAM takes the LIVE Fabric data
   - Saves it to local PAM database for configuration/tracking
   - Users can now configure the promotion in PAM

3. **Configuration Happens**
   - Users configure promotion details
   - Configuration stored in PAM database
   - Ready to be pushed to production systems

---

## 🐛 Troubleshooting

### If Connection Fails

Check error with:
```python
from data.fabric_database import fabric_db
fabric_db.get_last_error()
```

### Common Issues:

1. **Token Timeout**: Normal, will retry automatically
2. **Network Issues**: Check connectivity to `*.datawarehouse.fabric.microsoft.com`
3. **Credentials**: Verify Service Principal has proper permissions

### Debug Mode:

```python
import logging
logging.basicConfig(level=logging.INFO)
# Now you'll see detailed connection logs
```

---

## 📞 Support & Monitoring

### Check Integration Status:
```python
from data.orbit_database import OrbitDatabaseManager
mgr = OrbitDatabaseManager()
print(f"Using Fabric: {mgr.use_fabric}")  # Should be True
```

### Verify Data Source:
```python
result = mgr.get_orbit_record(some_gtm_id)
print(f"Fields returned: {len(result)}")  # Should be 327 for Fabric
```

---

## ✅ Summary

### Current State:
- ✅ Fabric connection tested and working
- ✅ Integration toggle enabled (`USE_FABRIC_ORBIT=true`)
- ✅ PAM is fetching LIVE ORBIT data from Fabric
- ✅ All existing PAM code works without changes
- ✅ 327 fields of real promotion data available
- ✅ Token caching for performance
- ✅ Thread-safe implementation

### Files Modified:
1. **`.env`** - Enabled `USE_FABRIC_ORBIT=true`
2. **`data/orbit_database.py`** - Added `table` attribute for Fabric mode

### Files Created:
1. **`test_fabric_database_module.py`** - Test suite
2. **`test_pam_fabric_live.py`** - PAM integration test
3. **`FABRIC_INTEGRATION_GUIDE.md`** - This guide

### No Changes Needed In:
- ✅ API routes
- ✅ Services
- ✅ Templates
- ✅ Frontend code

**Everything works automatically!**

---

**Status**: ✅ **LIVE AND WORKING**  
**Last Updated**: November 25, 2025  
**Data Source**: Microsoft Fabric Data Warehouse (LIVE)

