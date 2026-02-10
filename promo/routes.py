from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, send_file
import base64, json
from werkzeug.utils import secure_filename
import os
from typing import Optional, TYPE_CHECKING, Dict, Any
from services.mail_service import MailService

if TYPE_CHECKING:
    from data.storage import PromoDataManager

# Create blueprint for promotion routes
promo_bp = Blueprint('promo', __name__)

# Data manager will be set by the main app
data_manager: Optional['PromoDataManager'] = None

# Centralize SQL file path construction so GET/POST use identical logic
def _promo_sql_file_path(promo_code: str) -> str:
    return os.path.join('data','uploads','promotions', promo_code, f"{promo_code}_promo_eligibility_rules.sql")

def init_data_manager(dm):
    """Initialize the data manager from the main app"""
    global data_manager
    data_manager = dm

def _ensure_data_manager():
    """Ensure data_manager is initialized, raise error if not"""
    if data_manager is None:
        raise RuntimeError("Data manager not initialized. Call init_data_manager() first.")
    return data_manager

def _get_current_user_name() -> str | None:
    """Extract display name from Azure App Service Easy Auth headers.
    Preference order: givenname+surname -> name -> preferred_username/email -> header fallback.
    """
    try:
        b64 = request.headers.get('X-MS-CLIENT-PRINCIPAL')
        if b64:
            try:
                decoded = base64.b64decode(b64)
                payload = json.loads(decoded.decode('utf-8'))
                claims = payload.get('claims', [])
                def claim(key: str):
                    for c in claims:
                        if c.get('typ') == key:
                            return c.get('val')
                    return None
                given = claim('givenname') or claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname')
                surname = claim('surname') or claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname')
                full = None
                if (given or surname):
                    gn = (given or '').strip()
                    sn = (surname or '').strip()
                    full = f"{gn} {sn}".strip()
                name = claim('name') or claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name')
                if not full:
                    full = name
                if not full:
                    preferred = claim('preferred_username') or claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress') or claim('emailaddress')
                    full = preferred
                if full:
                    return full
            except Exception:
                pass
        simple = request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME')
        if simple:
            return simple
    except Exception:
        pass
    return None

# --- Primary RDC list route (legacy /promotions removed) ---
@promo_bp.route('/rdc', endpoint='rdc_page')
def rdc_page():
    return _render_rdc_page()

def _render_rdc_page():
    dm = _ensure_data_manager()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '', type=str)
    owner_filter = request.args.get('owner', 'all', type=str)
    scope = request.args.get('scope', 'all', type=str)
    promo_data = {}
    # Try optimized path first
    if hasattr(dm, 'get_paginated_promos_optimized'):
        try:
            promo_data = dm.get_paginated_promos_optimized(
                page=page,
                per_page=per_page,
                search=search,
                owner_filter=owner_filter,
                scope=scope
            )
        except Exception:
            promo_data = {}
    if not promo_data:  # fallback
        if hasattr(dm, 'get_pam_only_paginated_promos'):
            promo_data = dm.get_pam_only_paginated_promos(
                page=page,
                per_page=per_page,
                search=search,
                owner_filter=owner_filter
            )
        else:
            promo_data = dm.get_paginated_promos(
                page=page,
                per_page=per_page,
                search=search,
                owner_filter=owner_filter
            )
    # DEBUG
    import logging
    logger = logging.getLogger(__name__)
    if promo_data.get('promotions'):
        logger.info(f"RDC DEBUG First promo owner: '{promo_data['promotions'][0].get('owner')}'")
    return render_template(
        'pam/rdc.html',
        promotions=promo_data['promotions'],
        pagination=promo_data['pagination'],
        owners=promo_data['owners'],
        search_query=search,
        selected_owner=owner_filter,
        scope=scope,
        active_tab='RDC'
    )

@promo_bp.route('/spe', endpoint='spe_page')
def spe_page():
    dm = _ensure_data_manager()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '', type=str)
    owner_filter = request.args.get('owner', 'all', type=str)
    scope = request.args.get('scope', 'all', type=str)
    
    try:
        # Use same optimized pagination as RDC - pulls directly from PAM_Orbit_Data_Updated table
        if hasattr(dm, 'get_paginated_spe_promos_optimized'):
            spe_payload = dm.get_paginated_spe_promos_optimized(
                page=page,
                per_page=per_page,
                search=search,
                owner_filter=owner_filter,
                scope=scope
            )
        else:
            # Fallback - shouldn't happen but kept for safety
            spe_payload = dm.get_paginated_promos(
                page=page,
                per_page=per_page,
                search=search,
                owner_filter=owner_filter
            )
    except Exception as e:
        flash(f'Error loading SPE data: {e}', 'error')
        return render_template('pam/spe.html', spe_data=[], owners=[], search_query=search, selected_owner=owner_filter, active_tab='SPE')
    
    return render_template(
        'pam/spe.html',
        spe_data=spe_payload['promotions'],
        owners=spe_payload.get('owners', []),
        search_query=search,
        selected_owner=owner_filter,
        scope=scope,
        active_tab='SPE'
    )

@promo_bp.route('/rebates', endpoint='rebates_page')
def rebates_page():
    dm = _ensure_data_manager()
    try:
        search = request.args.get('search', '', type=str)
        owner_filter = request.args.get('owner', 'all', type=str)
        rebates_data_dict = dm.get_all_rebates()
        rebates_list = []
        for key in sorted(rebates_data_dict.keys()):
            item = rebates_data_dict[key]
            item['code'] = key
            rebates_list.append(item)
        if search:
            s = search.lower()
            rebates_list = [r for r in rebates_list if s in r.get('code','').lower() or s in r.get('owner','').lower() or s in r.get('bill_facing_name','').lower()]
        if owner_filter and owner_filter != 'all':
            rebates_list = [r for r in rebates_list if r.get('owner','') == owner_filter]
        owners = dm.get_rebate_owners() if hasattr(dm, 'get_rebate_owners') else []  # type: ignore[attr-defined]
        return render_template('pam/rebates.html', rebates_data=rebates_list, owners=owners, search_query=search, selected_owner=owner_filter, active_tab='Rebates')
    except Exception as e:
        flash(f'Error loading rebates data: {e}', 'error')
        return render_template('pam/rebates.html', rebates_data=[], owners=[], search_query='', selected_owner='all', active_tab='Rebates')

@promo_bp.route('/date-mismatch', endpoint='date_mismatch_page')
def date_mismatch_page():
    dm = _ensure_data_manager()
    try:
        # Use EXACT same optimized method as RDC to get promos with owners
        promo_data = dm.get_paginated_promos_optimized(
            page=1,
            per_page=10000,
            search="",
            owner_filter="all",
            scope="all"
        )
        
        all_promos = promo_data['promotions']
        
        # Get orbit dates from orbit table for comparison
        orbit_ids = [p.get('orbit_id') for p in all_promos if p.get('orbit_id')]
        orbit_dates_map = dm.db_manager.get_orbit_dates_map(orbit_ids) if orbit_ids else {}
        
        # Load PAM JSON for comparison
        import os, json
        pam_json = {}
        try:
            with open(os.path.join(dm.data_dir, 'promotions.json'),'r') as f:
                pam_json = json.load(f)
        except Exception:
            pass
        
        mismatch_promos = []
        for promo in all_promos:
            code = promo.get('code', '')
            orbit_id = promo.get('orbit_id', '')
            pj = pam_json.get(code, {})
            
            # Get orbit dates from orbit table
            orbit_dates = orbit_dates_map.get(orbit_id, {})
            orbit_end = orbit_dates.get('orbit_end_date', '')
            orbit_start = orbit_dates.get('orbit_start_date', '')
            
            # Get PAM dates (from JSON or fallback to promo table)
            pam_end = pj.get('promo_end_date','') or promo.get('promo_end_date', '')
            pam_start = pj.get('promo_start_date','') or promo.get('promo_start_date', '')
            
            mismatch_type = ''
            mismatch_severity = ''
            if orbit_end and pam_end and orbit_end != pam_end:
                mismatch_type = 'End Date'
                mismatch_severity = 'warning'
            elif orbit_end and not pam_end:
                mismatch_type = 'Missing in PAM'
                mismatch_severity = 'error'
            elif pam_end and not orbit_end:
                mismatch_type = 'Missing in ORBIT'
                mismatch_severity = 'error'
            
            mismatch_promos.append({
                'code': code,
                'orbit_id': orbit_id,
                'orbit_start_date': orbit_start,
                'orbit_end_date': orbit_end,
                'promo_start_date': pam_start,
                'promo_end_date': pam_end,
                'mismatch_type': mismatch_type,
                'mismatch_severity': mismatch_severity,
                'bill_facing_name': promo.get('bill_facing_name', ''),
                'owner': promo.get('owner', '')
            })
        
        return render_template('pam/date_mismatch.html',
                       promos=mismatch_promos,
                       owners=promo_data['owners'])
    except Exception as e:
        flash(f'Error loading date mismatch data: {e}', 'error')
        return render_template('pam/date_mismatch.html', promos=[], owners=[])

