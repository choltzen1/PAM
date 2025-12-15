"""Azure AD / Entra ID SSO Authentication and RBAC for Azure App Service.

When Easy Auth is enabled on Azure App Service, it injects user identity and 
group memberships into request headers. This module extracts that information
and provides role-based access control decorators.

Key Headers from Azure App Service Easy Auth:
- X-MS-CLIENT-PRINCIPAL: Base64-encoded JSON with user info and groups
- X-MS-CLIENT-PRINCIPAL-NAME: User's email/UPN
- X-MS-CLIENT-PRINCIPAL-ID: User's Azure AD object ID
"""
from __future__ import annotations
from functools import wraps
from flask import request, jsonify, g
import base64
import json
import os
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Configure your RBAC group mappings (Group Object IDs from Entra ID)
# You can get these from Azure Portal > Entra ID > Groups
RBAC_GROUPS = {
    'pam_admin': os.getenv('ENTRA_GROUP_PAM_ADMIN', ''),  # Full admin, override system controls
    'pam_approvers': os.getenv('ENTRA_GROUP_PAM_APPROVERS', ''),  # Approvals on promotions
    'pam_users': os.getenv('ENTRA_GROUP_PAM_USERS', ''),  # Promo owners - full edit access
    'pam_viewonly': os.getenv('ENTRA_GROUP_PAM_VIEWONLY', ''),  # Review and audit only
    'pam_research': os.getenv('ENTRA_GROUP_PAM_RESEARCH', ''),  # Research tools access
    'pam_offers': os.getenv('ENTRA_GROUP_PAM_OFFERS', ''),  # Offers workspace access
}

# Role hierarchy and permissions
# PAM_Admin: Full administrative control, overriding system controls
# PAM_Approvers: View only + one approval button (device finance and revenue accounting)
# PAM_Users: Full edit access - promo owners to configure promotions
# PAM_ViewOnly: Reviewers and audit - read only
# PAM_Research: Only access to research workspaces (analysts and issues research)
# PAM_Offers: Only access to offers workspace (offers owners / offers ops team)
ROLE_HIERARCHY = {
    'pam_admin': ['pam_admin', 'pam_approvers', 'pam_users', 'pam_viewonly', 'pam_research', 'pam_offers'],
    'pam_approvers': ['pam_approvers', 'pam_viewonly'],
    'pam_users': ['pam_users', 'pam_viewonly'],
    'pam_viewonly': ['pam_viewonly'],
    'pam_research': ['pam_research'],
    'pam_offers': ['pam_offers'],
}


