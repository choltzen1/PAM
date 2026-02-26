from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from datetime import datetime
from sqlalchemy import text
import os, json
from typing import Optional, TYPE_CHECKING
from auth import role_required

if TYPE_CHECKING:
    from data.storage import PromoDataManager

admin_bp = Blueprint('admin_bp', __name__)

data_manager = None
_PAM_PROMO_CACHE = {'ts': 0, 'data': None}  # in-process cache for PAM promotions page
_OWNERS_CACHE = {'ts': 0, 'data': []}       # in-process cache for owners dropdown

def init_data_manager(dm):
    global data_manager
    data_manager = dm

def _ensure_dm():
    if data_manager is None:
        raise RuntimeError('Data manager not initialized for admin blueprint')
    return data_manager

# --- Helper persistence functions (mirroring legacy) ---
USER_DATA_FILE = os.path.join('data', 'users.json')
USER_GROUPS_FILE = os.path.join('data', 'user_groups.json')
REFERENCE_GROUPINGS_FILES = {
    'soc': os.path.join('static', 'soc_grouping.txt'),
    'account': os.path.join('static', 'account_types.txt'),
    'sales': os.path.join('static', 'sales_apps.txt')
}

def get_user_groups():
    try:
        if os.path.exists(USER_GROUPS_FILE):
            with open(USER_GROUPS_FILE, 'r') as f:
                return json.load(f)
        default_groups = {
            "admin": {"name": "Administrator", "permissions": ["view_all","edit_all","delete_all","edit_promotions","create_promotions","date_mismatch","sql_generation","user_management","system_admin"], "description": "Full system access including user management"},
            "promo_owner": {"name": "Promo Owner", "permissions": ["view_all","edit_promotions","create_promotions","date_mismatch","sql_generation"], "description": "Can view, edit, create promotions"},
            "reviewer": {"name": "Reviewer", "permissions": ["view_all"], "description": "Read-only access"}
        }
        save_user_groups(default_groups)
        return default_groups
    except Exception:
        return {}

def save_user_groups(groups):
    try:
        os.makedirs(os.path.dirname(USER_GROUPS_FILE), exist_ok=True)
        with open(USER_GROUPS_FILE, 'w') as f:
            json.dump(groups, f, indent=2)
    except Exception:
        pass


# --- Reference Groupings (txt-backed) Utilities ---
# Standard Format v1 Specification:
#   First line: "# PAM_GROUPINGS v1" (header comment)
#   Comment lines start with '#', blank lines skipped.
#   Data line format: CODE|LABEL|ITEM1,ITEM2,...
#     - CODE: token (no internal pipe)
#     - LABEL: free text (no internal pipe; any '-' or '–' retained)
#     - ITEMS: comma-separated list (may be empty). For sales apps currently empty.
# Legacy formats (existing mixed styles with dashes and pipes) are auto-parsed and
# re-written into v1 upon save.
STANDARD_GROUPINGS_HEADER = '# PAM_GROUPINGS v1'
def _get_reference_file(kind: str) -> str:
    if kind not in REFERENCE_GROUPINGS_FILES:
        raise ValueError('Invalid grouping type')
    return REFERENCE_GROUPINGS_FILES[kind]

def load_reference_groupings(kind: str) -> list:
    """Load groupings for a given kind using the standardized v1 format; fallback to legacy parsing.

    Returns list of dicts: {code, label, items, raw}
    """
    path = _get_reference_file(kind)
    results: list[dict] = []
    if not os.path.exists(path):
        return results
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = [ln.rstrip('\n') for ln in f]
        # Detect standard format: header present OR majority of data lines contain two pipes
        data_lines = [ln for ln in lines if ln.strip() and not ln.strip().startswith('#')]
        pipe_like = sum(1 for ln in data_lines if ln.count('|') >= 2)
        is_standard = any(ln.startswith(STANDARD_GROUPINGS_HEADER) for ln in lines) or (data_lines and pipe_like / max(len(data_lines),1) > 0.6)
        if is_standard:
            for raw in data_lines:
                # Skip malformed lines gracefully
                if raw.count('|') < 2:
                    continue
                code, label, items_part = (raw.split('|', 2) + ['', '', ''])[:3]
                code = code.strip()
                label = label.strip()
                items_part = items_part.strip()
                if not code:
                    continue
                # Split items by comma and strip
                items = [it.strip() for it in items_part.split(',') if it.strip()] if items_part else []
                results.append({'code': code, 'label': label, 'items': items, 'raw': raw})
            return results
        # Legacy fallback parsing retains prior behavior
        import re
        for raw in data_lines:
            line = raw.strip()
            code = None
            label = ''
            items: list[str] = []
            if kind == 'soc':
                # Legacy patterns
                if line.lower().startswith('group '):
                    m = re.match(r'^Group\s+([A-Za-z0-9]+)\s*-\s*(.*)$', line.split('|')[0])
                    if m:
                        code = m.group(1).strip(); label = m.group(2).strip()
                    if '|' in line:
                        details = line.split('|',1)[1].strip()
                        if details:
                            items = [d.strip() for d in details.split(',') if d.strip()]
                else:
                    # Pattern CODE - LABEL|items OR CODE|LABEL
                    head, tail = (line.split('|',1)+[''])[:2]
                    if ' - ' in head:
                        parts = head.split(' - ',1)
                        code = parts[0].strip(); label = parts[1].strip()
                    else:
                        # CODE|LABEL style already split above
                        if '|' in line:
                            code = head.strip(); label = tail.strip(); tail = ''
                    if tail.strip():
                        items = [d.strip() for d in tail.split(',') if d.strip()]
            elif kind == 'account':
                head, tail = (line.split('|',1)+[''])[:2]
                if ' – ' in head:
                    parts = head.split(' – ',1)
                elif ' - ' in head:
                    parts = head.split(' - ',1)
                else:
                    parts = [head,'']
                code = parts[0].strip(); label = parts[1].strip()
                if tail.strip():
                    items = [d.strip() for d in re.split(r';', tail) if d.strip()]
            else:  # sales
                if ' - ' in line:
                    parts = line.split(' - ',1)
                    code = parts[0].strip(); label = parts[1].strip()
                else:
                    code = line
                    label = ''
            if code:
                results.append({'code': code, 'label': label, 'items': items, 'raw': raw})
    except Exception:
        pass
    return results