@promo_bp.route('/update-pam-date/<promo_code>', methods=['POST'], endpoint='update_pam_date')
@promo_bp.route('/update_pam_date/<promo_code>', methods=['POST'])  # backward-compatible alias (old JS used underscore)
def update_pam_date_bp(promo_code):
    dm = _ensure_data_manager()
    try:
        res = dm.sync_promo_end_date_from_orbit(promo_code, user_name=_get_current_user_name() or 'System')
        status = 200 if res.get('success') else 400
        return jsonify(res), status
    except Exception as e:
        return jsonify({'success': False,'message': f'Error updating PAM date: {str(e)}'}), 500

@promo_bp.route('/generate-date-sql', methods=['POST'], endpoint='generate_date_sql')
def generate_date_sql_bp():
    try:
        data = request.get_json()
        promo_codes = data.get('promo_codes', [])
        operator_id = data.get('operator_id', '')
        new_end_date = data.get('new_end_date', '')
        if not operator_id or not operator_id.isdigit() or len(operator_id) != 5:
            return jsonify({'success': False,'message':'Operator ID must be exactly 5 digits'}), 400
        if not promo_codes:
            return jsonify({'success': False,'message':'No promotion codes provided'}), 400
        if not new_end_date:
            return jsonify({'success': False,'message':'New end date is required'}), 400
        sql_statements = []
        from datetime import datetime, timedelta
        for promo_code in promo_codes:
            try:
                end_date_obj = datetime.strptime(new_end_date, '%m/%d/%Y')
                exp_date_obj = end_date_obj + timedelta(days=3*365)
                promo_end_formatted = end_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
                exp_end_formatted = exp_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
                display_end_formatted = (end_date_obj - timedelta(days=1)).strftime('%m/%d/%Y') + ' 00:00:00'
                sql = f"""update promo_eligibility_rules set SYS_UPDATE_DATE = sysdate, APPLICATION_ID = 'CPO', OPERATOR_ID = '{operator_id}', PROMO_END_DATE = to_date('{promo_end_formatted}','MM/DD/YYYY HH24:MI:SS'), EXPIRATION_DATE = to_date('{exp_end_formatted}','MM/DD/YYYY HH24:MI:SS'), DISPLAY_PROMO_END_DATE = to_date('{display_end_formatted}','MM/DD/YYYY HH24:MI:SS') where promo_code = '{promo_code}';"""
                sql_statements.append(sql)
            except ValueError:
                return jsonify({'success': False,'message': f'Invalid date format: {new_end_date}. Use MM/DD/YYYY format.'}), 400
        # Date mismatch event recording removed per version history deletion
        return jsonify({'success': True,'sql_statements': sql_statements})
    except Exception as e:
        return jsonify({'success': False,'message': f'Error generating SQL: {str(e)}'}), 500

# --- SQL generation (date mismatch) endpoints migration ---

def _generate_sql_content(promo_code, operator_id, orbit_end_date):
    try:
        if not operator_id or not operator_id.isdigit() or len(operator_id) != 5:
            return f'Error: Operator ID must be exactly 5 digits. Received: {operator_id}'
        if not orbit_end_date or orbit_end_date == 'N/A':
            return f'Error: No valid ORBIT end date found for promotion {promo_code}'
        from datetime import datetime, timedelta
        try:
            if len(orbit_end_date.split('/')[-1]) == 2:
                month, day, year = orbit_end_date.split('/')
                year = '20' + year if int(year) < 50 else '19' + year
                orbit_end_date = f"{month}/{day}/{year}"
            end_date_obj = datetime.strptime(orbit_end_date, '%m/%d/%Y')
            exp_date_obj = end_date_obj.replace(year=end_date_obj.year + 3)
            display_end_obj = end_date_obj - timedelta(days=1)
            promo_end_formatted = end_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
            exp_end_formatted = exp_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
            display_end_formatted = display_end_obj.strftime('%m/%d/%Y') + ' 00:00:00'
            sql = f"""update promo_eligibility_rules set SYS_UPDATE_DATE = sysdate, APPLICATION_ID = 'CPO', OPERATOR_ID = '{operator_id}', PROMO_END_DATE = to_date('{promo_end_formatted}','MM/DD/YYYY HH24:MI:SS'), EXPIRATION_DATE = to_date('{exp_end_formatted}','MM/DD/YYYY HH24:MI:SS'), DISPLAY_PROMO_END_DATE = to_date('{display_end_formatted}','MM/DD/YYYY HH24:MI:SS') where promo_code = '{promo_code}';"""
            return sql
        except ValueError as e:
            return f'Error: Invalid date format "{orbit_end_date}". Expected MM/DD/YY or MM/DD/YYYY format. Error: {str(e)}'
    except Exception as e:
        return f'Error generating SQL: {str(e)}'

@promo_bp.route('/generate-sql-for-promo/<promo_code>', endpoint='generate_sql_for_promo')
def generate_sql_for_promo_bp(promo_code):
    operator_id = request.args.get('operator_id','')
    orbit_end_date = request.args.get('orbit_end_date','')
    sql = _generate_sql_content(promo_code, operator_id, orbit_end_date)
    if sql.startswith('Error:'):
        flash(sql, 'error')
        return redirect(url_for('promo.date_mismatch_page'))
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
        f.write(sql)
        temp_path = f.name
    from flask import send_file
    filename = f"{promo_code}_end_date_update.sql"
    return send_file(temp_path, as_attachment=True, download_name=filename)

@promo_bp.route('/preview-sql-for-promo/<promo_code>', endpoint='preview_sql_for_promo')
def preview_sql_for_promo_bp(promo_code):
    operator_id = request.args.get('operator_id','')
    orbit_end_date = request.args.get('orbit_end_date','')
    sql = _generate_sql_content(promo_code, operator_id, orbit_end_date)
    if sql.startswith('Error:'):
        return jsonify({'error': sql}), 400
    return jsonify({'sql': sql})

@promo_bp.route('/generate-sql-form/<promo_code>', endpoint='generate_sql_form')
def generate_sql_form_bp(promo_code):
    return render_template('pam/generate_sql_form.html', promo_codes=[promo_code], is_batch=False)

@promo_bp.route('/generate-batch-sql-form', methods=['POST'], endpoint='generate_batch_sql_form')
def generate_batch_sql_form_bp():
    flash('Please select promotions first by checking the boxes, then click Batch Generate SQL', 'info')
    return redirect(url_for('promo.date_mismatch_page'))

@promo_bp.route('/generate-sql-submit', methods=['POST'], endpoint='generate_sql_submit')
def generate_sql_submit_bp():
    try:
        promo_codes = request.form.getlist('promo_codes')
        operator_id = request.form.get('operator_id','')
        new_end_date = request.form.get('new_end_date','')
        if not operator_id or not operator_id.isdigit() or len(operator_id) != 5:
            flash('Operator ID must be exactly 5 digits', 'error')
            return render_template('pam/generate_sql_form.html', promo_codes=promo_codes, is_batch=len(promo_codes) > 1, operator_id=operator_id, new_end_date=new_end_date)
        if not promo_codes:
            flash('No promotion codes provided', 'error')
            return redirect(url_for('promo.date_mismatch_page'))
        if not new_end_date:
            flash('New end date is required', 'error')
            return render_template('pam/generate_sql_form.html', promo_codes=promo_codes, is_batch=len(promo_codes) > 1, operator_id=operator_id, new_end_date=new_end_date)
        from datetime import datetime, timedelta
        sql_statements = []
        for code in promo_codes:
            try:
                end_date_obj = datetime.strptime(new_end_date, '%Y-%m-%d')
                exp_date_obj = end_date_obj + timedelta(days=3*365)
                promo_end_formatted = end_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
                exp_end_formatted = exp_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
                display_end_formatted = (end_date_obj - timedelta(days=1)).strftime('%m/%d/%Y') + ' 00:00:00'
                sql = f"""update promo_eligibility_rules set SYS_UPDATE_DATE = sysdate, APPLICATION_ID = 'CPO', OPERATOR_ID = '{operator_id}', PROMO_END_DATE = to_date('{promo_end_formatted}','MM/DD/YYYY HH24:MI:SS'), EXPIRATION_DATE = to_date('{exp_end_formatted}','MM/DD/YYYY HH24:MI:SS'), DISPLAY_PROMO_END_DATE = to_date('{display_end_formatted}','MM/DD/YYYY HH24:MI:SS') where promo_code = '{code}';"""
                sql_statements.append(sql)
            except ValueError:
                flash(f'Invalid date format: {new_end_date}', 'error')
                return render_template('pam/generate_sql_form.html', promo_codes=promo_codes, is_batch=len(promo_codes) > 1, operator_id=operator_id, new_end_date=new_end_date)
        return render_template('pam/sql_results.html', sql_statements=sql_statements, promo_codes=promo_codes)
    except Exception as e:
        flash(f'Error generating SQL: {str(e)}', 'error')
        return redirect(url_for('promo.date_mismatch_page'))

