from flask import Blueprint, render_template, redirect, url_for

core_bp = Blueprint('core', __name__)

@core_bp.route('/', endpoint='home')
def home_page():
    return redirect(url_for('core.landing'))

@core_bp.route('/PAM_homepage', endpoint='PAM_homepage')
def pam_homepage():
    """Primary navigation landing page (formerly index)."""
    return render_template('pam/PAM_homepage.html')

@core_bp.route('/landing', endpoint='landing')
def landing_page():
    """Primary entry landing page (workspace hub) with three selectable workspaces."""
    hub_name = "Promo Operations Management Tool"
    tiles = [
        {
            'key': 'pam',
            'label': 'PAM',
            'icon': 'bi-grid-3x3-gap-fill',
            'url': url_for('core.PAM_homepage'),
            'ribbon': 'Live',
            'sub': 'Promo & Workflow'
        },
        {
            'key': 'research',
            'label': 'Research',
            'icon': 'bi-search-heart',
            'url': url_for('research.index'),
            'ribbon': 'Alpha',
            'sub': 'Data & Eligibility'
        }
    ]
    objective = (
        "Choose a workspace. Pam and Research are in an Alpha and active development stage. Offers is a current placeholder." )
    return render_template('landing.html', tiles=tiles, objective=objective, hub_name=hub_name)

@core_bp.route('/theme', methods=['GET','POST'], endpoint='set_theme')
def set_theme():
    """Persist user theme choice (light/dark/auto) in a cookie.
    Returns JSON describing the saved mode. LocalStorage will also be used client-side for first-paint override.
    """
    from flask import request, make_response, jsonify
    mode = request.values.get('mode','auto')
    if mode not in ('light','dark','auto'):
        mode = 'auto'
    resp = make_response(jsonify(success=True, mode=mode))
    # 1 year persistence
    resp.set_cookie('theme', mode, max_age=60*60*24*365, samesite='Lax')
    return resp

@core_bp.route('/offers', endpoint='offers_workspace')
def offers_workspace():
    # Updated to new offers workspace hub layout (similar to research workspace)
    return render_template('offers/placeholder.html')

