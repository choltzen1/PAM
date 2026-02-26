from flask import Blueprint, render_template, redirect, url_for
from auth import role_required

core_bp = Blueprint('core', __name__)

@core_bp.route('/', endpoint='home')
def home_page():
    return redirect(url_for('core.landing'))

@core_bp.route('/PAM_homepage', endpoint='PAM_homepage')
@role_required('pam_viewonly')
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
        from data.fabric_database import fabric_db
        conn = fabric_db._get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT TOP 1 cat_billname FROM dbo.ORBIT_Reporting_Table")
            row = cursor.fetchone()
            results['fabric'] = {
                'status': 'connected',
                'sample_record': bool(row),
                'server': os.getenv('FABRIC_SERVER', '')[:50] + '...' if os.getenv('FABRIC_SERVER') else None,
                'health': fabric_db.get_status(),
            }
            cursor.close()
            # NOTE: do NOT close conn – it's a shared persistent connection
        else:
            results['fabric'] = {
                'status': 'failed',
                'error': 'Could not establish connection',
                'health': fabric_db.get_status(),
            }
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
        from data.fabric_database import fabric_db as fabric
        
        # Show driver being used
        debug_info['driver'] = fabric.driver
        debug_info['health'] = fabric.get_status()
        
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
                
                # NOTE: do NOT close conn – it's a shared persistent connection
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