@promo_bp.route('/generate-batch-sql', methods=['POST'], endpoint='generate_batch_sql')
@promo_bp.route('/generate_batch_sql', methods=['POST'])  # backward-compatible alias
def generate_batch_sql_bp():
    try:
        data = request.get_json()
        promotions = data.get('promotions', [])
        operator_id = data.get('operator_id','')
        if not operator_id or not operator_id.isdigit() or len(operator_id) != 5:
            return jsonify({'success': False,'error':'Operator ID must be exactly 5 digits'}), 400
        if not promotions:
            return jsonify({'success': False,'error':'No promotions provided'}), 400
        sql_statements = []
        successful_promos = []
        failed_promos = []
        for promo in promotions:
            code = promo.get('code','')
            orbit_end_date = promo.get('orbit_end_date','')
            sql = _generate_sql_content(code, operator_id, orbit_end_date)
            if sql.startswith('Error:'):
                failed_promos.append({'code': code, 'error': sql})
            else:
                sql_statements.append(sql)
                successful_promos.append(code)
        if not sql_statements:
            return jsonify({'success': False,'error':'No valid SQL statements could be generated','failed_promos': failed_promos}), 400
        # Record version history events for successful promos (one per promo)
        # Date mismatch event recording removed per version history deletion
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f"End_date_updates_{today}.sql"
        full_sql_content = '\n'.join(sql_statements)
        import tempfile, os
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False)
        temp_file.write(full_sql_content); temp_file.close()
        from flask import session
        session[f'sql_file_{operator_id}_{today}'] = temp_file.name
        return jsonify({'success': True,'filename': filename,'generated_at': datetime.now().strftime('%Y-%m-%d %I:%M %p'),'character_count': len(full_sql_content),'statement_count': len(sql_statements),'download_url': f'/download_batch_sql/{operator_id}/{today}','sql_content': full_sql_content,'successful_promos': successful_promos,'failed_promos': failed_promos})
    except Exception as e:
        return jsonify({'success': False,'error': f'Error generating batch SQL: {str(e)}'}), 500

@promo_bp.route('/download_batch_sql/<operator_id>/<date>', endpoint='download_batch_sql')
def download_batch_sql_bp(operator_id, date):
    try:
        from flask import session, Response
        import os
        temp_file_path = session.get(f'sql_file_{operator_id}_{date}')
        if not temp_file_path or not os.path.exists(temp_file_path):
            flash('SQL file not found or has expired. Please regenerate the SQL.', 'error')
            return redirect(url_for('promo.date_mismatch_page'))
        with open(temp_file_path,'r') as f:
            sql_content = f.read()
        os.unlink(temp_file_path); del session[f'sql_file_{operator_id}_{date}']
        filename = f"End_date_updates_{date}.sql"
        return Response(sql_content, mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename="{filename}"'})
    except Exception as e:
        flash(f'Error downloading SQL file: {str(e)}', 'error')
        return redirect(url_for('promo.date_mismatch_page'))

# --- SPE edit page migration ---
@promo_bp.route('/edit-spe/<promo_code>', methods=['GET','POST'], endpoint='edit_spe_page')
def edit_spe_page(promo_code):
    """Optimized SPE editor.

    Performance improvements:
      - Reuse global data manager (_ensure_data_manager) instead of constructing a new PromoDataManager per request.
      - Use optimized get_spe_promo (single-row lookup) vs full list scan.
      - Avoid duplicate SPE fetch (once for POST processing, once for render).
    """
    tab = request.args.get('tab','Details')
    dm = _ensure_data_manager()

    # Get full SPE data with all fields
    spe_data = dm.get_spe_promo(promo_code)
    
    if spe_data:
        # Overlay owner from paginated method (which works correctly in table view)
        try:
            result = dm.get_paginated_spe_promos_optimized(
                page=1,
                per_page=1,
                search=promo_code,
                owner_filter='all',
                scope='all'
            )
            if result and result.get('promotions'):
                for p in result['promotions']:
                    if p.get('code', '').upper() == promo_code.upper():
                        spe_data['owner'] = p.get('owner', '')
                        break
        except Exception:
            pass
    
    if not spe_data:
        spe_data = {
            'code': promo_code,
            'owner': 'Unknown',
            'description': '',
            'promo_start_date': '',
            'promo_end_date': '',
            'status': 'Draft'
        }
    
    # Guarantee code key populated (SPE records may have missing/blank code in DB or use alternate field names)
    if not spe_data.get('code'):
        spe_data['code'] = promo_code

    if request.method == 'POST':
        tab = request.form.get('active_tab', tab)
        updated = {k:v for k,v in request.form.items() if k != 'active_tab'}
        spe_data.update(updated)
        if not spe_data.get('code'):
            spe_data['code'] = promo_code
        try:
            # Persist using existing JSON compatibility path (SPE still legacy)
            dm.save_spe_promo(promo_code, spe_data, user_name=_get_current_user_name() or 'System')
            flash(f'SPE {promo_code} saved successfully!', 'success')
            return redirect(url_for('promo.edit_spe_page', promo_code=promo_code, tab=tab))
        except Exception as e:
            flash(f'Error saving SPE: {e}', 'error')
            # Continue to render with updated spe_data to avoid data loss in UI

    return render_template(
        'pam/edit_spe.html',
    promo=spe_data,
        spe_data=spe_data,
        spe_key=promo_code,
        active_tab=tab,
        soc_groupings=dm.get_soc_groupings(),
        soc_grouping_details=dm.get_soc_grouping_details(),
        account_types=dm.get_account_types(),
        account_type_details=dm.get_account_type_details(),
        sales_applications=dm.get_sales_applications(),
        sales_application_details=dm.get_sales_application_details()
    )

@promo_bp.route('/test-page', endpoint='test_page')
def test_page():
    return render_template('pam/test.html')

@promo_bp.route('/capacity', endpoint='capacity_page')
def capacity_page():
    dm = _ensure_data_manager()
    try:
        from datetime import datetime, date, timedelta

        def get_sunday_saturday_week(input_date):
            days_since_sunday = input_date.weekday() + 1
            if days_since_sunday == 7:
                days_since_sunday = 0
            week_start = input_date - timedelta(days=days_since_sunday)
            week_end = week_start + timedelta(days=6)
            return week_start, week_end

        def is_promo_active_on_date(promo_start, promo_end, check_date):
            try:
                if not promo_start:
                    return False
                promo_start_date = datetime.strptime(promo_start, '%Y-%m-%d').date()
                if not promo_end or promo_end == '':
                    return promo_start_date <= check_date
                promo_end_date = datetime.strptime(promo_end, '%Y-%m-%d').date()
                return promo_start_date <= check_date <= promo_end_date
            except Exception:
                return False

        current_date = date.today()
        rdc_data = dm.get_all_promos()
        spe_data = dm.get_all_spe_promos()
        rebates_data = dm.get_all_rebates()

        active_rdc = {}
        active_spe = {}
        active_rebates = {}

        for promo_key, promo in rdc_data.items():
            if is_promo_active_on_date(promo.get('promo_start_date'), promo.get('promo_end_date'), current_date):
                entry = promo.copy(); entry['type'] = 'RDC'; active_rdc[promo_key] = entry
        for spe_key, spe in spe_data.items():
            if is_promo_active_on_date(spe.get('promo_start_date'), spe.get('promo_end_date'), current_date):
                entry = spe.copy(); entry['type'] = 'SPE'; active_spe[spe_key] = entry
        for rebate_key, rebate in rebates_data.items():
            if is_promo_active_on_date(rebate.get('promo_start_date'), rebate.get('promo_end_date'), current_date):
                entry = rebate.copy(); entry['type'] = 'REBATE'; active_rebates[rebate_key] = entry

        total_active_rdc = len(active_rdc)
        total_active_spe = len(active_spe)
        total_active_rebates = len(active_rebates)
        total_currently_active = total_active_rdc + total_active_spe + total_active_rebates

        # Determine current week (Sunday-Saturday) and dynamic week options going forward
        current_week_start, current_week_end = get_sunday_saturday_week(current_date)
        week_count = 8  # number of selectable weeks (current + next 7)
        week_options = []
        for i in range(week_count):
            ws = current_week_start + timedelta(weeks=i)
            we = ws + timedelta(days=6)
            week_options.append(f"{ws.strftime('%m/%d/%Y')}-{we.strftime('%m/%d/%Y')}")

        selected_week = request.args.get('week')
        if not selected_week or selected_week not in week_options:
            selected_week = week_options[0]
        start_date_str, end_date_str = selected_week.split('-')
        start_date_wk = datetime.strptime(start_date_str.strip(), '%m/%d/%Y').date()
        end_date_wk = datetime.strptime(end_date_str.strip(), '%m/%d/%Y').date()
        start_date_dt = datetime.combine(start_date_wk, datetime.min.time())
        end_date_dt = datetime.combine(end_date_wk, datetime.min.time())

        def is_promo_launching_in_week(promo_start, week_start, week_end):
            try:
                if not promo_start:
                    return False
                promo_start_date = datetime.strptime(promo_start, '%Y-%m-%d')
                return week_start <= promo_start_date <= week_end
            except Exception:
                return False

        # Helper to access either correctly spelled or legacy typo start/end date keys
        def _start(p):
            return p.get('promo_start_date') or p.get('promo_start_date')
        def _end(p):
            return p.get('promo_end_date') or p.get('promo_end_date')  # second key kept for clarity / future alias

        filtered_rdc = {}
        for promo_key, promo in rdc_data.items():
            if is_promo_launching_in_week(_start(promo), start_date_dt, end_date_dt):
                entry = promo.copy(); entry['type'] = 'RDC'; filtered_rdc[promo_key] = entry
        filtered_spe = {}
        for spe_key, spe in spe_data.items():
            if is_promo_launching_in_week(_start(spe), start_date_dt, end_date_dt):
                entry = spe.copy(); entry['type'] = 'SPE'; filtered_spe[spe_key] = entry
        filtered_rebates = {}
        for rebate_key, rebate in rebates_data.items():
            if is_promo_launching_in_week(_start(rebate), start_date_dt, end_date_dt):
                entry = rebate.copy(); entry['type'] = 'REBATE'; filtered_rebates[rebate_key] = entry

        total_rdc = len(filtered_rdc)
        total_spe = len(filtered_spe)
        total_rebates = len(filtered_rebates)
        total_active = total_rdc + total_spe + total_rebates

        owner_workload = {}
        for promo_key, promo in filtered_rdc.items():
            owner = promo.get('owner', 'Unknown')
            owner_workload.setdefault(owner, {'rdc':0,'spe':0,'rebates':0})['rdc'] += 1
        for spe_key, spe in filtered_spe.items():
            owner = spe.get('owner', 'Unknown')
            owner_workload.setdefault(owner, {'rdc':0,'spe':0,'rebates':0})['spe'] += 1
        for rebate_key, rebate in filtered_rebates.items():
            owner = rebate.get('owner', 'Unknown')
            owner_workload.setdefault(owner, {'rdc':0,'spe':0,'rebates':0})['rebates'] += 1

        for owner in owner_workload:
            wl = owner_workload[owner]
            wl['total'] = wl['rdc'] + wl['spe'] + wl['rebates']
            wl['status'] = 'HIGH' if wl['total'] >= 3 else 'OK'

        # Build schedule starting with current week then next 3 weeks
        next_four_weeks = []
        for i in range(4):
            week_start = current_week_start + timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)
            week_start_dt = datetime.combine(week_start, datetime.min.time())
            week_end_dt = datetime.combine(week_end, datetime.min.time())
            week_promos = []
            for promo in rdc_data.values():
                if is_promo_launching_in_week(_start(promo), week_start_dt, week_end_dt):
                    entry = promo.copy(); entry['type'] = 'RDC'; week_promos.append(entry)
            for spe in spe_data.values():
                if is_promo_launching_in_week(_start(spe), week_start_dt, week_end_dt):
                    entry = spe.copy(); entry['type'] = 'SPE'; week_promos.append(entry)
            for rebate in rebates_data.values():
                if is_promo_launching_in_week(_start(rebate), week_start_dt, week_end_dt):
                    entry = rebate.copy(); entry['type'] = 'REBATE'; week_promos.append(entry)
            week_label = f"{week_start.strftime('%m/%d/%Y')} - {week_end.strftime('%m/%d/%Y')}"
            next_four_weeks.append({'week_label': week_label, 'promotions': week_promos})

        standardized_week = f"{start_date_wk.strftime('%m/%d/%Y')}-{end_date_wk.strftime('%m/%d/%Y')}"
        return render_template('pam/capacity.html',
                               total_active=total_active,
                               total_rdc=total_rdc,
                               total_spe=total_spe,
                               total_rebates=total_rebates,
                               active_today=total_currently_active,
                               active_rdc=total_active_rdc,
                               active_spe=total_active_spe,
                               active_rebates=total_active_rebates,
                               owner_workload=owner_workload,
                               next_four_weeks=next_four_weeks,
                               selected_week=standardized_week,
                               week_options=week_options)
    except Exception as e:
        flash(f'Error loading capacity data: {e}', 'error')
        return render_template('pam/capacity.html',
                               total_active=0,
                               total_rdc=0,
                               total_spe=0,
                               total_rebates=0,
                               active_today=0,
                               active_rdc=0,
                               active_spe=0,
                               active_rebates=0,
                               owner_workload={},
                               next_four_weeks=[],
                               selected_week='',
                               week_options=[])

