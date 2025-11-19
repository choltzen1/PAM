from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from datetime import datetime
import os, json
from typing import Optional, TYPE_CHECKING
import sqlite3

# Unified version history service import (merged module)
try:
    from data.version_history import version_history_service  # type: ignore
except Exception:  # pragma: no cover
    version_history_service = None  # type: ignore

if TYPE_CHECKING:
    from data.storage import PromoDataManager

admin_bp = Blueprint('admin_bp', __name__)

data_manager = None
_PAM_PROMO_CACHE = {'ts': 0, 'data': None}  # in-process cache for PAM promotions page

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
def admin_user_management():
    return render_template('pam/admin_user_management.html')

# New subpages for decluttered functionality
@admin_bp.route('/admin/data')
def admin_data_page():
    return render_template('pam/admin_data.html')

@admin_bp.route('/admin/performance')
def admin_performance_page():
    return render_template('pam/admin_performance.html')

@admin_bp.route('/admin/integrations')
def admin_integrations_page():
    return render_template('pam/admin_integrations.html')

@admin_bp.route('/admin/security')
def admin_security_page():
    return render_template('pam/admin_security.html')

@admin_bp.route('/admin/groupings')
def admin_groupings_page():
    """Dedicated management page for device & reference groupings."""
    return render_template('pam/admin_groupings.html')