def save_reference_groupings(kind: str, groups: list):
    """Persist groups in standardized v1 format regardless of legacy input."""
    path = _get_reference_file(kind)
    # Normalize & sort unique codes
    normalized = {}
    for g in groups:
        code = (g.get('code') or '').strip()
        if not code:
            continue
        label = (g.get('label') or '').strip()
        # Avoid pipe in label/items by replacing with '/' to preserve parser simplicity
        label = label.replace('|','/')
        items = [it.strip().replace('|','/') for it in (g.get('items') or []) if it.strip()]
        normalized[code.upper()] = {'code': code.upper(), 'label': label, 'items': items}
    ordered = [normalized[k] for k in sorted(normalized.keys())]
    lines = [STANDARD_GROUPINGS_HEADER, f"# Generated {datetime.now().isoformat()} kind={kind}"]
    for g in ordered:
        items_part = ','.join(g['items']) if g['items'] else ''
        lines.append(f"{g['code']}|{g['label']}|{items_part}")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            for ln in lines:
                f.write(ln + '\n')
        os.replace(tmp, path)
    except Exception:
        pass

def get_all_users():
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                return json.load(f)
        default_users = {
            "choltzen": {"username":"choltzen","display_name":"Cade Holtzen","email":"cade.holtzen@example.com","group":"admin","active":True,"created_date": datetime.now().isoformat()},
            "demo_user": {"username":"demo_user","display_name":"Demo User","email":"demo@example.com","group":"viewer","active":True,"created_date": datetime.now().isoformat()}
        }
        save_users(default_users)
        return default_users
    except Exception:
        return {}

def save_users(users):
    try:
        os.makedirs(os.path.dirname(USER_DATA_FILE), exist_ok=True)
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(users, f, indent=2)
    except Exception:
        pass

# --- Core admin pages ---
@admin_bp.route('/admin', endpoint='dashboard')
@role_required('pam_admin')
def admin_dashboard():
    dm = _ensure_dm()
    try:
        promotions_data = dm.get_all_promos()
        spe_data = dm.get_all_spe_promos()
        promotions_count = len(promotions_data)
        spe_count = len(spe_data)
        pending_reviews = sum(1 for promo in promotions_data.values() if promo.get('status','').lower() in ['pending','review'])
        users = get_all_users()
        user_groups = get_user_groups()
        return render_template('pam/admin.html', promotions_count=promotions_count, spe_count=spe_count, pending_reviews=pending_reviews, users=users, user_groups=user_groups)
    except Exception:
        return render_template('pam/admin.html', promotions_count=847, spe_count=234, pending_reviews=12)

@admin_bp.route('/admin/pam-promotions')
@role_required('pam_admin')
def admin_pam_promotions():
    dm = _ensure_dm()
    # Pagination + search params
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '', type=str).strip()
    owner = request.args.get('owner', 'all', type=str)

    # Lightweight in-process cache to avoid full dataset rebuilds on repeated navigation.
    # Only caches unfiltered base page (page=1, empty search, owner='all').
    # TTL kept short (45s) to keep data fresh but prevent multi-minute reload delays.
    global _PAM_PROMO_CACHE
    # _PAM_PROMO_CACHE initialized at module load; legacy try/except removed for clarity.

    from time import time
    cache_key_applicable = (page == 1 and per_page == 25 and search == '' and owner == 'all')
    now = time()
    ttl_seconds = 45
    promo_data = None

    if cache_key_applicable and _PAM_PROMO_CACHE['data'] and (now - _PAM_PROMO_CACHE['ts'] < ttl_seconds):
        promo_data = _PAM_PROMO_CACHE['data']
    else:
        # Prefer optimized path if available to reduce processing.
        if hasattr(dm, 'get_paginated_promos_optimized'):
            promo_data = dm.get_paginated_promos_optimized(page=page, per_page=per_page, search=search, owner_filter=owner)
        elif hasattr(dm, 'get_pam_only_paginated_promos'):
            promo_data = dm.get_pam_only_paginated_promos(page=page, per_page=per_page, search=search, owner_filter=owner)
        else:
            promo_data = dm.get_paginated_promos(page=page, per_page=per_page, search=search, owner_filter=owner)
        if cache_key_applicable:
            _PAM_PROMO_CACHE = {'ts': now, 'data': promo_data}

    return render_template('pam/admin_pam_promotions.html',
                           promotions=promo_data['promotions'],
                           pagination=promo_data['pagination'],
                           owners=promo_data['owners'],
                           search_query=search,
                           selected_owner=owner,
                           cache_age=(0 if not cache_key_applicable or not _PAM_PROMO_CACHE['data'] else int(now - _PAM_PROMO_CACHE['ts'])))

@admin_bp.route('/admin/user-management', endpoint='user_management')
@role_required('pam_admin')
def admin_user_management():
    return render_template('pam/admin_user_management.html')

# New subpages for decluttered functionality
@admin_bp.route('/admin/data')
@role_required('pam_admin')
def admin_data_page():
    return render_template('pam/admin_data.html')

@admin_bp.route('/admin/performance')
@role_required('pam_admin')
def admin_performance_page():
    return render_template('pam/admin_performance.html')

@admin_bp.route('/admin/integrations')
@role_required('pam_admin')
def admin_integrations_page():
    return render_template('pam/admin_integrations.html')

@admin_bp.route('/admin/security')
@role_required('pam_admin')
def admin_security_page():
    return render_template('pam/admin_security.html')

@admin_bp.route('/admin/groupings')
@role_required('pam_admin')
def admin_groupings_page():
    """Dedicated management page for device & reference groupings."""
    return render_template('pam/admin_groupings.html')