# --- Download & data clear endpoints migrated from legacy app.py ---

@promo_bp.route('/updates', endpoint='updates_page')
def updates_page():
    dm = _ensure_data_manager()
    search = request.args.get('search', '', type=str)
    all_promos = dm.get_all_promos()
    if search:
        filtered_promos = {}
        search_lower = search.lower()
        for code, promo in all_promos.items():
            if (search_lower in code.lower() or
                search_lower in promo.get('description', '').lower() or
                search_lower in promo.get('bill_facing_name', '').lower() or
                search_lower in promo.get('owner', '').lower()):
                filtered_promos[code] = promo
        all_promos = filtered_promos
    default_promo = None
    if all_promos:
        first_code = next(iter(all_promos))
        default_promo = all_promos[first_code]
        default_promo['code'] = first_code
    return render_template('pam/updates.html',
                           search_query=search,
                           default_promo=default_promo,
                           total_results=len(all_promos))


@promo_bp.route('/approvers', endpoint='approvers_page')
def approvers_page():
    dm = _ensure_data_manager()
    import logging
    log = logging.getLogger(__name__)
    try:
        # Approvers page should mirror RDC data retrieval exactly (PAM data only)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 500, type=int)  # large page to show broad set
        search = request.args.get('search', '', type=str)
        owner_filter = request.args.get('owner', 'all', type=str)
        target_promo_code = request.args.get('promo_code', '').strip().upper()
        scope = request.args.get('scope', 'all', type=str)

        payload = {}
        if hasattr(dm, 'get_paginated_promos_optimized'):
            try:
                payload = dm.get_paginated_promos_optimized(
                    page=page,
                    per_page=per_page,
                    search=search,
                    owner_filter=owner_filter,
                    scope=scope
                )
            except Exception as e:
                log.warning(f"Approvers fallback from optimized path: {e}")
                payload = {}
        if not payload:
            if hasattr(dm, 'get_pam_only_paginated_promos'):
                payload = dm.get_pam_only_paginated_promos(
                    page=page,
                    per_page=per_page,
                    search=search,
                    owner_filter=owner_filter
                )
            else:
                payload = dm.get_paginated_promos(
                    page=page,
                    per_page=per_page,
                    search=search,
                    owner_filter=owner_filter
                )

        promos = payload.get('promotions', [])
        owners_list = [p.get('owner','').strip() for p in promos]
        owners_list = [o for o in owners_list if o]  # remove blanks
        unique_owners = sorted({o for o in owners_list if o.lower() != 'unknown'})

        promo_codes = [p.get('code','') for p in promos]
        # Prioritize searched promo_code if present
        if target_promo_code and target_promo_code in promo_codes:
            idx = promo_codes.index(target_promo_code)
            if idx != 0:
                promos = [promos[idx]] + promos[:idx] + promos[idx+1:]
                promo_codes = [p.get('code','') for p in promos]
                owners_list = [p.get('owner','') for p in promos]

        # Placeholder revenue approvers until integrated
        revenue_approvers = [
            {'name': 'John Smith', 'email': 'john.smith@company.com'},
            {'name': 'Sarah Davis', 'email': 'sarah.davis@company.com'},
            {'name': 'Mike Johnson', 'email': 'mike.johnson@company.com'},
            {'name': 'Lisa Chen', 'email': 'lisa.chen@company.com'}
        ]

        return render_template(
            'pam/approvers.html',
            promo_codes=promo_codes,
            owners=owners_list,
            unique_owners=unique_owners,
            revenue_approvers=revenue_approvers,
            target_promo_code=target_promo_code,
            pagination=payload.get('pagination', {}),
            search_query=search,
            selected_owner=owner_filter
        )
    except Exception as e:
        flash(f'Error loading approvers data: {e}', 'error')
        return render_template('pam/approvers.html', promo_codes=[], owners=[], unique_owners=[], revenue_approvers=[], target_promo_code='')