@core_bp.route('/debug/network', endpoint='debug_network')
def debug_network():
    """Deep network diagnostic for Fabric connectivity.
    Tests each layer independently: DNS, TCP, TLS, ODBC, Token, Full connection.
    Use this to pinpoint exactly where the connection fails on Azure vs local."""
    from flask import jsonify
    import os
    import socket
    import ssl
    import time

    server = os.getenv('FABRIC_SERVER', '')
    port = int(os.getenv('FABRIC_PORT', '1433'))

    results = {
        'environment': {
            'is_azure': bool(os.getenv('WEBSITE_INSTANCE_ID')),
            'hostname': socket.gethostname(),
            'server_target': server,
            'port': port,
        },
        'tests': {}
    }

    # 0. Outbound public IP (so we can compare Azure vs local)
    try:
        import urllib.request
        start = time.time()
        req = urllib.request.Request('https://api.ipify.org?format=json', method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json as _json
            ip_data = _json.loads(resp.read().decode())
        elapsed = round((time.time() - start) * 1000)
        results['tests']['0_outbound_ip'] = {
            'status': 'info',
            'public_ip': ip_data.get('ip', 'unknown'),
            'ms': elapsed,
            'note': 'Compare this IP between local and Azure to see if traffic is proxied differently',
        }
    except Exception as e:
        results['tests']['0_outbound_ip'] = {'status': 'info', 'error': str(e)[:200]}

    # 1. DNS Resolution
    try:
        start = time.time()
        ip = socket.gethostbyname(server)
        elapsed = round((time.time() - start) * 1000)
        results['tests']['1_dns'] = {'status': 'pass', 'ip': ip, 'ms': elapsed}
    except Exception as e:
        results['tests']['1_dns'] = {'status': 'FAIL', 'error': str(e)[:200]}

    # 2. TCP Connect (raw socket, port 1433)
    try:
        start = time.time()
        sock = socket.create_connection((server, port), timeout=10)
        elapsed = round((time.time() - start) * 1000)
        # Get the local (outbound) IP the OS chose
        local_ip = sock.getsockname()[0]
        sock.close()
        results['tests']['2_tcp'] = {'status': 'pass', 'ms': elapsed, 'local_ip': local_ip}
    except Exception as e:
        results['tests']['2_tcp'] = {'status': 'FAIL', 'error': str(e)[:200]}

    # 3. TDS Pre-login probe (send TDS prelogin + read response)
    # Port 1433 uses TDS protocol, not raw TLS. We send a minimal
    # TDS prelogin packet and check if the server responds.
    try:
        start = time.time()
        raw = socket.create_connection((server, port), timeout=10)
        # TDS prelogin packet (minimal): Header(8) + VERSION option
        prelogin = (
            b'\x12'       # Type: Pre-Login
            b'\x01'       # Status: EOM
            b'\x00\x2f'   # Length: 47
            b'\x00\x00'   # SPID
            b'\x01'       # PacketID
            b'\x00'       # Window
            # Options: VERSION(0), ENCRYPTION(1), TERMINATOR(0xff)
            b'\x00\x00\x15\x00\x06'  # VERSION at offset 21, len 6
            b'\x01\x00\x1b\x00\x01'  # ENCRYPTION at offset 27, len 1
            b'\xff'                    # TERMINATOR
            # VERSION data: 0.0.0.0 + subbuild 0
            b'\x00\x00\x00\x00\x00\x00'
            # ENCRYPTION data: 0x01 = ENCRYPT_ON
            b'\x01'
        )
        raw.settimeout(10)
        raw.sendall(prelogin)
        resp = raw.recv(128)
        elapsed = round((time.time() - start) * 1000)
        raw.close()
        got_response = len(resp) > 0
        # Check if response starts with TDS prelogin response type (0x04)
        resp_type = resp[0] if resp else None
        results['tests']['3_tds_prelogin'] = {
            'status': 'pass' if got_response else 'FAIL',
            'ms': elapsed,
            'response_bytes': len(resp),
            'response_type': hex(resp_type) if resp_type is not None else None,
            'note': 'TDS prelogin response received' if got_response else 'No response',
        }
    except Exception as e:
        results['tests']['3_tds_prelogin'] = {'status': 'FAIL', 'error': str(e)[:200]}

    # 4. OAuth Token
    try:
        from data.fabric_database import fabric_db as _fabric
        start = time.time()
        token = _fabric._get_access_token()
        elapsed = round((time.time() - start) * 1000)
        results['tests']['4_token'] = {
            'status': 'pass' if token else 'FAIL',
            'ms': elapsed,
            'token_bytes': len(token) if token else 0,
        }
    except Exception as e:
        results['tests']['4_token'] = {'status': 'FAIL', 'error': str(e)[:200]}

    # 5. ODBC/pyodbc connect (the actual Fabric connection)
    try:
        from data.fabric_database import fabric_db as _fabric2
        start = time.time()
        conn = _fabric2._get_connection()
        elapsed = round((time.time() - start) * 1000)
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            results['tests']['5_odbc'] = {'status': 'pass', 'ms': elapsed}
        else:
            results['tests']['5_odbc'] = {'status': 'FAIL', 'error': _fabric2._last_error, 'ms': elapsed}
    except Exception as e:
        results['tests']['5_odbc'] = {'status': 'FAIL', 'error': str(e)[:200]}

    # Summary
    failed = [k for k, v in results['tests'].items() if v.get('status') == 'FAIL']
    results['summary'] = {
        'all_pass': len(failed) == 0,
        'failed_tests': failed,
        'diagnosis': _diagnose_failure(failed),
    }

    return jsonify(results)


def _diagnose_failure(failed):
    """Provide human-readable diagnosis based on which tests failed."""
    if not failed:
        return "All tests passed - Fabric connection is working."
    first = failed[0]
    if '1_dns' in first:
        return "DNS resolution failed. FABRIC_SERVER env var may be missing or DNS is blocked."
    if '2_tcp' in first:
        return "TCP connection failed. Port 1433 is blocked by firewall/NSG, or the server is unreachable."
    if '3_tds' in first:
        return "TDS prelogin failed. TCP connected but the SQL endpoint did not respond to TDS protocol. The server may be actively rejecting non-whitelisted connections at the application layer."
    if '4_token' in first:
        return "OAuth token acquisition failed. Check Service Principal credentials (FABRIC_CLIENT_ID, FABRIC_CLIENT_SECRET, FABRIC_TENANT_ID)."
    if '5_odbc' in first:
        return "ODBC connection failed but TCP+TLS+Token all passed. This means the Fabric endpoint is rejecting the authenticated ODBC session. This is the Premium capacity SKU limitation - it only accepts connections from corporate-proxied traffic (Zscaler), not direct Azure connections."
    return f"Unknown failure pattern: {failed}"


# Research workspace handled by research blueprint (/research)

__all__ = ['core_bp']