def get_user_from_headers() -> Optional[Dict[str, Any]]:
    """Extract user information from Azure App Service Easy Auth headers.
    
    Returns:
        Dictionary with user info: {
            'name': str,           # Display name
            'email': str,          # UPN/email
            'id': str,             # Azure AD object ID
            'groups': List[str],   # List of group object IDs
            'roles': List[str],    # Mapped role names (admin, power_user, etc.)
        }
        Returns None if not authenticated or running locally without Easy Auth.
    """
    # Check for Easy Auth header
    principal_header = request.headers.get('X-MS-CLIENT-PRINCIPAL')
    
    if not principal_header:
        # Not running with Easy Auth (local dev)
        # Return a default dev user if configured
        if os.getenv('DEV_MODE') == 'true':
            logger.info("Dev mode: Using default dev user")
            return {
                'name': os.getenv('DEV_USER_NAME', 'Dev User'),
                'email': os.getenv('DEV_USER_EMAIL', 'dev@example.com'),
                'id': 'dev-user-id',
                'groups': [],
                'roles': ['admin'],  # Dev user gets admin by default
            }
        return None
    
    try:
        # Decode the base64-encoded JSON
        principal_json = base64.b64decode(principal_header).decode('utf-8')
        principal_data = json.loads(principal_json)
        
        # Extract user information
        user_info = {
            'name': principal_data.get('userDetails', 'Unknown'),
            'email': principal_data.get('userId', request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME', 'unknown')),
            'id': principal_data.get('userPrincipalId', request.headers.get('X-MS-CLIENT-PRINCIPAL-ID', 'unknown')),
            'groups': principal_data.get('claims', {}).get('groups', []),
            'roles': [],
        }
        
        # Map groups to roles
        user_info['roles'] = get_user_roles(user_info['groups'])
        
        logger.info(f"Authenticated user: {user_info['email']} with roles: {user_info['roles']}")
        return user_info
        
    except Exception as e:
        logger.error(f"Failed to parse Easy Auth headers: {e}")
        return None


def get_user_roles(user_groups: List[str]) -> List[str]:
    """Map Azure AD group memberships to application roles.
    
    Args:
        user_groups: List of Azure AD group object IDs the user belongs to
        
    Returns:
        List of role names (e.g., ['admin', 'power_user'])
    """
    roles = []
    
    for role_name, group_id in RBAC_GROUPS.items():
        if group_id and group_id in user_groups:
            roles.append(role_name)
    
    # If no roles matched, default to viewonly
    if not roles:
        roles.append('pam_viewonly')
    
    return roles


def has_role(user_info: Optional[Dict[str, Any]], required_role: str) -> bool:
    """Check if user has the required role (including inherited roles).
    
    Args:
        user_info: User information dictionary from get_user_from_headers()
        required_role: Role name to check (e.g., 'power_user')
        
    Returns:
        True if user has the required role or a higher role in the hierarchy
    """
    if not user_info:
        return False
    
    user_roles = user_info.get('roles', [])
    
    # Check if user has any role that includes the required role in hierarchy
    for user_role in user_roles:
        allowed_roles = ROLE_HIERARCHY.get(user_role, [])
        if required_role in allowed_roles:
            return True
    
    return False


def login_required(f):
    """Decorator to require authentication for a route.
    
    Usage:
        @app.route('/protected')
        @login_required
        def protected_route():
            return "This requires authentication"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_info = get_user_from_headers()
        
        if not user_info:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Please log in to access this resource'
            }), 401
        
        # Store user info in Flask g object for use in route handlers
        g.user = user_info
        
        return f(*args, **kwargs)
    
    return decorated_function


def role_required(required_role: str):
    """Decorator to require a specific role for a route.
    
    Args:
        required_role: Role name required (e.g., 'admin', 'power_user')
    
    Usage:
        @app.route('/admin')
        @role_required('admin')
        def admin_route():
            return "This requires admin role"
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_info = get_user_from_headers()
            
            if not user_info:
                return jsonify({
                    'error': 'Authentication required',
                    'message': 'Please log in to access this resource'
                }), 401
            
            if not has_role(user_info, required_role):
                return jsonify({
                    'error': 'Access denied',
                    'message': f'This resource requires {required_role} role',
                    'your_roles': user_info.get('roles', [])
                }), 403
            
            # Store user info in Flask g object
            g.user = user_info
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


def get_current_user() -> Optional[Dict[str, Any]]:
    """Get the current authenticated user from Flask g object or headers.
    
    Returns:
        User info dictionary or None if not authenticated
    """
    # Check if user is already stored in g (from decorator)
    if hasattr(g, 'user'):
        return g.user
    
    # Otherwise, extract from headers
    return get_user_from_headers()


def is_admin() -> bool:
    """Check if current user has PAM_Admin role."""
    user = get_current_user()
    return has_role(user, 'pam_admin')


def is_approver() -> bool:
    """Check if current user has PAM_Approvers role or higher."""
    user = get_current_user()
    return has_role(user, 'pam_approvers')


def is_user() -> bool:
    """Check if current user has PAM_Users role or higher (can edit promos)."""
    user = get_current_user()
    return has_role(user, 'pam_users')


def is_viewonly() -> bool:
    """Check if current user has PAM_ViewOnly role or higher."""
    user = get_current_user()
    return has_role(user, 'pam_viewonly')


def has_research_access() -> bool:
    """Check if current user has PAM_Research role or admin."""
    user = get_current_user()
    return has_role(user, 'pam_research') or has_role(user, 'pam_admin')


def has_offers_access() -> bool:
    """Check if current user has PAM_Offers role or admin."""
    user = get_current_user()
    return has_role(user, 'pam_offers') or has_role(user, 'pam_admin')


def can_edit_promo(promo_owner: str = None) -> bool:
    """Check if current user can edit a promo.
    
    Args:
        promo_owner: Optional owner field from the promo (e.g., 'Zhang, Daniel')
        
    Returns:
        True if user is admin, PAM_Users, or owns this specific promo
    """
    user = get_current_user()
    
    if not user:
        return False
    
    # Admins can edit any promo
    if has_role(user, 'pam_admin'):
        return True
    
    # PAM_Users (promo owners) have full edit access to all promos they own
    if has_role(user, 'pam_users'):
        # If no specific owner provided, they can edit (they're a promo owner)
        if not promo_owner:
            return True
        
        # Check if user owns this specific promo
        user_email = user.get('email', '').lower()
        user_name = user.get('name', '').lower()
        owner_lower = promo_owner.lower() if promo_owner else ''
        
        return (user_email in owner_lower) or (user_name in owner_lower)
    
    return False


def can_approve() -> bool:
    """Check if current user can approve promotions (PAM_Approvers role).
    
    Returns:
        True if user has approver access
    """
    return is_approver()