@promo_bp.route('/send-approval-email', methods=['POST'], endpoint='send_approval_email')
def send_approval_email():
    """Send approval email via Database Mail with promo details"""
    from services.mail_service import MailService
    
    try:
        dm = _ensure_data_manager()
        data = request.get_json()
        promo_code = data.get('promo_code', '').upper()
        send_to_device_finance = data.get('device_finance', False)
        send_to_revenue_accounting = data.get('revenue_accounting', False)
        send_trade = data.get('trade', False)
        
        if not promo_code:
            return jsonify({'success': False, 'message': 'Promo code is required'}), 400
        
        if not send_to_device_finance and not send_to_revenue_accounting and not send_trade:
            return jsonify({'success': False, 'message': 'At least one recipient is required'}), 400
        
        # Fetch promo details from database
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            # Try SPE or rebates
            from data.storage import PromoDataManager as JSONManager
            json_manager = JSONManager()
            spe_data = json_manager.get_all_spe_promos()
            promo_data = spe_data.get(promo_code)
            if not promo_data:
                rebates_data = json_manager.get_all_rebates()
                promo_data = rebates_data.get(promo_code)
        
        if not promo_data:
            return jsonify({'success': False, 'message': f'Promo code {promo_code} not found'}), 404
        
        # Extract promo details
        bill_facing_name = promo_data.get('bill_facing_name', 'Unknown')
        version_number = promo_data.get('version_number', promo_data.get('version', '1'))
        
        # Calculate deadline: promo start date - 1 day at 11:59 EST
        from datetime import datetime, timedelta
        promo_start_date_str = promo_data.get('promo_start_date', promo_data.get('start_date'))
        deadline = 'the specified deadline'
        
        if promo_start_date_str:
            try:
                # Parse the date - handle various date formats
                promo_start = None
                if isinstance(promo_start_date_str, str):
                    # Try common date formats
                    for date_format in ['%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y']:
                        try:
                            promo_start = datetime.strptime(promo_start_date_str, date_format)
                            break
                        except ValueError:
                            continue
                else:
                    promo_start = promo_start_date_str
                
                # Calculate deadline: start date - 1 day at 11:59 EST
                if promo_start:
                    deadline_date = promo_start - timedelta(days=1)
                    deadline = deadline_date.strftime('%m/%d/%Y') + ' 11:59 EST'
            except Exception:
                deadline = 'the specified deadline'
        
        # Build PAM reviewers page URL for the promo
        pam_url = f"{request.host_url.rstrip('/')}{url_for('promo.reviewers_with_code', promo_code=promo_code)}"
        
        # Get desired_execution from promo data (RDC, SPE, or Rebate)
        promo_desired_execution = promo_data.get('Desired_Execution', 'Unknown')
        
        # Determine which departments are selected for email body context
        departments = []
        if send_to_device_finance:
            departments.append('Device Finance')
        if send_to_revenue_accounting:
            departments.append('Revenue Accounting')
        departments_str = ' & '.join(departments)
        
        # Format subject line with promo's desired_execution type
        subject = f'{promo_desired_execution} Approval request - {promo_code} - {bill_facing_name} - Version #{version_number}'
        
        # Format body email with PAM link and calculated deadline
        body = f'''Hello All,<br><br>Please review and provide approval for {promo_code} - {bill_facing_name} - Version #{version_number}.<br><br><a href="{pam_url}">PAM - Promotions Automation Manager</a><br><br>Please provide approval prior to {deadline}.<br><br>Please let me know if there are any questions and concerns.<br><br>Thank you!'''
        
        # Send email to test recipient
        mail_service = MailService()
        result = mail_service.send_approval_email(
            recipients='cade.holtzen1@t-mobile.com',
            subject=subject,
            body=body,
            body_format='HTML'
        )
        
        if result['success']:
            # Track this approval request for later reply
            from data.approval_email_tracking import store_approval_request
            store_approval_request(promo_code, version_number, subject, 'cade.holtzen1@t-mobile.com')
            
            # Send trade devices email if trade is selected
            if send_trade:
                trade_devices = promo_data.get('eligible_trade_in_devices', 'No trade-in devices listed')
                trade_subject = f'Trade Devices - {promo_code} - {bill_facing_name} - Version #{version_number}'
                
                # Format trade devices for display
                if isinstance(trade_devices, str):
                    devices_list = trade_devices
                else:
                    devices_list = str(trade_devices)
                
                trade_body = f'''Here are the eligible trade-in devices for {promo_code} - {bill_facing_name} - Version #{version_number}:<br><br><strong>Eligible Trade-In Devices:</strong><br>{devices_list.replace(chr(10), '<br>')}'''
                
                trade_result = mail_service.send_approval_email(
                    recipients='cade.holtzen1@t-mobile.com',
                    subject=trade_subject,
                    body=trade_body,
                    body_format='HTML'
                )
                
                if trade_result['success']:
                    result['message'] += ' + Trade devices email sent'
            
            return jsonify({'success': True, 'message': result['message']}), 200
        else:
            return jsonify({'success': False, 'message': result['message']}), 500
    
    except Exception as e:
        error_msg = f'Error sending approval email: {str(e)}'
        import logging
        logging.error(error_msg, exc_info=True)
        return jsonify({'success': False, 'message': error_msg}), 500

@promo_bp.route('/approve-promo', methods=['POST'])
def approve_promo():
    """Handle promo approval and send reply email"""
    try:
        data = request.get_json()
        promo_code = data.get('promo_code', '').upper()
        version_number = data.get('version_number', '1')
        
        if not promo_code:
            return jsonify({'success': False, 'message': 'Promo code is required'}), 400
        
        # Fetch promo details from database
        dm = _ensure_data_manager()
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            # Try SPE or rebates
            from data.storage import PromoDataManager as JSONManager
            json_manager = JSONManager()
            spe_data = json_manager.get_all_spe_promos()
            promo_data = spe_data.get(promo_code)
            if not promo_data:
                rebates_data = json_manager.get_all_rebates()
                promo_data = rebates_data.get(promo_code)
        
        if not promo_data:
            return jsonify({'success': False, 'message': f'Promo code {promo_code} not found'}), 404
        
        # Extract promo details
        bill_facing_name = promo_data.get('bill_facing_name', 'Unknown')
        promo_desired_execution = promo_data.get('Desired_Execution', 'Unknown')
        
        # Get the original approval request's mail ID for threading
        from data.approval_email_tracking import get_approval_tracking, store_approval_reply
        tracking = get_approval_tracking(promo_code, version_number)
        request_mail_id = tracking.get('request_mail_id') if tracking else None
        
        # Build approval email subject and body
        approval_subject = f'RE: {promo_desired_execution} Approval request - {promo_code} - {bill_facing_name} - Version #{version_number}'
        approval_body = f'''Hello All,<br><br>I am writing to confirm that I have approved {promo_code} - {bill_facing_name} - Version #{version_number}.<br><br>Please proceed with the next steps.<br><br>Thank you!'''
        
        # Send approval reply email
        mail_service = MailService()
        result = mail_service.send_approval_email(
            recipients='cade.holtzen1@t-mobile.com',
            subject=approval_subject,
            body=approval_body,
            body_format='HTML',
            is_reply=True,
            in_reply_to_mail_id=request_mail_id
        )
        
        if result['success']:
            # Track this approval reply
            store_approval_reply(promo_code, version_number)
            
            return jsonify({'success': True, 'message': f'Approval sent for {promo_code} Version #{version_number}'}), 200
        else:
            return jsonify({'success': False, 'message': result['message']}), 500
    
    except Exception as e:
        error_msg = f'Error approving promo: {str(e)}'
        import logging
        logging.error(error_msg, exc_info=True)
        return jsonify({'success': False, 'message': error_msg}), 500

@promo_bp.route('/reject-promo', methods=['POST'])
def reject_promo():
    """Handle promo rejection and send rejection reply email"""
    from services.mail_service import MailService
    try:
        data = request.get_json()
        promo_code = data.get('promo_code', '').upper()
        version_number = data.get('version_number', '1')
        reason = data.get('reason', '').strip()

        if not promo_code:
            return jsonify({'success': False, 'message': 'Promo code is required'}), 400

        dm = _ensure_data_manager()
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            from data.storage import PromoDataManager as JSONManager
            json_manager = JSONManager()
            spe_data = json_manager.get_all_spe_promos()
            promo_data = spe_data.get(promo_code)
            if not promo_data:
                rebates_data = json_manager.get_all_rebates()
                promo_data = rebates_data.get(promo_code)

        if not promo_data:
            return jsonify({'success': False, 'message': f'Promo code {promo_code} not found'}), 404

        bill_facing_name = promo_data.get('bill_facing_name', 'Unknown')
        promo_desired_execution = promo_data.get('Desired_Execution', 'Unknown')

        from data.approval_email_tracking import get_approval_tracking
        tracking = get_approval_tracking(promo_code, version_number)
        request_mail_id = tracking.get('request_mail_id') if tracking else None

        rejection_subject = f'RE: {promo_desired_execution} Approval request - {promo_code} - {bill_facing_name} - Version #{version_number}'
        reason_line = f'<br><br><strong>Reason:</strong> {reason}' if reason else ''
        rejection_body = f'''Hello All,<br><br>I am writing to inform you that {promo_code} - {bill_facing_name} - Version #{version_number} has been <strong style="color:#dc3545;">rejected</strong>.{reason_line}<br><br>Please address the concerns and resubmit for approval.<br><br>Thank you!'''

        mail_service = MailService()
        result = mail_service.send_approval_email(
            recipients='cade.holtzen1@t-mobile.com',
            subject=rejection_subject,
            body=rejection_body,
            body_format='HTML',
            is_reply=True,
            in_reply_to_mail_id=request_mail_id
        )

        if result['success']:
            return jsonify({'success': True, 'message': f'Rejection sent for {promo_code} Version #{version_number}'}), 200
        else:
            return jsonify({'success': False, 'message': result['message']}), 500

    except Exception as e:
        error_msg = f'Error rejecting promo: {str(e)}'
        import logging
        logging.error(error_msg, exc_info=True)
        return jsonify({'success': False, 'message': error_msg}), 500

@promo_bp.route('/reviewers', defaults={'promo_code': None}, endpoint='reviewers_page')
@promo_bp.route('/reviewers/<promo_code>', endpoint='reviewers_with_code')
def reviewers_page(promo_code):
    dm = _ensure_data_manager()
    promo_data = None
    error_message = None
    if promo_code:
        promo_code_upper = promo_code.upper()
        promo_data = dm.get_promo(promo_code_upper)
        if not promo_data:
            spe_promos = dm.get_all_spe_promos()
            promo_data = spe_promos.get(promo_code_upper)
        if not promo_data:
            error_message = f"Promotion code '{promo_code}' not found"
    return render_template('pam/reviewers.html', promo_code=promo_code, promo_data=promo_data, error_message=error_message)

@promo_bp.route('/links', endpoint='links_main_page')
def links_main_page():
    return render_template('pam/links.html')

