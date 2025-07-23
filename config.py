# Promo App Configuration
# ======================

# Paths (all relative to project root)
DATA_DIR = "data"
RESULTS_DIR = "results" 
TEMP_DIR = "temp"
ARCHIVE_DIR = "archive"

# Main data files
EXCEL_FILE = "data/Z0MATERIAL_ATTRB_REP01_00000.xlsx"
MAPPING_FILE = "data/device_alias_mapping.csv"
STATE_FILE = "data/mapping_state.json"

# Flask app settings
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False

# Excel processing settings
FILTER_CRITERIA = {
    "SKU Type": ["A-STOCK", "WARRANTY", "PRWARRANTY", "REFURB SKU"],
    "Handset Brand": ["T-MOBILE", "SPRINT", "UNIVERSAL"]
}

# Automation settings
AUTOMATION_TIME = "10:00"  # Daily check time
MAX_RESULTS_PER_SEARCH = 1000

# File patterns to ignore during cleanup
IGNORE_PATTERNS = [
    "__pycache__",
    "*.pyc", 
    ".git",
    "venv",
    "*.log"
]
