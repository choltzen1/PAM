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

# Map Azure App Roles to internal role names
# These come from Enterprise Application > Users and groups > Assigned roles
AZURE_ROLE_MAPPING = {
    'Admin': 'pam_admin',  # Full admin, override system controls
    'Approver': 'pam_approvers',  # Approvals on promotions
    'User': 'pam_users',  # Promo owners - full edit access
    'ViewOnly': 'pam_viewonly',  # Review and audit only
    'Research': 'pam_research',  # Research tools access
}

# Role hierarchy and permissions
# PAM_Admin: Full administrative control, overriding system controls
# PAM_Approvers: View only + one approval button (device finance and revenue accounting)
# PAM_Users: Full edit access - promo owners to configure promotions + research access
# PAM_ViewOnly: Reviewers and audit - read only (PAM homepage + reviewers tab only)
# PAM_Research: Only access to research workspaces (analysts and issues research)
ROLE_HIERARCHY = {
    'pam_admin': ['pam_admin', 'pam_approvers', 'pam_users', 'pam_viewonly', 'pam_research'],
    'pam_approvers': ['pam_approvers', 'pam_viewonly'],
    'pam_users': ['pam_users', 'pam_viewonly', 'pam_research'],
    'pam_viewonly': ['pam_viewonly'],
    'pam_research': ['pam_research'],
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
            # DEV_USER_ROLE can be: pam_admin, pam_users, pam_viewonly, pam_research
            dev_role = os.getenv('DEV_USER_ROLE', 'pam_admin')
            return {
                'name': os.getenv('DEV_USER_NAME', 'Dev User'),
                'email': os.getenv('DEV_USER_EMAIL', 'dev@example.com'),
                'id': 'dev-user-id',
                'groups': [],
                'roles': [dev_role],
            }
        return None
    
    try:
        # Decode the base64-encoded JSON
        principal_json = base64.b64decode(principal_header).decode('utf-8')
        principal_data = json.loads(principal_json)
        
        # Extract claims
        claims = principal_data.get('claims', [])
        
        # Helper to get claim value by type
        def get_claim(claim_type: str) -> Optional[str]:
            for claim in claims:
                if claim.get('typ') == claim_type:
                    return claim.get('val')
            return None
        
        # Extract user information
        user_info = {
            'name': get_claim('name') or get_claim('preferred_username') or 'Unknown',
            'email': get_claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress') or get_claim('preferred_username') or 'unknown',
            'id': get_claim('http://schemas.microsoft.com/identity/claims/objectidentifier') or request.headers.get('X-MS-CLIENT-PRINCIPAL-ID', 'unknown'),
            'azure_roles': [],
            'roles': [],
        }
        
        # Extract Azure App Roles (can be in 'roles' or 'assignedroles' claim)
        # NOTE: Azure Easy Auth sends each App Role as a SEPARATE claim entry
        # with the same typ, so we must collect ALL of them (not just the first).
        def get_all_claims(claim_type: str) -> list:
            return [c.get('val') for c in claims if c.get('typ') == claim_type and c.get('val')]
        
        all_role_vals = get_all_claims('roles') or get_all_claims('assignedroles')
        azure_role_list = []
        for rv in all_role_vals:
            # Each value could itself be comma-separated
            azure_role_list.extend([r.strip() for r in rv.split(',')])
        user_info['azure_roles'] = azure_role_list
        
        # Map Azure roles to internal roles
        user_info['roles'] = get_user_roles_from_azure_roles(user_info['azure_roles'])
        
        logger.info(f"Authenticated user: {user_info['email']} with Azure roles: {user_info['azure_roles']} -> Internal roles: {user_info['roles']}")
        return user_info
        
    except Exception as e:
        logger.error(f"Failed to parse Easy Auth headers: {e}")
        return None


def get_user_roles_from_azure_roles(azure_roles: List[str]) -> List[str]:
    """Map Azure App Roles to internal application roles.
    
    Args:
        azure_roles: List of Azure App Role names (e.g., ['Admin', 'User'])
        
    Returns:
        List of internal role names (e.g., ['pam_admin', 'pam_users'])
    """
    roles = []
    
    for azure_role in azure_roles:
        internal_role = AZURE_ROLE_MAPPING.get(azure_role)
        if internal_role:
            roles.append(internal_role)
        else:
            logger.warning(f"Unknown Azure role: {azure_role}")
    
    # If no roles matched, default to viewonly
    if not roles:
        logger.info("No roles matched, defaulting to pam_viewonly")
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