@promo_bp.route('/links/<promo_code>', methods=['GET','POST'], endpoint='links_page')
def links_page(promo_code):
    dm = _ensure_data_manager()
    try:
        promo_code_upper = promo_code.upper()
        promo_data = dm.get_promo(promo_code_upper)
        if not promo_data:
            spe_promos = dm.get_all_spe_promos()
            promo_data = spe_promos.get(promo_code_upper)
        if not promo_data:
            error_message = f"Promotion code '{promo_code_upper}' not found"
            return render_template('pam/links.html', promo_code=promo_code_upper, promo_data=None, error_message=error_message)
        if request.method == 'POST':
            promo_data['sku_link'] = request.form.get('skuLink', '')
            promo_data['tradein_link'] = request.form.get('tradeLink', '')
            promo_data['orbit_link'] = request.form.get('orbitLink', '')
            promo_data['legal_link'] = request.form.get('legalLink', '')
            promo_data['c2_article_link'] = request.form.get('c2ArticleLink', '')
            try:
                regular_promos = dm.get_all_promos()
                if promo_code_upper in regular_promos:
                    dm.save_promo(promo_code_upper, promo_data, user_name=_get_current_user_name() or 'System')
                else:
                    from data.storage import PromoDataManager as JSONManager
                    json_manager = JSONManager()
                    json_manager.save_spe_promo(promo_code_upper, promo_data, user_name=_get_current_user_name() or 'System')
                return redirect(url_for('promo.links_page', promo_code=promo_code_upper))
            except Exception as e:
                flash(f'Error saving links: {e}', 'error')
        return render_template('pam/links.html', promo_code=promo_code_upper, promo_data=promo_data)
    except Exception as e:
        flash(f'Error loading links for promotion: {e}', 'error')
        return redirect(url_for('promo.rdc_page'))

@promo_bp.route('/edit_rdc/<promo_code>', methods=['GET', 'POST'], endpoint='edit_rdc')
def edit_rdc(promo_code):
    return _edit_rdc(promo_code)