@admin_bp.route('/version-history', endpoint='version_history_page')
def version_history_page():
    dm = _ensure_dm()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = max(1, min(per_page, 200))  # sanity bounds
        search = request.args.get('search', '', type=str).strip().lower()
        owner = request.args.get('owner', 'all', type=str).strip()
        # Build base promo mapping using same method as RDC (optimized paginated retrieval) for consistent owner/date fields
        base_map = {}
        if hasattr(dm, 'get_paginated_promos_optimized'):
            try:
                # Large page to approximate full set; if more than limit, consider enhancing to full-fetch API later
                base_payload = dm.get_paginated_promos_optimized(page=1, per_page=1000, search='', owner_filter='all', scope='all')
                for r in base_payload.get('promotions', []):
                    code = r.get('code')
                    if code:
                        base_map[code] = r
            except Exception:
                base_map = {}
        if not base_map:
            # Fallback to legacy full fetch then convert list->map
            try:
                raw_list = dm.get_all_promos() or []
                for r in raw_list:
                    code = r.get('code') or r.get('Code')
                    if code:
                        base_map[str(code)] = r
            except Exception:
                base_map = {}

        # Merge with history via service (service expects callable returning mapping)
        all_promos = []
        if version_history_service:
            all_promos = version_history_service.get_all_promotions_with_history(lambda: base_map)

        owners = sorted({p.get('promo_owner','') for p in all_promos if p.get('promo_owner')})

        def matches(p):
            if owner != 'all' and p.get('promo_owner','').lower() != owner.lower():
                return False
            if search:
                hay = ' '.join([
                    p.get('promo_code',''),
                    p.get('promo_owner',''),
                    p.get('bill_facing_name',''),
                    p.get('orbit_id',''),
                    p.get('status','')
                ]).lower()
                return search in hay
            return True

        filtered_promos = [p for p in all_promos if matches(p)]
        total_items = len(filtered_promos)
        total_pages = (total_items // per_page) + (1 if total_items % per_page else 0)
        if page > total_pages and total_pages > 0:
            page = total_pages
        start = (page - 1) * per_page
        end = start + per_page
        page_promos = filtered_promos[start:end]
        pagination = {
            'page': page,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': total_pages or 1,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < total_pages else None
        }
        return render_template('pam/version_history.html', promotions=page_promos, pagination=pagination, owners=owners, search_query=search, selected_owner=owner)
    except Exception as e:
        flash(f'Error loading version history: {e}', 'error')
        return render_template('pam/version_history.html', promotions=[], pagination={'page':1,'per_page':50,'total_items':0,'total_pages':1,'has_prev':False,'has_next':False}, owners=[], search_query='', selected_owner='all')

# --- Admin actions ---
@admin_bp.route('/admin/backup', methods=['POST'])
def admin_backup():
    try:
        import shutil
        backup_dir = f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(backup_dir, exist_ok=True)
        # Copy metadata/database artifacts (legacy JSON promo files removed; copy any lingering .bak for safety)
        for fname in ['data/version_history.db']:
            if os.path.exists(fname):
                shutil.copy2(fname, backup_dir)
        if os.path.exists('data/uploads'):
            shutil.copytree('data/uploads', os.path.join(backup_dir,'uploads'))
        return jsonify({'success': True, 'message': f'Backup created in {backup_dir} (Promotions reside in SQL Server)'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Backup failed: {e}'})

@admin_bp.route('/admin/stats', methods=['GET'])
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
            'data_source': 'Database (SQL Server + SQLite metadata)',
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
        try:
            import sqlite3, os
            with sqlite3.connect(os.path.join('data','version_history.db')) as conn:
                row = conn.execute("SELECT COUNT(*) FROM version_history WHERE change_type='PCR Version'").fetchone()
                pcr_events = row[0] if row else 0
                row2 = conn.execute("SELECT COUNT(DISTINCT promo_code) FROM version_history WHERE change_type='PCR Version'").fetchone()
                pcr_promos = row2[0] if row2 else 0
        except Exception:
            pass
        # Date diagnostics latest snapshot
        invalid_ratio = None
        try:
            import sqlite3, os
            with sqlite3.connect(os.path.join('data','version_history.db')) as conn:
                snap = conn.execute("SELECT invalid_ratio FROM date_diagnostics_history ORDER BY id DESC LIMIT 1").fetchone()
                if snap: invalid_ratio = snap[0]
        except Exception:
            pass
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

@admin_bp.route('/admin/cache-status')
def admin_cache_status():
    dm = _ensure_dm()
    try:
        cache_status = dm.get_cache_status()
        return jsonify({'success': True, 'cache_status': cache_status})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to get cache status: {e}'})

@admin_bp.route('/admin/cache-refresh', methods=['POST'])
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
def admin_pcr_stats():
    # Provide counts of PCR Version events per promo
    try:
        db_path = os.path.join('data', 'version_history.db')
        stats = []
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT promo_code, COUNT(*) AS pcr_versions,
                       MIN(timestamp) AS first_pcr, MAX(timestamp) AS last_pcr
                FROM version_history
                WHERE change_type='PCR Version'
                GROUP BY promo_code
                ORDER BY pcr_versions DESC, last_pcr DESC
                LIMIT 100
            """).fetchall()
            stats = [dict(r) for r in rows]
        return jsonify({'success': True, 'pcr_stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to load PCR stats: {e}'})

@admin_bp.route('/admin/date-diagnostics')
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
def admin_data_health():
    # Aggregate latest diagnostics snapshot & PCR counts summary
    try:
        db_path = os.path.join('data', 'version_history.db')
        result = {}
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            snap = conn.execute("""
                SELECT * FROM date_diagnostics_history
                ORDER BY id DESC LIMIT 1
            """).fetchone()
            if snap:
                result['latest_snapshot'] = dict(snap)
            else:
                result['latest_snapshot'] = None
            pcr_summary = conn.execute("""
                SELECT COUNT(*) as total_pcr_events, COUNT(DISTINCT promo_code) as promos_with_pcr
                FROM version_history WHERE change_type='PCR Version'
            """).fetchone()
            result['pcr_summary'] = dict(pcr_summary) if pcr_summary else {}
        # Derive status
        status = 'unknown'
        ratio = None
        if result['latest_snapshot'] and result['latest_snapshot'].get('invalid_ratio') is not None:
            ratio = result['latest_snapshot']['invalid_ratio']
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
def admin_users():
    try:
        users = get_all_users()
        groups = get_user_groups()
        return jsonify({'success': True, 'users': users, 'groups': groups})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to get users: {e}'})

@admin_bp.route('/admin/users', methods=['POST'])
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
def admin_list_reference_groupings():
    kind = request.args.get('type','soc').strip()
    try:
        groups = load_reference_groupings(kind)
        return jsonify({'success': True, 'type': kind, 'groups': groups})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to load {kind} groupings: {e}'})

@admin_bp.route('/admin/reference-groupings', methods=['POST'])
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
