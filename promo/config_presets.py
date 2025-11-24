"""
Promo configuration presets for dropdown selections.
Each preset defines field overrides applied during promo code generation.
"""

def get_config_preset(config_name: str) -> dict:
    """
    Return field overrides for the specified configuration preset.
    
    Args:
        config_name: The dropdown selection (e.g., 'apple', 'bogo-gsm', 'samsung')
    
    Returns:
        Dictionary of field names and values to override in the database.
        Keys correspond to database column names used in the insertion dict.
    
    Example:
        >>> preset = get_config_preset('apple')
        >>> preset['sales_application']
        'S15'
    """
    # Normalize config name (handle underscores, hyphens, and case variations)
    normalized = config_name.lower().replace('_', '-').strip()
    
    presets = {
        'apple': {
            'product_type': 'G',
            'sales_application': 'S15',  # Apple channel
            'mpss_lookback': '14',
        },
        'samsung': {
            'product_type': 'G',
            'sales_application': 'S17',  # Samsung channel
            'mpss_lookback': '14',
        },
        'standard-gsm': {
            'product_type': 'G',
            'mpss_lookback': '14',
            
        },
        'standard-mi': {
            'product_type': 'B',
            'mpss_lookback': '14',
            
        },
        'bogo-gsm': {
            'product_type': 'G',
            'bogo': 'Y',
            'mpss_lookback': '14',
            
        },
        'bogo-mi': {
            'product_type': 'B',
            'bogo': 'Y',
            'mpss_lookback': '14',
            
        },
        'bvt-gsm': {
            'product_type': 'G',
            'mpss_lookback': '14',
        },
        'bvt-mi': {
            'product_type': 'B',
            'mpss_lookback': '14',
            
            # BVT-specific fields - customize as needed
        },
        'non-0-trade-in': {
            'trade_in_grace': '32',
            'mpss_lookback': '14',
            # Trade-in specific fields - customize as needed
        },
        'rebate': {
            'product_type': 'G',
            # Rebate-specific fields - customize as needed
        },
        'spe': {
            # SPE-specific fields - customize as needed
        },
    }
    
    return presets.get(normalized, {})


def get_all_config_options():
    """
    Return list of all available configuration options for dropdowns.
    
    Returns:
        List of tuples (value, label) for use in HTML select elements.
    """
    return [
        ('apple', 'Apple'),
        ('bogo-gsm', 'BOGO GSM'),
        ('bogo-mi', 'BOGO MI'),
        ('bvt-gsm', 'BVT GSM'),
        ('bvt-mi', 'BVT MI'),
        ('non-0-trade-in', 'Non 0$ Trade-In'),
        ('rebate', 'Rebate'),
        ('samsung', 'Samsung'),
        ('spe', 'SPE'),
        ('standard-gsm', 'Standard GSM'),
        ('standard-mi', 'Standard MI'),
    ]


__all__ = ['get_config_preset', 'get_all_config_options']