def _edit_rdc(promo_code):
    """Primary editor for RDC (formerly promotions)"""
    dm = _ensure_data_manager()

    if request.method == 'POST':
        """POST handling order (updated):
        1. Load current DB promo state (not relying on stale in-memory form submission)
        2. Process file uploads first (so newly uploaded SKU/Trade files influence SQL generation)
        3. Apply form field edits & persist (save_promo) so DB reflects latest values
        4. If generate_sql requested, RE-FETCH from DB and generate SQL using ONLY what the PAM DB exposes.
           Any field absent in DB simply remains missing/blank and generator maps it to NULL.
        5. Persist generated SQL to disk & attach metadata (not stored verbatim in DB columns)
        """
        from datetime import datetime
        import time
        active_tab = request.form.get('active_tab', 'Details')
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            promo_data = {
                'code': promo_code,
                'owner': 'Unknown',
                'description': '',
                'start_date': '',
                'end_date': '',
                'status': 'Draft'
            }

        # 1. & 2. Handle file uploads first
        for file_key in ['sku_excel', 'tradein_excel']:
            if file_key in request.files:
                file = request.files[file_key]
                if file and file.filename:
                    try:
                        file_metadata = dm.save_excel_file(promo_code, file, file_key)
                        if file_metadata:
                            # Update the promo data with file metadata
                            if 'uploaded_files' not in promo_data:
                                promo_data['uploaded_files'] = {}
                            promo_data['uploaded_files'][file_key] = file_metadata
                            
                            # Process trade-in Excel file to populate trade tier data
                            if file_key == 'tradein_excel':
                                from promo.parsers import parse_tradein_excel
                                try:
                                    sql_statements = parse_tradein_excel(file_metadata['file_path'], promo_data)
                                    
                                    # Parse the SQL statements to extract tier information and populate form fields
                                    tier_data = {}
                                    for sql in sql_statements:
                                        # Extract tier and model information from SQL
                                        if 'TIER' in sql:
                                            # Find tier number in the SQL statement
                                            import re
                                            tier_match = re.search(r'TIER (\d+)', sql)
                                            make_match = re.search(r",'([^']+)','([^']+)',", sql)
                                            grp_id_match = re.search(r"Values \('([^']+)'", sql)
                                            
                                            if tier_match and make_match and grp_id_match:
                                                tier_num = tier_match.group(1)
                                                make = make_match.group(1)
                                                model = make_match.group(2)
                                                grp_id = grp_id_match.group(1)
                                                
                                                if tier_num not in tier_data:
                                                    tier_data[tier_num] = {
                                                        'make_model': grp_id,
                                                        'devices': []
                                                    }
                                                tier_data[tier_num]['devices'].append(f"{make} - {model}")
                                    
                                    # Update promo data with tier information
                                    for tier_num, data in tier_data.items():
                                        promo_data[f'trade_tier_{tier_num}_make_model'] = data['make_model']
                                        # You can also set default amounts, conditions, etc. based on your business logic
                                        if not promo_data.get(f'trade_tier_{tier_num}_cond_id'):
                                            promo_data[f'trade_tier_{tier_num}_cond_id'] = 'ST1'  # Default condition
                                    
                                    # Store the generated SQL statements for later use
                                    promo_data['tradein_sql_statements'] = sql_statements  
                                    
                                    flash(f"Trade-in Excel processed successfully. {len(sql_statements)} SQL statements generated.", "success")
                                    
                                except Exception as e:
                                    flash(f"Error processing trade-in Excel: {str(e)}", "warning")
                            
                            dm.save_promo(promo_code, promo_data, user_name=_get_current_user_name() or 'System')
                            
                            flash(f"{file_key.replace('_', ' ').title()} uploaded successfully", "success")
                        else:
                            flash(f"Failed to save {file_key.replace('_', ' ')}", "error")
                    except Exception as e:
                        flash(f"Error uploading {file_key}: {str(e)}", "error")
        
        # 3. Update promo fields based on active tab (save BEFORE generation so DB has latest values)
        updated_fields = []
        for field_name, field_value in request.form.items():
            if field_name not in ['active_tab', 'generate_sql']:
                # Check if it's a new field or existing field
                if field_name in promo_data or field_value.strip():  # Update if field exists or has value
                    old_value = promo_data.get(field_name)
                    if old_value != field_value:
                        promo_data[field_name] = field_value
                        updated_fields.append(field_name)
        # Normalize bill facing name space variant after gathering updates
        if 'bill_facing_name' in promo_data:
            # Ensure both variants point to same value for downstream DB update logic
            promo_data['bill facing name'] = promo_data.get('bill_facing_name')
        
        # Save changes
        if updated_fields:
            promo_data['last_changes'] = f"Updated {', '.join(updated_fields)} on {active_tab} tab"
            dm.save_promo(promo_code, promo_data, user_name=_get_current_user_name() or 'System')
            flash(f"Saved {active_tab} successfully", "success")

        # 4. Generate SQL only after saving & reloading DB state (source-of-truth requirement)
        if request.form.get('generate_sql'):
            from promo.builders import generate_promo_eligibility_sql
            try:
                # Re-fetch to ensure we only use DB-backed fields (missing ones become NULL in generator)
                db_snapshot = dm.get_promo(promo_code) or {}
                # PRE-CLEAN: convert None -> '' so generator .strip() calls are safe
                for _k,_v in list(db_snapshot.items()):
                    if _v is None:
                        db_snapshot[_k] = ''
                # Guarantee code present
                if not db_snapshot.get('code'):
                    db_snapshot['code'] = promo_code
                # Inject minimal required placeholders so generator produces a visible INSERT even if DB sparse
                if not db_snapshot.get('code'):
                    db_snapshot['code'] = promo_code
                # Provide fallback promo_start_date/end_date if absent so date functions don't yield all NULL
                from datetime import datetime, timedelta
                today = datetime.utcnow().date()
                if not db_snapshot.get('promo_start_date'):
                    db_snapshot['promo_start_date'] = today.strftime('%Y-%m-%d')
                if not db_snapshot.get('promo_end_date'):
                    db_snapshot['promo_end_date'] = (today + timedelta(days=14)).strftime('%Y-%m-%d')
                # Basic bill facing name placeholder
                if not db_snapshot.get('bill_facing_name'):
                    db_snapshot['bill_facing_name'] = f"Auto {promo_code}"
                # Log snapshot keys for debugging
                print(f"[SQL GEN][DEBUG] Generating for {promo_code} with keys: {sorted(list(db_snapshot.keys()))[:30]} ...")
                print(f"[SQL GEN][DEBUG] Field snapshot core values: code={db_snapshot.get('code')} orbit_id={db_snapshot.get('orbit_id')} sku_group_id={db_snapshot.get('sku_group_id')} start={db_snapshot.get('promo_start_date')} end={db_snapshot.get('promo_end_date')} operator_id={db_snapshot.get('operator_id')}")
                start_time = time.time()
                sql_content = generate_promo_eligibility_sql(db_snapshot, current_user=_get_current_user_name() or 'System')
                end_time = time.time()
                generation_time = end_time - start_time
                if not sql_content or not sql_content.strip():
                    sql_content = '-- No SQL generated (all required inputs missing in PAM DB after fallback)\nSELECT 1 AS no_data_placeholder;\n'
                # Removed DIAG header injection per user request; leaving raw generator output intact.
                # Absolute fallback: if somehow still empty, produce minimal INSERT with just promo_code
                if not sql_content.strip():
                    sql_content = f"-- FALLBACK MINIMAL SQL\nINSERT INTO PROMO_ELIGIBILITY_RULES (PROMO_CODE) VALUES ('{promo_code}');\n"
                print(f"[SQL GEN][DEBUG] Generated length for {promo_code}: {len(sql_content)} chars")
                # Attach to working promo_data for redirect display
                promo_data['generated_sql'] = sql_content
                promo_data['sql_generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                promo_data['sql_generation_time'] = f"{generation_time:.4f}"
                promo_data['sql_length'] = len(sql_content)
                # Store in SQLite blob table (separate persistence)
                try:
                    from data import sql_store
                    sql_hash = sql_store.save_generated_sql(promo_code, sql_content, generation_time, source='rdc_generator')
                    promo_data['sql_hash'] = sql_hash
                except Exception as blob_err:
                    print(f"[SQL GEN][BLOB][ERROR] Failed to store SQL blob for {promo_code}: {blob_err}")
                # Persist physical file (durable across reloads)
                saved_path = None
                try:
                    saved_path = dm.save_sql_file(promo_code, sql_content, f"{promo_code}_promo_eligibility_rules.sql")
                    print(f"[SQL GEN][WRITE] Saved SQL file for {promo_code} at {saved_path} ({len(sql_content)} bytes)")
                except Exception as save_err:
                    print(f"[SQL GEN][WRITE][ERROR] File save failed for {promo_code}: {save_err}")
                    flash(f"SQL file save failed: {save_err}", 'warning')
                # Version history removed: no PCR version recorded
                # Performance + summary flash
                flash(f"SQL generated in {generation_time:.2f}s | {len(sql_content):,} chars", 'success')
                # Force tab to SQL Generation
                active_tab = 'SQL Generation'
            except Exception as gen_err:
                print(f"[SQL GEN][ERROR] Generation failure for {promo_code}: {gen_err}")
                from datetime import datetime
                err_sql = ("-- GENERATION ERROR: " + str(gen_err).replace('\n',' ') + "\n"
                           "-- A minimal placeholder INSERT is provided so preview is not blank.\n"
                           f"INSERT INTO PROMO_ELIGIBILITY_RULES (PROMO_CODE) VALUES ('{promo_code}');\n")
                promo_data['generated_sql'] = err_sql
                promo_data['sql_generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                promo_data['sql_generation_time'] = 'ERR'
                promo_data['sql_length'] = len(err_sql)
                try:
                    from data import sql_store
                    sql_store.save_generated_sql(promo_code, err_sql, 0.0, source='error_fallback')
                except Exception:
                    pass
                try:
                    dm.save_sql_file(promo_code, err_sql, f"{promo_code}_promo_eligibility_rules.sql")
                except Exception:
                    pass
                flash("SQL generation error captured. Placeholder shown.", 'error')
                active_tab = 'SQL Generation'
        
        # Redirect (PRG). If we just generated SQL add gen=1 flag for debug visibility
        gen_flag = 1 if request.form.get('generate_sql') else None
        # If generated SQL this request, include inline snippet (first 500 chars) via query for guaranteed visibility
        inline_sql_snippet = None
        if gen_flag and promo_data.get('generated_sql'):
            inline_sql_snippet = promo_data['generated_sql'][:500]
        return redirect(url_for('promo.edit_rdc', promo_code=promo_code, tab=active_tab, gen=gen_flag, sql_snip=inline_sql_snippet))
    
    # GET request
    tab = request.args.get('tab', 'Details')
    gen_flag = request.args.get('gen')
    inline_sql_snip = request.args.get('sql_snip')
    
    # Get full promo data with all fields
    promo_data = dm.get_promo(promo_code)
    
    if promo_data:
        # Overlay owner from paginated method (which works correctly in table view)
        try:
            result = dm.get_paginated_promos_optimized(
                page=1,
                per_page=1,
                search=promo_code,
                owner_filter='all',
                scope='all'
            )
            if result and result.get('promotions'):
                for p in result['promotions']:
                    if p.get('code', '').upper() == promo_code.upper():
                        promo_data['owner'] = p.get('owner', '')
                        break
        except Exception:
            pass
    
    if not promo_data:
        # Create new promo data if it doesn't exist
        promo_data = {
            'code': promo_code,
            'owner': 'Unknown',
            'description': '',
            'start_date': '',
            'end_date': '',
            'status': 'Draft'
        }
    
    # If SQL missing but inline snippet passed, attach minimal placeholder for display
    if inline_sql_snip and not promo_data.get('generated_sql'):
        promo_data['generated_sql'] = inline_sql_snip + ('\n-- (Truncated preview via redirect parameter)')
        promo_data['sql_length'] = len(promo_data['generated_sql'])
    # Force code population for template / filename correctness
    if not promo_data.get('code'):
        promo_data['code'] = promo_code
    # 5. GET fallback: if SQL file exists on disk but field not populated (DB returns empty) load it
    # ALWAYS attempt disk load so we can compare what is stored vs memory (adds transparency)
    disk_sql_path = _promo_sql_file_path(promo_code)
    try:
        disk_exists = os.path.exists(disk_sql_path)
        promo_data['sql_disk_exists'] = disk_exists
        if disk_exists:
            from datetime import datetime
            with open(disk_sql_path, 'r', encoding='utf-8', errors='replace') as fh:
                disk_sql = fh.read()
            promo_data['sql_disk_length'] = len(disk_sql)
            # If in-memory missing or differs in length, populate & flag source
            if not promo_data.get('generated_sql') or len(promo_data.get('generated_sql','')) != len(disk_sql):
                if disk_sql.strip():
                    promo_data['generated_sql'] = disk_sql
                    promo_data['sql_length'] = len(disk_sql)
                    promo_data['sql_generated_at'] = promo_data.get('sql_generated_at') or datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    promo_data['sql_generation_time'] = promo_data.get('sql_generation_time') or 'N/A'
                    promo_data['sql_debug_loaded_from'] = 'GET_disk_refresh'
        else:
            promo_data['sql_disk_length'] = 0
    except Exception as load_err:
        print(f"[SQL GEN][GET] Disk load error for {promo_code}: {load_err}")
    # If still no SQL in memory, attempt to fetch latest from sql_store
    if not promo_data.get('generated_sql'):
        try:
            from data import sql_store
            blob_sql, blob_meta = sql_store.get_latest_generated_sql(promo_code)
            if blob_sql:
                promo_data['generated_sql'] = blob_sql
                promo_data['sql_length'] = len(blob_sql)
                if blob_meta:
                    promo_data['sql_generated_at'] = blob_meta.get('stored_at')
                    promo_data['sql_generation_time'] = blob_meta.get('generation_time')
                    promo_data['sql_hash'] = blob_meta.get('sql_hash')
                    promo_data['sql_debug_loaded_from'] = 'GET_sql_store'
        except Exception as blob_get_err:
            print(f"[SQL GEN][GET][BLOB] Failed to load SQL from store for {promo_code}: {blob_get_err}")
    auto_open_sql_preview = True if (gen_flag and promo_data.get('generated_sql') and tab == 'SQL Generation') else False
    # Compute persistent flag: has SQL ever been generated (file or memory)
    try:
        sql_file_exists = os.path.exists(os.path.join('data','uploads','promotions', promo_code, f"{promo_code}_promo_eligibility_rules.sql"))
    except Exception:
        sql_file_exists = False
    has_generated_sql = bool(promo_data.get('generated_sql')) or sql_file_exists
    # Build field diagnostics for template (only for SQL Generation tab)
    sql_source_fields = {}
    if tab == 'SQL Generation':
        debug_keys = [
            'code','orbit_id','sku_group_id','promo_start_date','promo_end_date','operator_id','bill_facing_name',
            'discount','amount','account_type','sales_application','soc_grouping','trade_in_group_id',
            'tiered_group_id','segment_group_id','limit_per_ban','nseip_drop','maintain_soc','activation_type',
            'device_sales_type','port_in_group_id','min_gsm_count','max_gsm_count','flow_indicator','clawback_indicator'
        ]
        for k in debug_keys:
            sql_source_fields[k] = promo_data.get(k)
    return render_template('pam/edit_rdc.html', 
                         promo=promo_data, 
                         active_tab=tab,
                         gen_flag=gen_flag,
                         auto_open_sql_preview=auto_open_sql_preview,
                         has_generated_sql=has_generated_sql,
                         sql_source_fields=sql_source_fields,
                         sql_disk_path=disk_sql_path,
                         soc_groupings=dm.get_soc_groupings(),
                         soc_grouping_details=dm.get_soc_grouping_details(),
                         account_types=dm.get_account_types(),
                         account_type_details=dm.get_account_type_details(),
                         sales_applications=dm.get_sales_applications(),
                         sales_application_details=dm.get_sales_application_details(),
                         jira_dcd_ticket=os.getenv('JIRA_DCD_CURRENT_TICKET', 'DCOMM-13037'))

@promo_bp.route('/autosave/<promo_code>', methods=['POST'])
def autosave_promo(promo_code):
    """Autosave endpoint to persist partial field changes without full form submission."""
    dm = _ensure_data_manager()
    try:
        payload = request.get_json() or {}
        # Accept nested {'fields': {...}} or flat JSON
        raw_changes_candidate = payload.get('fields') if isinstance(payload.get('fields'), dict) else payload
        raw_changes: Dict[str, Any] = dict(raw_changes_candidate or {})
        for ro in ['code','promo_code','orbit_id']:
            if ro in raw_changes:
                del raw_changes[ro]
        result = dm.save_promo(promo_code, raw_changes, user_name=(payload.get('user') or _get_current_user_name() or 'System'))
        return jsonify({'success': True, 'promo_code': promo_code, **result})
    except Exception as e:
        return jsonify({'success': False, 'promo_code': promo_code, 'error': str(e)}), 500

@promo_bp.route('/debug/sql/<promo_code>', methods=['GET'])
def debug_sql_meta(promo_code):
    """Return JSON metadata about the generated SQL file & in-memory state for deep troubleshooting."""
    dm = _ensure_data_manager()
    promo = dm.get_promo(promo_code) or {}
    path = _promo_sql_file_path(promo_code)
    meta = {
        'promo_code': promo_code,
        'in_memory_has_generated_sql': bool(promo.get('generated_sql')),
        'in_memory_length': len(promo.get('generated_sql','')),
        'disk_path': path,
        'disk_exists': os.path.exists(path),
        'disk_length': None,
        'disk_first_200': None
    }
    if meta['disk_exists']:
        try:
            with open(path,'r',encoding='utf-8',errors='replace') as fh:
                content = fh.read()
            meta['disk_length'] = len(content)
            meta['disk_first_200'] = content[:200]
        except Exception as e:
            meta['disk_error'] = str(e)
    return jsonify(meta)

@promo_bp.route('/clear_trade_data/<promo_code>', methods=['POST'])
def clear_trade_data(promo_code):
    """Clear all trade-related data for a promotion"""
    try:
        dm = _ensure_data_manager()
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            return jsonify({'success': False, 'error': 'Promotion not found'})
        
        # Clear trade-related fields
        trade_fields = [
            'trade_in_group_id', 'broken_trade',
            'trade_tier_1_make_model', 'trade_tier_1_amount', 'trade_tier_1_cond_id', 
            'trade_tier_1_min_fmv', 'trade_tier_1_max_fmv',
            'trade_tier_2_make_model', 'trade_tier_2_amount', 'trade_tier_2_cond_id',
            'trade_tier_2_min_fmv', 'trade_tier_2_max_fmv',
            'trade_tier_3_make_model', 'trade_tier_3_amount', 'trade_tier_3_cond_id',
            'trade_tier_3_min_fmv', 'trade_tier_3_max_fmv',
            'trade_tier_4_make_model', 'trade_tier_4_amount', 'trade_tier_4_cond_id',
            'trade_tier_4_min_fmv', 'trade_tier_4_max_fmv'
        ]
        
        for field in trade_fields:
            if field == 'broken_trade':
                promo_data[field] = 'N'  # Reset to default value
            else:
                promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        dm.save_promo(promo_code, promo_data, user_name=_get_current_user_name() or 'System')
        
        return jsonify({'success': True, 'message': 'Trade data cleared successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/clear_tiers_data/<promo_code>', methods=['POST'])
def clear_tiers_data(promo_code):
    """Clear all tiers-related data for a promotion"""
    try:
        dm = _ensure_data_manager()
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            return jsonify({'success': False, 'error': 'Promotion not found'})
        
        # Clear tiers-related fields
        tier_fields = [
            'tiered_group_id',
            'tier_1_amount', 'tier_1_sku_group_id', 'tier_1_devices',
            'tier_2_amount', 'tier_2_sku_group_id', 'tier_2_devices',
            'tier_3_amount', 'tier_3_sku_group_id', 'tier_3_devices',
            'tier_4_amount', 'tier_4_sku_group_id', 'tier_4_devices'
        ]
        
        for field in tier_fields:
            promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        dm.save_promo(promo_code, promo_data, user_name=_get_current_user_name() or 'System')
        
        return jsonify({'success': True, 'message': 'Tiers data cleared successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/clear_segment_data/<promo_code>', methods=['POST'])
def clear_segment_data(promo_code):
    """Clear all segmentation-related data for a promotion"""
    try:
        dm = _ensure_data_manager()
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            return jsonify({'success': False, 'error': 'Promotion not found'})
        
        # Clear segmentation-related fields
        segment_fields = [
            'segment_name', 'sub_segment', 'segment_group_id', 'segment_level'
        ]
        
        for field in segment_fields:
            promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        dm.save_promo(promo_code, promo_data, user_name=_get_current_user_name() or 'System')
        
        return jsonify({'success': True, 'message': 'Segmentation data cleared successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/delete_file/<promo_code>/<file_type>', methods=['POST'])
def delete_file(promo_code, file_type):
    """Delete an uploaded file for a promotion"""
    try:
        dm = _ensure_data_manager()
        success = dm.delete_uploaded_file(promo_code, file_type)
        if success:
            return jsonify({'success': True, 'message': f'{file_type.replace("_", " ").title()} file deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete file'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/download_file/<promo_code>/<file_type>')
def download_file(promo_code, file_type):
    """Download uploaded files for a promotion"""
    try:
        dm = _ensure_data_manager()
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            flash("Promotion not found", "error")
            return redirect(url_for('core.home'))
        
        if not promo_data.get('uploaded_files') or file_type not in promo_data['uploaded_files']:
            flash("File not found", "error")
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))
        
        file_info = promo_data['uploaded_files'][file_type]
        file_path = file_info.get('file_path', file_info.get('path', ''))  # Handle both possible keys
        
        if not os.path.exists(file_path):
            flash("File no longer exists", "error")
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))
        
        return send_file(file_path, as_attachment=True, download_name=file_info['original_name'])
    except Exception as e:
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for('promo.edit_promo', promo_code=promo_code))

@promo_bp.route('/download_sql/<promo_code>')
def download_sql(promo_code):
    """Download generated SQL for a promotion"""
    try:
        dm = _ensure_data_manager()
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            flash("Promotion not found", "error")
            return redirect(url_for('core.home'))
        
        if not promo_data.get('generated_sql'):
            flash("No SQL generated yet", "error")
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))
        
        # Create temporary SQL file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(promo_data['generated_sql'])
            temp_path = f.name
        
        filename = f"{promo_code}_promo_eligibility_rules.sql"
        
        def remove_file(response):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            return response
        
        return send_file(temp_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f"Error downloading SQL: {str(e)}", "error")
        return redirect(url_for('promo.edit_promo', promo_code=promo_code))

