"""
Approval Email Tracking Module
Tracks sent approval request emails and their replies for audit and threading
"""

import json
import os
from datetime import datetime
import logging
import hashlib

logger = logging.getLogger(__name__)

TRACKING_FILE = os.path.join(os.path.dirname(__file__), 'approval_emails.json')


def generate_tracking_id(promo_code, version_number):
    """Generate a unique tracking ID based on promo code and version"""
    return f"{promo_code.upper()}_v{version_number}"


def load_tracking_data():
    """Load approval email tracking data from JSON file"""
    if os.path.exists(TRACKING_FILE):
        try:
            with open(TRACKING_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading approval email tracking: {e}")
            return {}
    return {}


def save_tracking_data(data):
    """Save approval email tracking data to JSON file"""
    try:
        with open(TRACKING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving approval email tracking: {e}")


def store_approval_request(promo_code, version_number, subject, recipients):
    """
    Store a sent approval request email
    
    Args:
        promo_code (str): The promotion code
        version_number (str): The version number
        subject (str): Email subject
        recipients (str): Email recipients
    """
    data = load_tracking_data()
    
    key = generate_tracking_id(promo_code, version_number)
    
    data[key] = {
        'promo_code': promo_code,
        'version_number': version_number,
        'request_subject': subject,
        'request_recipients': recipients,
        'request_timestamp': datetime.now().isoformat(),
        'approval_timestamp': None,
        'approved': False
    }
    
    save_tracking_data(data)
    logger.info(f"Stored approval request: {key}")


def store_approval_reply(promo_code, version_number):
    """
    Store the approval reply email
    
    Args:
        promo_code (str): The promotion code
        version_number (str): The version number
    """
    data = load_tracking_data()
    
    key = generate_tracking_id(promo_code, version_number)
    
    if key in data:
        data[key]['approval_timestamp'] = datetime.now().isoformat()
        data[key]['approved'] = True
        save_tracking_data(data)
        logger.info(f"Stored approval reply: {key}")
    else:
        logger.warning(f"No approval request found for {key} to link reply to")


def get_approval_tracking(promo_code, version_number):
    """
    Get approval tracking information
    
    Args:
        promo_code (str): The promotion code
        version_number (str): The version number
    
    Returns:
        dict: Approval tracking data or None if not found
    """
    data = load_tracking_data()
    key = generate_tracking_id(promo_code, version_number)
    return data.get(key)