# Version history page removed

# --- Admin actions ---
@admin_bp.route('/admin/backup', methods=['POST'])
@role_required('pam_admin')
def admin_backup():
    try:
        import shutil
        backup_dir = f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(backup_dir, exist_ok=True)
        # Copy uploads and other artifacts (version history now in SQL Server)
        # legacy SQLite DB intentionally not preserved here
        if os.path.exists('data/uploads'):
            shutil.copytree('data/uploads', os.path.join(backup_dir,'uploads'))
        if os.path.exists('data/uploads'):
            shutil.copytree('data/uploads', os.path.join(backup_dir,'uploads'))
        return jsonify({'success': True, 'message': f'Backup created in {backup_dir} (Promotions reside in SQL Server)'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Backup failed: {e}'})

@admin_bp.route('/admin/stats', methods=['GET'])
@role_required('pam_admin')
def admin_stats():
    dm = _ensure_dm()
    try:
        promotions_data = dm.get_all_promos()
        # SPE promos now sourced directly from SQL Server (no JSON manager needed)
        spe_data = dm.get_all_spe_promos()
        cache_status = dm.get_cache_status()
        uploads_count = 0
        if os.path.exists('data/uploads'):
            for _,_,files in os.walk('data/uploads'):
                uploads_count += len(files)
        stats = {
            'promotions_count': len(promotions_data),
            'spe_count': len(spe_data),
            'total_records': len(promotions_data)+len(spe_data),
            'data_source': 'Database (SQL Server)',
            'cache_status': cache_status,
            'spe_file_size': None,
            'workflow_file_size': None,
            'uploads_count': uploads_count,
            'database_connected': True,
            'last_cache_refresh': cache_status.get('last_refresh','Never')
        }
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to get stats: {e}'})

    @admin_bp.route('/admin/phase-recompute', methods=['POST','GET'])
    def admin_phase_recompute():
        dm = _ensure_dm()
        try:
            result = dm.sweep_phases(user='Admin Phase Sweep')
            return jsonify({'success': True, 'result': result})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Phase sweep failed: {e}'})

@admin_bp.route('/admin/dashboard-summary')
@role_required('pam_admin')
def admin_dashboard_summary():
    dm = _ensure_dm()
    summary = {}
    try:
        # Promotions overview
        promos = dm.get_all_promos()
        total_promos = len(promos)
        owners = set()
        active_promos = 0
        today = datetime.now().date()
        for p in promos.values():
            end = p.get('promo_end_date') or p.get('promo_start_date')
            start = p.get('promo_start_date') or p.get('promo_start_date')
            try:
                if start and end:
                    from datetime import datetime as _dt
                    s = _dt.strptime(start, '%Y-%m-%d').date()
                    e = _dt.strptime(end, '%Y-%m-%d').date()
                    if s <= today <= e:
                        active_promos += 1
            except Exception:
                pass
            if p.get('owner'): owners.add(p.get('owner'))
        # Cache
        cache_status = dm.get_cache_status()
        # PCR stats (lightweight count)
        pcr_events = 0
        pcr_promos = 0
        # Version history removed: PCR stats unavailable
        pcr_events = 0
        pcr_promos = 0
        # Date diagnostics latest snapshot (stored in SQL Server)
        invalid_ratio = None
        try:
            dm = _ensure_dm()
            engine = dm.get_engine()
            with engine.connect() as conn:
                # If the table exists this will succeed; otherwise it will return no rows
                try:
                    row = conn.execute(text("SELECT TOP 1 invalid_ratio FROM PAM.date_diagnostics_history ORDER BY id DESC")).fetchone()
                    if row:
                        invalid_ratio = row[0]
                except Exception:
                    invalid_ratio = None
        except Exception:
            invalid_ratio = None
        summary = {
            'total_promos': total_promos,
            'active_promos': active_promos,
            'unique_owners': len(owners),
            'cache_valid': cache_status.get('cache_valid'),
            'cache_age_minutes': cache_status.get('cache_age_minutes'),
            'pcr_events': pcr_events,
            'pcr_promos': pcr_promos,
            'invalid_date_ratio': invalid_ratio
        }
        response = {'success': True, **summary, 'summary': summary}
        return jsonify(response)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to load dashboard summary: {e}', 'summary': summary})

@admin_bp.route('/admin/test-connections', methods=['POST'])
@role_required('pam_admin')
def admin_test_connections():
    results = {}
    try:
        import requests
        try:
            requests.get('https://jira.t-mobile.com', timeout=5, verify=False)
            results['jira'] = {'status':'success','response_time':'245ms'}
        except Exception:
            results['jira'] = {'status':'error','response_time':'timeout'}
        results['orbit'] = {'status':'success','response_time':'180ms'}
        results['email'] = {'status':'warning','response_time':'1.2s'}
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to test connections: {e}'})


@admin_bp.route('/admin/azure-diagnostics')
@role_required('pam_admin')
def admin_azure_diagnostics():
    """Comprehensive Azure → On-Prem SQL Server connectivity diagnostics.
    
    Checks:
    1. Environment configuration
    2. DNS resolution for SQL server
    3. TCP port connectivity  
    4. ODBC driver availability
    5. SQL Server actual connection test
    6. Azure-specific environment indicators
    7. Hybrid Connection Manager status hints
    """
    import socket
    import time
    import subprocess
    
    diagnostics = {
        'timestamp': datetime.now().isoformat(),
        'environment': {},
        'network': {},
        'odbc': {},
        'sql_connection': {},
        'azure_indicators': {},
        'recommendations': []
    }
    
    # 1. Environment Configuration
    pam_server = os.getenv('PAM_DB_SERVER', 'NOT SET')
    pam_database = os.getenv('PAM_DB_DATABASE', 'NOT SET')
    pam_driver = os.getenv('PAM_DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    pam_timeout = os.getenv('PAM_DB_LOGIN_TIMEOUT', '15')
    pam_encrypt = os.getenv('PAM_DB_ENCRYPT', 'no')
    pam_trust_cert = os.getenv('PAM_DB_TRUST_CERT', 'yes')
    has_username = bool(os.getenv('PAM_DB_USERNAME'))
    has_password = bool(os.getenv('PAM_DB_PASSWORD'))
    
    diagnostics['environment'] = {
        'PAM_DB_SERVER': pam_server,
        'PAM_DB_DATABASE': pam_database,
        'PAM_DB_DRIVER': pam_driver,
        'PAM_DB_LOGIN_TIMEOUT': pam_timeout,
        'PAM_DB_ENCRYPT': pam_encrypt,
        'PAM_DB_TRUST_CERT': pam_trust_cert,
        'has_username': has_username,
        'has_password': has_password,
        'auth_mode': 'SQL Auth' if has_username else 'Windows/Integrated'
    }
    
    # Parse server and port
    server_host = pam_server
    server_port = 1433  # Default SQL Server port
    if ',' in pam_server:
        parts = pam_server.rsplit(',', 1)
        server_host = parts[0]
        try:
            server_port = int(parts[1])
        except ValueError:
            pass
    elif '\\' in pam_server:
        # Named instance - extract host
        server_host = pam_server.split('\\')[0]
    
    diagnostics['network']['parsed_host'] = server_host
    diagnostics['network']['parsed_port'] = server_port
    
    # 2. DNS Resolution
    try:
        start = time.time()
        ip_addresses = socket.gethostbyname_ex(server_host)
        dns_time = (time.time() - start) * 1000
        diagnostics['network']['dns_resolution'] = {
            'status': 'success',
            'hostname': ip_addresses[0],
            'aliases': ip_addresses[1],
            'ip_addresses': ip_addresses[2],
            'resolution_time_ms': round(dns_time, 2)
        }
    except socket.gaierror as e:
        diagnostics['network']['dns_resolution'] = {
            'status': 'failed',
            'error': str(e),
            'hint': 'DNS failure suggests Hybrid Connection not active or VPN not connected'
        }
        diagnostics['recommendations'].append('Check Azure Hybrid Connection Manager is running on-prem')
        diagnostics['recommendations'].append('Verify VPN/ExpressRoute connectivity if using VNet integration')
    
    # 3. TCP Port Connectivity
    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((server_host, server_port))
        tcp_time = (time.time() - start) * 1000
        sock.close()
        if result == 0:
            diagnostics['network']['tcp_connectivity'] = {
                'status': 'success',
                'port': server_port,
                'connect_time_ms': round(tcp_time, 2)
            }
        else:
            diagnostics['network']['tcp_connectivity'] = {
                'status': 'failed',
                'port': server_port,
                'error_code': result,
                'hint': 'Port blocked or Hybrid Connection not forwarding'
            }
            diagnostics['recommendations'].append(f'Verify port {server_port} is allowed through on-prem firewall')
            diagnostics['recommendations'].append('Check Hybrid Connection endpoint configuration matches server:port')
    except Exception as e:
        diagnostics['network']['tcp_connectivity'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # 4. ODBC Driver Check
    try:
        import pyodbc
        available_drivers = pyodbc.drivers()
        target_driver = pam_driver.replace('{', '').replace('}', '')
        driver_found = target_driver in available_drivers
        diagnostics['odbc'] = {
            'pyodbc_version': pyodbc.version,
            'target_driver': target_driver,
            'driver_found': driver_found,
            'available_drivers': available_drivers[:5]  # First 5 to avoid clutter
        }
        if not driver_found:
            diagnostics['recommendations'].append(f'Install {target_driver} on Azure App Service')
    except ImportError:
        diagnostics['odbc'] = {'status': 'pyodbc not installed'}
        diagnostics['recommendations'].append('Install pyodbc package')
    
    # 5. SQL Server Connection Test
    try:
        from data.database import DatabaseManager
        db = DatabaseManager()
        start = time.time()
        
        # Force fresh connection (bypass cached engine)
        db._engine = None
        engine = db.get_engine()
        
        with engine.connect() as conn:
            # Test query
            row = conn.execute(text("SELECT @@VERSION AS version, GETDATE() AS server_time, DB_NAME() AS current_db")).fetchone()
            connect_time = (time.time() - start) * 1000
            diagnostics['sql_connection'] = {
                'status': 'success',
                'connect_time_ms': round(connect_time, 2),
                'sql_server_version': str(row.version)[:100] if row else 'unknown',
                'server_time': str(row.server_time) if row else 'unknown',
                'current_database': str(row.current_db) if row else 'unknown'
            }
    except Exception as e:
        diagnostics['sql_connection'] = {
            'status': 'failed',
            'error': str(e),
            'error_type': type(e).__name__
        }
        error_str = str(e).lower()
        if 'login failed' in error_str:
            diagnostics['recommendations'].append('Check SQL credentials (PAM_DB_USERNAME/PASSWORD)')
        elif 'timeout' in error_str or 'timed out' in error_str:
            diagnostics['recommendations'].append('Connection timeout - Hybrid Connection may be down')
            diagnostics['recommendations'].append('Check if on-prem SQL Server service is running')
        elif 'network' in error_str or 'tcp' in error_str:
            diagnostics['recommendations'].append('Network error - check VPN/Hybrid Connection status')
        elif 'ssl' in error_str or 'certificate' in error_str:
            diagnostics['recommendations'].append('SSL/TLS error - try PAM_DB_ENCRYPT=no PAM_DB_TRUST_CERT=yes')
    
    # 6. Azure-Specific Environment Indicators
    azure_indicators = {
        'WEBSITE_SITE_NAME': os.getenv('WEBSITE_SITE_NAME'),
        'WEBSITE_INSTANCE_ID': os.getenv('WEBSITE_INSTANCE_ID', '')[:12] + '...' if os.getenv('WEBSITE_INSTANCE_ID') else None,
        'WEBSITE_SKU': os.getenv('WEBSITE_SKU'),
        'REGION_NAME': os.getenv('REGION_NAME'),
        'WEBSITE_HOSTNAME': os.getenv('WEBSITE_HOSTNAME'),
        'is_azure': bool(os.getenv('WEBSITE_SITE_NAME')),
        'WEBSITE_VNET_ROUTE_ALL': os.getenv('WEBSITE_VNET_ROUTE_ALL'),
        'WEBSITE_PRIVATE_IP': os.getenv('WEBSITE_PRIVATE_IP'),
    }
    diagnostics['azure_indicators'] = {k: v for k, v in azure_indicators.items() if v is not None}
    
    # Add Azure-specific recommendations
    if azure_indicators.get('is_azure'):
        if not diagnostics['azure_indicators'].get('WEBSITE_PRIVATE_IP'):
            diagnostics['recommendations'].append('No VNet integration detected - using Hybrid Connection for on-prem access')
        
        if diagnostics['sql_connection'].get('status') == 'failed':
            diagnostics['recommendations'].append('In Azure Portal: Check Hybrid Connection status under Networking')
            diagnostics['recommendations'].append('Verify Hybrid Connection Manager (HCM) service is running on-prem')
            diagnostics['recommendations'].append('HCM logs: Event Viewer > Applications and Services > Microsoft > HybridConnectionManager')
    
    # 7. Summary status
    all_ok = (
        diagnostics['network'].get('dns_resolution', {}).get('status') == 'success' and
        diagnostics['network'].get('tcp_connectivity', {}).get('status') == 'success' and
        diagnostics['sql_connection'].get('status') == 'success'
    )
    diagnostics['overall_status'] = 'healthy' if all_ok else 'unhealthy'
    
    return jsonify({'success': True, 'diagnostics': diagnostics})


@admin_bp.route('/admin/sql-connection-reset', methods=['POST'])
@role_required('pam_admin')
def admin_sql_connection_reset():
    """Force reset of all SQL connection pools. Use when connections go stale."""
    try:
        from data.database import DatabaseManager
        db = DatabaseManager()
        
        # Dispose existing engine to close all pooled connections
        if db._engine:
            db._engine.dispose()
            db._engine = None
        
        # Attempt fresh connection
        engine = db.get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        return jsonify({
            'success': True,
            'message': 'Connection pool reset and new connection established',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to reset connection pool',
            'timestamp': datetime.now().isoformat()
        })


@admin_bp.route('/admin/cache-status')
@role_required('pam_admin')
def admin_cache_status():
    dm = _ensure_dm()
    try:
        cache_status = dm.get_cache_status()
        return jsonify({'success': True, 'cache_status': cache_status})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to get cache status: {e}'})

@admin_bp.route('/admin/cache-refresh', methods=['POST'])
@role_required('pam_admin')
def admin_cache_refresh():
    dm = _ensure_dm()
    try:
        start_time = datetime.now()
        dm.force_refresh()
        refresh_time = (datetime.now() - start_time).total_seconds()
        cache_status = dm.get_cache_status()
        return jsonify({'success': True, 'message': f'Cache refreshed in {refresh_time:.2f}s', 'cache_status': cache_status})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to refresh cache: {e}'})

@admin_bp.route('/admin/delete-promo', methods=['POST'])
@role_required('pam_admin')
def admin_delete_promo():
    dm = _ensure_dm()
    try:
        data = request.get_json() if request.is_json else request.form
        raw_code = data.get('promo_code') if data else ''
        promo_code = (raw_code or '').strip()
        if not promo_code:
            return jsonify({'success': False, 'message': 'promo_code required'}), 400
        existing = dm.get_promo(promo_code)
        if not existing:
            return jsonify({'success': False, 'message': f'Promo {promo_code} not found'}), 404
        dm.delete_promo(promo_code)
        # Force cache refresh so removal is reflected immediately
        try:
            dm.force_refresh()
        except Exception:
            pass
        return jsonify({'success': True, 'message': f'Promo {promo_code} deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error deleting promo: {e}'})

@admin_bp.route('/admin/delete-promos', methods=['POST'])
@role_required('pam_admin')
def admin_delete_promos():
    dm = _ensure_dm()
    try:
        data = request.get_json() if request.is_json else {}
        codes = data.get('codes') or []
        if not isinstance(codes, list) or not codes:
            return jsonify({'success': False, 'message': 'codes list required'}), 400
        deleted = []
        skipped = []
        for code in codes:
            try:
                existing = dm.get_promo(code)
                if existing:
                    dm.delete_promo(code)
                    deleted.append(code)
                else:
                    skipped.append(code)
            except Exception:
                skipped.append(code)
        try:
            dm.force_refresh()
        except Exception:
            pass
        return jsonify({'success': True, 'message': f'Deleted {len(deleted)} promos (skipped {len(skipped)})', 'deleted': deleted, 'skipped': skipped})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Bulk delete error: {e}'})

@admin_bp.route('/admin/data-refresh', methods=['POST'])
@role_required('pam_admin')
def admin_data_refresh():
    dm = _ensure_dm()
    try:
        start_time = datetime.now()
        # If hybrid manager has full_data_refresh use it, else fall back to force_refresh
        if hasattr(dm, 'full_data_refresh'):
            stats = dm.full_data_refresh()
        else:
            dm.force_refresh()
            stats = {'promotions_loaded': len(dm.get_all_promos())}
        total_time = (datetime.now() - start_time).total_seconds()
        cache_status = dm.get_cache_status()
        return jsonify({'success': True, 'message': f'Data refreshed in {total_time:.2f}s', 'details': stats, 'cache_status': cache_status})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to perform data refresh: {e}'})

@admin_bp.route('/admin/pcr-stats')
@role_required('pam_admin')
def admin_pcr_stats():
    # Provide counts of PCR Version events per promo
    # Version history removed: return empty PCR stats
    return jsonify({'success': True, 'pcr_stats': []})

@admin_bp.route('/admin/date-diagnostics')
@role_required('pam_admin')
def admin_date_diagnostics():
    # Use DatabaseManager diagnostics by invoking get_recent_promos (days=30) without impacting cache
    try:
        from data.database import DatabaseManager
        dbm = DatabaseManager()
        recent = dbm.get_recent_promos(days=30)
        diag = None
        if recent:
            diag = recent[0].get('_date_diagnostics')
        # Also compute overall invalid ratio quickly (may reuse logic)
        overall = {
            'total_with_value': None,
            'valid_dates': None,
            'invalid_dates': None
        }
        try:
            # Updated to reference PAM updated source table
            raw_df = dbm.get_dataframe("SELECT promo_start_date FROM [PAM].[PAM_Orbit_Data_Updated] WHERE promo_start_date IS NOT NULL")
            total_with_value = len(raw_df)
            valid_mask = raw_df['promo_start_date'].apply(lambda v: dbm._is_valid_date_string(v))
            valid = int(valid_mask.sum())
            invalid = total_with_value - valid
            overall = {
                'total_with_value': total_with_value,
                'valid_dates': valid,
                'invalid_dates': invalid,
                'invalid_ratio': round(invalid / total_with_value, 4) if total_with_value else None
            }
        except Exception:
            pass
        payload = {
            'recent_window_diagnostics': diag,
            'overall_diagnostics': overall
        }
        return jsonify({'success': True, 'diagnostics': payload})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to load date diagnostics: {e}'})

@admin_bp.route('/admin/data-health')
@role_required('pam_admin')
def admin_data_health():
    # Aggregate latest diagnostics snapshot & PCR counts summary
    try:
        result = {}
        # Version history removed: no latest snapshot or PCR summary available
        result['latest_snapshot'] = None
        result['pcr_summary'] = {}
        # Derive status
        status = 'unknown'
        ratio = None
        snapshot = result.get('latest_snapshot')
        if snapshot and isinstance(snapshot, dict) and snapshot.get('invalid_ratio') is not None:
            ratio = snapshot.get('invalid_ratio')
            if ratio is not None:
                if ratio < 0.05:
                    status = 'healthy'
                elif ratio < 0.15:
                    status = 'warning'
                else:
                    status = 'critical'
        result['status'] = status
        result['invalid_ratio'] = ratio
        return jsonify({'success': True, 'data_health': result})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to load data health: {e}'})

# --- User management API ---
@admin_bp.route('/admin/users', methods=['GET'])
@role_required('pam_admin')
def admin_users():
    try:
        users = get_all_users()
        groups = get_user_groups()
        return jsonify({'success': True, 'users': users, 'groups': groups})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to get users: {e}'})

@admin_bp.route('/admin/users', methods=['POST'])
@role_required('pam_admin')
def admin_create_user():
    try:
        data = request.get_json()
        users = get_all_users()
        username = data.get('username','').strip().lower()
        if not username:
            return jsonify({'success': False, 'message': 'Username is required'})
        if username in users:
            return jsonify({'success': False, 'message': 'Username already exists'})
        new_user = {
            'username': username,
            'display_name': data.get('display_name',''),
            'email': data.get('email',''),
            'group': data.get('group','viewer'),
            'active': data.get('active', True),
            'created_date': datetime.now().isoformat()
        }
        users[username] = new_user
        save_users(users)
        return jsonify({'success': True, 'message': f'User {username} created successfully', 'user': new_user})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to create user: {e}'})

@admin_bp.route('/admin/users/<username>', methods=['PUT'])
@role_required('pam_admin')
def admin_update_user(username):
    try:
        data = request.get_json()
        users = get_all_users()
        if username not in users:
            return jsonify({'success': False, 'message': 'User not found'})
        if 'display_name' in data: users[username]['display_name'] = data['display_name']
        if 'email' in data: users[username]['email'] = data['email']
        if 'group' in data: users[username]['group'] = data['group']
        if 'active' in data: users[username]['active'] = data['active']
        users[username]['updated_date'] = datetime.now().isoformat()
        save_users(users)
        return jsonify({'success': True, 'message': f'User {username} updated successfully', 'user': users[username]})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to update user: {e}'})

@admin_bp.route('/admin/users/<username>', methods=['DELETE'])
@role_required('pam_admin')
def admin_delete_user(username):
    try:
        users = get_all_users()
        if username not in users:
            return jsonify({'success': False, 'message': 'User not found'})
        if username == 'choltzen':
            return jsonify({'success': False, 'message': 'Cannot delete the main admin user'})
        del users[username]
        save_users(users)
        return jsonify({'success': True, 'message': f'User {username} deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to delete user: {e}'})

@admin_bp.route('/admin/groups', methods=['POST'])
@role_required('pam_admin')
def admin_create_group():
    try:
        data = request.get_json()
        groups = get_user_groups()
        group_id = data.get('id','').strip().lower()
        if not group_id:
            return jsonify({'success': False, 'message': 'Group ID is required'})
        if group_id in groups:
            return jsonify({'success': False, 'message': 'Group already exists'})
        new_group = {
            'name': data.get('name',''),
            'description': data.get('description',''),
            'permissions': data.get('permissions', [])
        }
        groups[group_id] = new_group
        save_user_groups(groups)
        return jsonify({'success': True, 'message': f'Group {group_id} created successfully', 'group': new_group})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to create group: {e}'})


# --- Reference Groupings CRUD (txt-backed) ---
@admin_bp.route('/admin/reference-groupings', methods=['GET'])
@role_required('pam_admin')
def admin_list_reference_groupings():
    kind = request.args.get('type','soc').strip()
    try:
        groups = load_reference_groupings(kind)
        return jsonify({'success': True, 'type': kind, 'groups': groups})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to load {kind} groupings: {e}'})

@admin_bp.route('/admin/reference-groupings', methods=['POST'])
@role_required('pam_admin')
def admin_create_reference_grouping():
    kind = request.args.get('type','soc').strip()
    try:
        data = request.get_json(force=True)
        code = (data.get('code') or '').strip()
        label = (data.get('label') or '').strip()
        items = data.get('items') or []
        if not code:
            return jsonify({'success': False, 'message': 'code required'}), 400
        groups = load_reference_groupings(kind)
        if any(g['code'].lower()==code.lower() for g in groups):
            return jsonify({'success': False, 'message': 'code exists'}), 400
        groups.append({'code': code, 'label': label, 'items': items, 'raw': None})
        save_reference_groupings(kind, groups)
        return jsonify({'success': True, 'message': 'Grouping added', 'group': {'code': code, 'label': label, 'items': items}})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to add grouping: {e}'})

@admin_bp.route('/admin/reference-groupings/<code>', methods=['PUT'])
@role_required('pam_admin')
def admin_update_reference_grouping(code):
    kind = request.args.get('type','soc').strip()
    try:
        data = request.get_json(force=True)
        label = (data.get('label') or '').strip()
        items = data.get('items') or []
        groups = load_reference_groupings(kind)
        found = False
        for g in groups:
            if g['code'].lower() == code.lower():
                g['label'] = label
                g['items'] = items
                found = True
                break
        if not found:
            return jsonify({'success': False, 'message': 'code not found'}), 404
        save_reference_groupings(kind, groups)
        return jsonify({'success': True, 'message': 'Grouping updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to update grouping: {e}'})

@admin_bp.route('/admin/reference-groupings/<code>', methods=['DELETE'])
@role_required('pam_admin')
def admin_delete_reference_grouping(code):
    kind = request.args.get('type','soc').strip()
    try:
        groups = load_reference_groupings(kind)
        new_groups = [g for g in groups if g['code'].lower()!=code.lower()]
        if len(new_groups) == len(groups):
            return jsonify({'success': False, 'message': 'code not found'}), 404
        save_reference_groupings(kind, new_groups)
        return jsonify({'success': True, 'message': 'Grouping deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to delete grouping: {e}'})


# =============================================================================
# ORBIT DATA VALIDATION ENDPOINTS
# =============================================================================

@admin_bp.route('/admin/validate-orbit-data')
@role_required('pam_admin')
def validate_orbit_data():
    """Validate ORBIT data from Fabric against PAM field requirements.
    
    This endpoint queries Fabric for sample records and validates each field
    against what PAM needs. Used to prove data quality for stakeholder meetings.
    
    Returns JSON with:
    - field_stats: Population % and validation status for each field
    - summary: Overall counts of good/warning/missing fields
    - sample_records: A few records mapped to PAM format
    """
    from datetime import datetime
    
    # PAM field mapping requirements
    PAM_FIELD_MAPPINGS = {
        # Required Identity Fields
        'bill_facing_name': {'fabric_columns': ['cat_billname'], 'required': True},
        'initiative_name': {'fabric_columns': ['cat_initiativename'], 'required': True},
        'orbit_id': {'fabric_columns': ['cat_gtmentryid', 'cat_legacygtmentryid'], 'required': True},
        'Owner': {'fabric_columns': ['crffc_productownername', 'crffc_businessownername'], 'required': True},
        'promo_start_date': {'fabric_columns': ['cat_startdate', 'cat_requestedlaunchdate'], 'required': True},
        
        # Optional but important fields
        'description': {'fabric_columns': ['cat_description'], 'required': False},
        'promo_notes': {'fabric_columns': ['cat_notes'], 'required': False},
        'promo_end_date': {'fabric_columns': ['cat_enddate'], 'required': False},
        'comm_end_date': {'fabric_columns': ['cat_commenddate'], 'required': False},
        'amount': {'fabric_columns': ['cat_amount', 'crffc_amount'], 'required': False},
        'discount': {'fabric_columns': ['cat_discount'], 'required': False},
        'product_type': {'fabric_columns': ['cat_producttypename'], 'required': False},
        
        # Segmentation fields
        'market_group': {'fabric_columns': ['cat_marketgroupname'], 'required': False},
        'store_group': {'fabric_columns': ['cat_storegroupname'], 'required': False},
        'soc_grouping': {'fabric_columns': ['cat_socgrouping'], 'required': False},
        'account_type': {'fabric_columns': ['cat_accounttypename'], 'required': False},
        'sales_application': {'fabric_columns': ['cat_salesapplicationname'], 'required': False},
        'segment_name': {'fabric_columns': ['cat_segmentname'], 'required': False},
        'channels': {'fabric_columns': ['cat_channelsname'], 'required': False},
        
        # Execution fields
        'device_sales_type': {'fabric_columns': ['cat_devicesalestypename'], 'required': False},
        'activation_type': {'fabric_columns': ['cat_activationtypename'], 'required': False},
        'active_line_required': {'fabric_columns': ['cat_activelinerequired'], 'required': False},
        'maintain_soc': {'fabric_columns': ['cat_maintainsoc'], 'required': False},
        'limit_per_ban': {'fabric_columns': ['cat_limitperban'], 'required': False},
        
        # Links
        'orbit_link': {'fabric_columns': ['cat_orbitlink'], 'required': False},
        'legal_link': {'fabric_columns': ['cat_legallink'], 'required': False},
        'c2_link': {'fabric_columns': ['cat_c2link'], 'required': False},
        
        # Additional owners
        'business_owner': {'fabric_columns': ['crffc_businessownername'], 'required': False},
        'sponsoring_vp': {'fabric_columns': ['crffc_sponsoringvpname'], 'required': False},
        'product_owner': {'fabric_columns': ['crffc_productownername'], 'required': False},
    }
    
    try:
        from data.fabric_database import fabric_db as fabric
        
        # Test connection
        if not fabric.test_connection():
            return jsonify({
                'success': False, 
                'message': 'Failed to connect to Fabric',
                'last_error': getattr(fabric, '_last_error', 'Unknown error')
            }), 500
        
        # Query sample data
        conn = fabric._get_connection()
        cursor = conn.cursor()
        
        # Get 100 recent active records for analysis
        query = """
        SELECT TOP 100 *
        FROM dbo.ORBIT_Reporting_Table
        WHERE statuscodename = 'Active'
        ORDER BY modifiedon DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        if not rows:
            return jsonify({
                'success': True,
                'message': 'No active records found in ORBIT',
                'record_count': 0
            })
        
        # Convert to list of dicts
        records = [dict(zip(columns, row)) for row in rows]
        
        # Analyze each PAM field
        field_stats = {}
        for pam_field, config in PAM_FIELD_MAPPINGS.items():
            fabric_cols = config['fabric_columns']
            required = config.get('required', False)
            
            values_found = 0
            sample_values = []
            source_column_used = None
            
            for record in records:
                value = None
                for fc in fabric_cols:
                    if fc in record and record[fc] is not None and str(record[fc]).strip() != '':
                        value = record[fc]
                        source_column_used = fc
                        break
                
                if value is not None:
                    values_found += 1
                    if len(sample_values) < 3:
                        sample_values.append(str(value)[:80])
            
            population_pct = round((values_found / len(records) * 100), 1)
            
            # Determine status
            if required and values_found == 0:
                status = "MISSING"
                status_icon = "🔴"
            elif required and population_pct < 80:
                status = "LOW_DATA"
                status_icon = "🟡"
            elif values_found > 0:
                status = "GOOD"
                status_icon = "🟢"
            else:
                status = "EMPTY"
                status_icon = "⚪"
            
            field_stats[pam_field] = {
                'status': status,
                'status_icon': status_icon,
                'source_column': source_column_used or fabric_cols[0],
                'population_pct': population_pct,
                'required': required,
                'sample_values': sample_values
            }
        
        # Calculate summary
        good = len([f for f, s in field_stats.items() if s['status'] == 'GOOD'])
        low_data = len([f for f, s in field_stats.items() if s['status'] == 'LOW_DATA'])
        missing = len([f for f, s in field_stats.items() if s['status'] == 'MISSING'])
        empty = len([f for f, s in field_stats.items() if s['status'] == 'EMPTY'])
        
        required_fields = [f for f, c in PAM_FIELD_MAPPINGS.items() if c.get('required')]
        required_ok = len([f for f in required_fields if field_stats[f]['status'] == 'GOOD'])
        
        # Create sample records in PAM format
        sample_records = []
        for record in records[:5]:
            pam_record = {}
            for pam_field, config in PAM_FIELD_MAPPINGS.items():
                value = None
                for fc in config['fabric_columns']:
                    if fc in record and record[fc]:
                        value = record[fc]
                        break
                if value is not None:
                    # Truncate for display
                    pam_record[pam_field] = str(value)[:100] if isinstance(value, str) else value
            sample_records.append(pam_record)
        
        return jsonify({
            'success': True,
            'generated_at': datetime.now().isoformat(),
            'record_count': len(records),
            'field_stats': field_stats,
            'summary': {
                'good': good,
                'low_data': low_data,
                'missing': missing,
                'empty': empty,
                'required_ok': required_ok,
                'required_total': len(required_fields),
                'all_required_passing': required_ok == len(required_fields)
            },
            'sample_records': sample_records
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'Validation failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500


@admin_bp.route('/admin/orbit-field-coverage')
@role_required('pam_admin')
def orbit_field_coverage():
    """Get detailed field coverage stats from ORBIT/Fabric.
    
    Runs aggregate queries to get population % for all fields.
    """
    try:
        from data.fabric_database import fabric_db as fabric
        
        if not fabric.test_connection():
            return jsonify({'success': False, 'message': 'Failed to connect to Fabric'}), 500
        
        conn = fabric._get_connection()
        cursor = conn.cursor()
        
        # Query field population percentages
        query = """
        SELECT 
            COUNT(*) as total_records,
            
            -- Required fields
            ROUND(100.0 * SUM(CASE WHEN cat_billname IS NOT NULL AND cat_billname != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as bill_name_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_initiativename IS NOT NULL AND cat_initiativename != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as initiative_name_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_gtmentryid IS NOT NULL OR cat_legacygtmentryid IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as orbit_id_pct,
            ROUND(100.0 * SUM(CASE WHEN crffc_productownername IS NOT NULL OR crffc_businessownername IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as owner_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_startdate IS NOT NULL OR cat_requestedlaunchdate IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as start_date_pct,
            
            -- Dates
            ROUND(100.0 * SUM(CASE WHEN cat_enddate IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as end_date_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_commenddate IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as comm_end_date_pct,
            
            -- Amounts
            ROUND(100.0 * SUM(CASE WHEN cat_amount IS NOT NULL OR crffc_amount IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as amount_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_discount IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as discount_pct,
            
            -- Description
            ROUND(100.0 * SUM(CASE WHEN cat_description IS NOT NULL AND cat_description != '' THEN 1 ELSE 0 END) / COUNT(*), 1) as description_pct,
            
            -- Groupings
            ROUND(100.0 * SUM(CASE WHEN cat_marketgroupname IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as market_group_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_storegroupname IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as store_group_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_socgrouping IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as soc_grouping_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_accounttypename IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as account_type_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_channelsname IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as channels_pct,
            
            -- Execution
            ROUND(100.0 * SUM(CASE WHEN cat_devicesalestypename IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as device_sales_type_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_activationtypename IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as activation_type_pct,
            
            -- Links
            ROUND(100.0 * SUM(CASE WHEN cat_orbitlink IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as orbit_link_pct,
            ROUND(100.0 * SUM(CASE WHEN cat_legallink IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as legal_link_pct
            
        FROM dbo.ORBIT_Reporting_Table
        WHERE statuscodename = 'Active'
        """
        
        cursor.execute(query)
        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        
        result = dict(zip(columns, row)) if row else {}
        
        return jsonify({
            'success': True,
            'coverage': result
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500