@promo_bp.route('/get_full_sql/<promo_code>')
def get_full_sql(promo_code):
    """Get the full SQL for a promotion via AJAX"""
    try:
        dm = _ensure_data_manager()
        promo_data = dm.get_promo(promo_code)
        if not promo_data:
            return jsonify({'success': False, 'error': 'Promotion not found'})
        
        sql = promo_data.get('generated_sql', '')
        if not sql:
            return jsonify({'success': False, 'error': 'No SQL found for this promotion'})
        
        return jsonify({
            'success': True, 
            'sql': sql,
            'length': len(sql)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/get-promo-codes', methods=['GET','POST'], endpoint='get_promo_codes_page')
def get_promo_codes_page():
    """Blueprint version of get_promo_codes (RDC & SPE)"""
    dm = _ensure_data_manager()
    try:
        if request.method == 'POST':
            promo_type = request.form.get('promoType', 'rdc')
            promo_prefix = request.form.get('promoPrefix', '').strip().upper()
            promo_year = request.form.get('promoYear', '')
            bill_facing_name = request.form.get('billFacingName', '').strip()
            promo_owner = request.form.get('promoOwner', '').strip()
            start_date = request.form.get('startDate', '')
            end_date = request.form.get('endDate', '')
            description = request.form.get('description', '').strip()

            from datetime import datetime
            generated_code = f"{promo_prefix}{promo_year}"
            promo_data = {
                'code': generated_code,
                'bill_facing_name': bill_facing_name,
                'promo_owner': promo_owner,
                'promo_start_date': start_date,
                'promo_end_date': end_date,
                'description': description,
                'status': 'Draft',
                'created_date': datetime.now().strftime('%Y-%m-%d'),
                'created_by': _get_current_user_name() or 'System'
            }

            if promo_type == 'spe':
                promo_data['spe_category'] = request.form.get('speCategory', '')
                promo_data['spe_type'] = request.form.get('speType', '')
                # SPE uses JSON manager still
                from data.storage import PromoDataManager as JSONManager
                JSONManager().save_spe_promo(generated_code, promo_data, user_name=_get_current_user_name() or 'System')
                flash(f'SPE promo code {generated_code} created successfully!', 'success')
                return redirect(url_for('promo.spe_page'))
            else:
                dm.save_promo(generated_code, promo_data, user_name=_get_current_user_name() or 'System')
                flash(f'RDC promo code {generated_code} created successfully!', 'success')
                return redirect(url_for('promo.rdc_page'))

        from datetime import datetime
        current_year = datetime.now().year
        return render_template('pam/get_promo_codes.html', current_year=current_year)
    except Exception as e:
        flash(f"Error creating promo code: {str(e)}", 'error')
        from datetime import datetime
        current_year = datetime.now().year
        return render_template('pam/get_promo_codes.html', current_year=current_year)