@core_bp.route('/debug/me', endpoint='debug_user')
def debug_user():
    """Debug endpoint to inspect Azure Easy Auth headers and user identity.
    
    Shows the raw X-MS-CLIENT-PRINCIPAL header decoded, plus processed user info
    from the auth module.
    """
    import base64
    import json
    from flask import request, jsonify
    
    # Get raw header
    encoded = request.headers.get('X-MS-CLIENT-PRINCIPAL')
    
    if not encoded:
        # Not running with Easy Auth - show dev mode status
        import os
        dev_mode = os.getenv('DEV_MODE') == 'true'
        
        return jsonify({
            'error': 'No X-MS-CLIENT-PRINCIPAL header found',
            'dev_mode': dev_mode,
            'message': 'Running locally without Azure Easy Auth' if dev_mode else 'Easy Auth not configured',
            'all_headers': dict(request.headers)
        }), 200
    
    try:
        # Decode the Easy Auth header
        decoded = base64.b64decode(encoded)
        principal = json.loads(decoded.decode('utf-8'))
        
        # Also get processed user info from auth module
        from auth import get_current_user
        processed_user = get_current_user()
        
        return jsonify({
            'raw_principal': principal,
            'processed_user': processed_user,
            'headers': {
                'X-MS-CLIENT-PRINCIPAL-NAME': request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME'),
                'X-MS-CLIENT-PRINCIPAL-ID': request.headers.get('X-MS-CLIENT-PRINCIPAL-ID'),
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to decode principal header',
            'exception': str(e),
            'raw_header': encoded[:100] + '...' if len(encoded) > 100 else encoded
        }), 500


@core_bp.route('/health', endpoint='health')
def health_check():
    """Basic health check - returns 200 if app is running."""
    from flask import jsonify
    return jsonify({'status': 'ok', 'message': 'PAM is running'})


@core_bp.route('/debug/env', endpoint='debug_env')
def debug_env():
    """Debug endpoint to check which environment variables are set (not values, just presence)."""
    import os
    from flask import jsonify
    
    # Check for required env vars (show presence, not values)
    env_checks = {
        # Fabric (ORBIT data source)
        'FABRIC_SERVER': bool(os.getenv('FABRIC_SERVER')),
        'FABRIC_DATABASE': bool(os.getenv('FABRIC_DATABASE')),
        'FABRIC_CLIENT_ID': bool(os.getenv('FABRIC_CLIENT_ID')),
        'FABRIC_TENANT_ID': bool(os.getenv('FABRIC_TENANT_ID')),
        'FABRIC_CLIENT_SECRET': bool(os.getenv('FABRIC_CLIENT_SECRET')),
        # PAM Database
        'PAM_DB_SERVER': bool(os.getenv('PAM_DB_SERVER')),
        'PAM_DB_DATABASE': bool(os.getenv('PAM_DB_DATABASE')),
        'PAM_DB_USERNAME': bool(os.getenv('PAM_DB_USERNAME')),
        'PAM_DB_PASSWORD': bool(os.getenv('PAM_DB_PASSWORD')),
        # JIRA
        'JIRA_URL': bool(os.getenv('JIRA_URL')),
        'JIRA_USERNAME': bool(os.getenv('JIRA_USERNAME')),
        'JIRA_API_TOKEN': bool(os.getenv('JIRA_API_TOKEN')),
        # RBAC Groups
        'ENTRA_GROUP_PAM_ADMIN': bool(os.getenv('ENTRA_GROUP_PAM_ADMIN')),
        'ENTRA_GROUP_PAM_USERS': bool(os.getenv('ENTRA_GROUP_PAM_USERS')),
        # App settings
        'FLASK_ENV': os.getenv('FLASK_ENV', 'not set'),
        'DEV_MODE': os.getenv('DEV_MODE', 'not set'),
    }
    
    # Count how many required vars are missing
    required = ['FABRIC_SERVER', 'FABRIC_DATABASE', 'FABRIC_CLIENT_ID', 
                'FABRIC_TENANT_ID', 'FABRIC_CLIENT_SECRET',
                'PAM_DB_SERVER', 'PAM_DB_DATABASE', 'PAM_DB_USERNAME', 'PAM_DB_PASSWORD']
    missing = [k for k in required if not env_checks.get(k)]
    
    return jsonify({
        'env_vars': env_checks,
        'missing_required': missing,
        'status': 'ok' if not missing else 'missing_vars',
        'ready': len(missing) == 0
    })


@core_bp.route('/debug/db', endpoint='debug_db')
def debug_db():
    """Debug endpoint to test database connectivity."""
    from flask import jsonify
    import os
    
    results = {
        'fabric': {'status': 'unknown', 'error': None},
        'pam_db': {'status': 'unknown', 'error': None}
    }
    
    # Test Fabric connection
    try:
        from data.fabric_database import FabricDatabaseManager
        fabric = FabricDatabaseManager()
        conn = fabric._get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT TOP 1 cat_billname FROM dbo.ORBIT_Reporting_Table")
            row = cursor.fetchone()
            results['fabric'] = {
                'status': 'connected',
                'sample_record': bool(row),
                'server': os.getenv('FABRIC_SERVER', '')[:50] + '...' if os.getenv('FABRIC_SERVER') else None
            }
            cursor.close()
            conn.close()
        else:
            results['fabric'] = {'status': 'failed', 'error': 'Could not establish connection'}
    except Exception as e:
        results['fabric'] = {'status': 'error', 'error': str(e)[:200]}
    
    # Test PAM DB connection
    try:
        from data.database import DatabaseManager
        dbm = DatabaseManager()
        engine = dbm.get_engine()
        if engine:
            with engine.connect() as conn:
                from sqlalchemy import text
                result = conn.execute(text("SELECT TOP 1 promo_code FROM [PAM].[PAM_Orbit_Data_Updated]"))
                row = result.fetchone()
                results['pam_db'] = {
                    'status': 'connected',
                    'sample_record': bool(row),
                    'server': os.getenv('PAM_DB_SERVER', '')
                }
        else:
            results['pam_db'] = {'status': 'failed', 'error': 'Could not create engine'}
    except Exception as e:
        results['pam_db'] = {'status': 'error', 'error': str(e)[:200]}
    
    all_ok = all(r['status'] == 'connected' for r in results.values())
    
    return jsonify({
        'databases': results,
        'all_connected': all_ok,
        'status': 'ok' if all_ok else 'degraded'
    })


@core_bp.route('/debug/fabric', endpoint='debug_fabric')
def debug_fabric():
    """Debug endpoint specifically for Fabric/ORBIT connection issues."""
    from flask import jsonify
    import os
    
    debug_info = {
        'config': {
            'server_set': bool(os.getenv('FABRIC_SERVER')),
            'database_set': bool(os.getenv('FABRIC_DATABASE')),
            'client_id_set': bool(os.getenv('FABRIC_CLIENT_ID')),
            'tenant_id_set': bool(os.getenv('FABRIC_TENANT_ID')),
            'client_secret_set': bool(os.getenv('FABRIC_CLIENT_SECRET')),
            'server_preview': os.getenv('FABRIC_SERVER', '')[:30] + '...' if os.getenv('FABRIC_SERVER') else None,
        },
        'connection_test': None,
        'token_test': None,
        'query_test': None,
        'connection_string_used': None,
        'driver': None,
        'last_error': None
    }
    
    try:
        from data.fabric_database import FabricDatabaseManager
        fabric = FabricDatabaseManager()
        
        # Show driver being used
        debug_info['driver'] = fabric.driver
        
        # Test token acquisition
        try:
            token = fabric._get_access_token()
            debug_info['token_test'] = {
                'status': 'success' if token else 'failed',
                'token_length': len(token) if token else 0
            }
        except Exception as e:
            debug_info['token_test'] = {'status': 'error', 'error': str(e)[:150]}
        
        # Test connection
        try:
            conn = fabric._get_connection()
            # Show what connection string was used (without secrets)
            debug_info['connection_string_used'] = fabric._used_connection_string
            debug_info['last_error'] = fabric._last_error
            
            if conn:
                debug_info['connection_test'] = {'status': 'success'}
                
                # Test query
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM dbo.ORBIT_Reporting_Table")
                    count = cursor.fetchone()[0]
                    debug_info['query_test'] = {
                        'status': 'success',
                        'total_records': count
                    }
                    cursor.close()
                except Exception as e:
                    debug_info['query_test'] = {'status': 'error', 'error': str(e)[:150]}
                
                conn.close()
            else:
                debug_info['connection_test'] = {'status': 'failed', 'error': 'No connection returned', 'last_error': fabric._last_error}
        except Exception as e:
            debug_info['connection_test'] = {'status': 'error', 'error': str(e)[:150]}
            debug_info['last_error'] = fabric._last_error
            
    except Exception as e:
        debug_info['init_error'] = str(e)[:200]
    
    return jsonify(debug_info)


@core_bp.route('/debug/jira', endpoint='debug_jira')
def debug_jira():
    """Debug endpoint to test JIRA connectivity from Azure."""
    from flask import jsonify
    import os
    import requests
    import socket
    
    jira_url = os.getenv('JIRA_URL', 'https://t-mobile.atlassian.net')
    username = os.getenv('JIRA_USERNAME', '')
    api_token = os.getenv('JIRA_API_TOKEN', '')
    
    debug_info = {
        'config': {
            'url': jira_url,
            'username_set': bool(username),
            'api_token_set': bool(api_token),
            'api_token_length': len(api_token) if api_token else 0,
            'api_token_preview': api_token[:10] + '...' if api_token and len(api_token) > 10 else 'too_short_or_empty',
        },
        'dns_test': None,
        'connection_test': None,
        'auth_test': None,
    }
    
    # Extract hostname from URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(jira_url)
        hostname = parsed.netloc
        debug_info['hostname'] = hostname
    except Exception as e:
        debug_info['hostname_error'] = str(e)
        hostname = None
    
    # Test DNS resolution
    if hostname:
        try:
            ip = socket.gethostbyname(hostname)
            debug_info['dns_test'] = {'status': 'success', 'ip': ip}
        except socket.gaierror as e:
            debug_info['dns_test'] = {'status': 'failed', 'error': str(e)}
        except Exception as e:
            debug_info['dns_test'] = {'status': 'error', 'error': str(e)}
    
    # Test basic HTTPS connection (no auth)
    try:
        resp = requests.get(jira_url, timeout=10, verify=True)
        debug_info['connection_test'] = {
            'status': 'success',
            'http_status': resp.status_code,
            'response_time_ms': int(resp.elapsed.total_seconds() * 1000),
        }
    except requests.exceptions.SSLError as e:
        debug_info['connection_test'] = {'status': 'ssl_error', 'error': str(e)[:200]}
    except requests.exceptions.ConnectionError as e:
        debug_info['connection_test'] = {'status': 'connection_failed', 'error': str(e)[:200]}
    except requests.exceptions.Timeout:
        debug_info['connection_test'] = {'status': 'timeout', 'error': 'Request timed out after 10s'}
    except Exception as e:
        debug_info['connection_test'] = {'status': 'error', 'error': str(e)[:200]}
    
    # Test authenticated API call
    if username and api_token:
        try:
            resp = requests.get(
                f"{jira_url}/rest/api/2/myself",
                auth=(username, api_token),
                timeout=15,
                verify=True
            )
            if resp.status_code == 200:
                user_data = resp.json()
                debug_info['auth_test'] = {
                    'status': 'success',
                    'authenticated_as': user_data.get('displayName', user_data.get('name', 'unknown')),
                    'email': user_data.get('emailAddress', 'unknown'),
                }
            else:
                debug_info['auth_test'] = {
                    'status': 'auth_failed',
                    'http_status': resp.status_code,
                    'response': resp.text[:200]
                }
        except requests.exceptions.ConnectionError as e:
            debug_info['auth_test'] = {'status': 'connection_failed', 'error': str(e)[:200]}
        except Exception as e:
            debug_info['auth_test'] = {'status': 'error', 'error': str(e)[:200]}
    else:
        debug_info['auth_test'] = {'status': 'skipped', 'reason': 'Missing username or api_token'}
    
    # Overall status
    all_ok = (
        debug_info.get('dns_test', {}).get('status') == 'success' and
        debug_info.get('connection_test', {}).get('status') == 'success' and
        debug_info.get('auth_test', {}).get('status') == 'success'
    )
    debug_info['overall_status'] = 'ok' if all_ok else 'failed'
    
    return jsonify(debug_info)


# Research workspace handled by research blueprint (/research)

__all__ = ['core_bp']
