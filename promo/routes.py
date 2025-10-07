from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from data.storage import PromoDataManager

# Create blueprint for promotion routes
promo_bp = Blueprint('promo', __name__)

# Data manager will be set by the main app
data_manager: Optional['PromoDataManager'] = None

def init_data_manager(dm):
    """Initialize the data manager from the main app"""
    global data_manager
    data_manager = dm

def _ensure_data_manager():
    """Ensure data_manager is initialized, raise error if not"""
    if data_manager is None:
        raise RuntimeError("Data manager not initialized. Call init_data_manager() first.")
    return data_manager

# --- Batch 1: Blueprint wrapper endpoints (temporary redirects to legacy views) ---
@promo_bp.route('/promotions', endpoint='promotions_page')
def promotions_page():
    dm = _ensure_data_manager()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '', type=str)
    owner_filter = request.args.get('owner', 'all', type=str)
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
    return render_template(
        'promotions.html',
        promotions=promo_data['promotions'],
        pagination=promo_data['pagination'],
        owners=promo_data['owners'],
        search_query=search,
        selected_owner=owner_filter,
        active_tab='RDC'
    )

@promo_bp.route('/spe', endpoint='spe_page')
def spe_page():
    dm = _ensure_data_manager()
    try:
        spe_data_dict = dm.get_all_spe_promos()
        spe_data = []
        for key in sorted(spe_data_dict.keys()):
            item = spe_data_dict[key]
            item['code'] = key
            spe_data.append(item)
        return render_template('spe.html', spe_data=spe_data, active_tab='SPE')
    except Exception as e:
        flash(f'Error loading SPE data: {e}', 'error')
        return render_template('spe.html', spe_data=[], active_tab='SPE')

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
        return render_template('rebates.html', rebates_data=rebates_list, owners=owners, search_query=search, selected_owner=owner_filter, active_tab='Rebates')
    except Exception as e:
        flash(f'Error loading rebates data: {e}', 'error')
        return render_template('rebates.html', rebates_data=[], owners=[], search_query='', selected_owner='all', active_tab='Rebates')

@promo_bp.route('/date-mismatch', endpoint='date_mismatch_page')
def date_mismatch_page():
    dm = _ensure_data_manager()
    try:
        mismatch_data = dm.get_date_mismatched_promos()
        return render_template('date_mismatch.html',
                               promos=mismatch_data.get('promos', []),
                               owners=mismatch_data.get('owners', []),
                               user_name='Cade Holtzen')
    except Exception as e:
        flash(f'Error loading date mismatch data: {e}', 'error')
        return render_template('date_mismatch.html', promos=[], owners=[], user_name='Cade Holtzen')

@promo_bp.route('/update-pam-date/<promo_code>', methods=['POST'], endpoint='update_pam_date')
@promo_bp.route('/update_pam_date/<promo_code>', methods=['POST'])  # backward-compatible alias (old JS used underscore)
def update_pam_date_bp(promo_code):
    dm = _ensure_data_manager()
    try:
        res = dm.sync_promo_end_date_from_orbit(promo_code, user_name='System')
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
        # Record a single compact version history event per promo
        dm = _ensure_data_manager()
        for promo_code in promo_codes:
            if hasattr(dm, 'record_date_mismatch_sql'):
                # Provide minimal metrics (no huge SQL blob)
                dm.record_date_mismatch_sql(promo_code, 'System', generation_time=0.0, sql_length=sum(len(s) for s in sql_statements))
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
    return render_template('generate_sql_form.html', promo_codes=[promo_code], is_batch=False)

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
            return render_template('generate_sql_form.html', promo_codes=promo_codes, is_batch=len(promo_codes) > 1, operator_id=operator_id, new_end_date=new_end_date)
        if not promo_codes:
            flash('No promotion codes provided', 'error')
            return redirect(url_for('promo.date_mismatch_page'))
        if not new_end_date:
            flash('New end date is required', 'error')
            return render_template('generate_sql_form.html', promo_codes=promo_codes, is_batch=len(promo_codes) > 1, operator_id=operator_id, new_end_date=new_end_date)
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
                return render_template('generate_sql_form.html', promo_codes=promo_codes, is_batch=len(promo_codes) > 1, operator_id=operator_id, new_end_date=new_end_date)
        return render_template('sql_results.html', sql_statements=sql_statements, promo_codes=promo_codes)
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
        try:
            dm = _ensure_data_manager()
            for code in successful_promos:
                if hasattr(dm, 'record_date_mismatch_sql'):
                    # Use individual statement length for each promo for better granularity
                    try:
                        stmt = next((s for s in sql_statements if f"promo_code = '{code}'" in s), '')
                        dm.record_date_mismatch_sql(code, 'System', generation_time=0.0, sql_length=len(stmt))
                    except Exception:
                        pass
        except Exception:
            pass
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
    tab = request.args.get('tab','Details')
    from data.storage import PromoDataManager as JSONManager
    json_manager = JSONManager()
    if request.method == 'POST':
        tab = request.form.get('active_tab', tab)
        spe_data = json_manager.get_spe_promo(promo_code) or {
            'code': promo_code,
            'owner': 'Unknown',
            'description': '',
            'start_date': '',
            'end_date': '',
            'status': 'Draft'
        }
        updated = {k:v for k,v in request.form.items() if k != 'active_tab'}
        spe_data.update(updated)
        try:
            json_manager.save_spe_promo(promo_code, spe_data, user_name='Cade Holtzen')
            flash(f'SPE {promo_code} saved successfully!', 'success')
            return redirect(url_for('promo.edit_spe_page', promo_code=promo_code, tab=tab))
        except Exception as e:
            flash(f'Error saving SPE: {e}', 'error')
    spe_data = json_manager.get_spe_promo(promo_code) or {
        'code': promo_code,
        'owner': 'Unknown',
        'description': '',
        'start_date': '',
        'end_date': '',
        'status': 'Draft'
    }
    return render_template('edit_spe.html', promo=spe_data, spe_data=spe_data, spe_key=promo_code, active_tab=tab,
                           soc_groupings=json_manager.get_soc_groupings(),
                           soc_grouping_details=json_manager.get_soc_grouping_details(),
                           account_types=json_manager.get_account_types(),
                           account_type_details=json_manager.get_account_type_details(),
                           sales_applications=json_manager.get_sales_applications(),
                           sales_application_details=json_manager.get_sales_application_details(),
                           user_name='Cade Holtzen')

@promo_bp.route('/test-page', endpoint='test_page')
def test_page():
    return render_template('test.html')

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
            return p.get('promo_start_date') or p.get('promo_srart_date')
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
        return render_template('capacity.html',
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
        return render_template('capacity.html',
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
    @promo_bp.route('/download_file/<promo_code>/<file_type>', endpoint='download_file')
    def download_file(promo_code, file_type):
        dm = _ensure_data_manager()
        try:
            file_path = dm.get_file_path(promo_code, file_type)
            if file_path and os.path.exists(file_path):
                return send_file(file_path, as_attachment=True)
            flash('File not found', 'error')
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))
        except Exception as e:
            flash(f'Error downloading file: {e}', 'error')
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))

    @promo_bp.route('/download_sql/<promo_code>', endpoint='download_sql')
    def download_sql(promo_code):
        dm = _ensure_data_manager()
        try:
            promo_data = dm.get_promo(promo_code)
            if not promo_data:
                flash('Promo not found', 'error')
                return redirect(url_for('promo.promotions_page'))
            sql_file_info = promo_data.get('sql_file')
            if sql_file_info and os.path.exists(sql_file_info.get('path','')):
                return send_file(sql_file_info['path'], as_attachment=True, download_name=sql_file_info['filename'])
            from promo.builders import generate_promo_eligibility_sql
            sql_statement = generate_promo_eligibility_sql(promo_data)
            import tempfile
            temp_dir = tempfile.gettempdir()
            sql_filename = f"{promo_code}_promo_eligibility_rules.sql"
            temp_file_path = os.path.join(temp_dir, sql_filename)
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(sql_statement)
            return send_file(temp_file_path, as_attachment=True, download_name=sql_filename)
        except Exception as e:
            flash(f'Error generating SQL download: {e}', 'error')
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))

    @promo_bp.route('/clear_trade_data/<promo_code>', methods=['POST'], endpoint='clear_trade_data')
    def clear_trade_data(promo_code):
        dm = _ensure_data_manager()
        try:
            promo_data = dm.get_promo(promo_code)
            if not promo_data:
                return jsonify({'success': False, 'error': 'Promo not found'})
            trade_fields = [
                'trade_in_group_id','broken_trade',
                'trade_tier_1_amount','trade_tier_1_cond_id','trade_tier_1_min_fmv','trade_tier_1_max_fmv','trade_tier_1_make_model',
                'trade_tier_2_amount','trade_tier_2_cond_id','trade_tier_2_min_fmv','trade_tier_2_max_fmv','trade_tier_2_make_model',
                'trade_tier_3_amount','trade_tier_3_cond_id','trade_tier_3_min_fmv','trade_tier_3_max_fmv','trade_tier_3_make_model',
                'trade_tier_4_amount','trade_tier_4_cond_id','trade_tier_4_min_fmv','trade_tier_4_max_fmv','trade_tier_4_make_model'
            ]
            for f in trade_fields:
                promo_data[f] = 'N' if f == 'broken_trade' else ''
            dm.save_promo(promo_code, promo_data, user_name='System')
            return jsonify({'success': True, 'message': 'Trade data cleared successfully'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @promo_bp.route('/clear_tiers_data/<promo_code>', methods=['POST'], endpoint='clear_tiers_data')
    def clear_tiers_data(promo_code):
        dm = _ensure_data_manager()
        try:
            promo_data = dm.get_promo(promo_code)
            if not promo_data:
                return jsonify({'success': False, 'error': 'Promo not found'})
            tiers_fields = [
                'tiered_group_id',
                'tier_1_amount','tier_1_sku_group_id','tier_1_devices',
                'tier_2_amount','tier_2_sku_group_id','tier_2_devices',
                'tier_3_amount','tier_3_sku_group_id','tier_3_devices',
                'tier_4_amount','tier_4_sku_group_id','tier_4_devices'
            ]
            for f in tiers_fields:
                promo_data[f] = ''
            dm.save_promo(promo_code, promo_data, user_name='System')
            return jsonify({'success': True, 'message': 'Tiers data cleared successfully'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @promo_bp.route('/clear_segment_data/<promo_code>', methods=['POST'], endpoint='clear_segment_data')
    def clear_segment_data(promo_code):
        dm = _ensure_data_manager()
        try:
            promo_data = dm.get_promo(promo_code)
            if not promo_data:
                return jsonify({'success': False, 'error': 'Promo not found'})
            segment_fields = [
                'segment_name','sub_segment','segment_group_id','segment_level',
                'soc_grouping','account_type','sales_application','bptcr'
            ]
            for f in segment_fields:
                promo_data[f] = ''
            dm.save_promo(promo_code, promo_data, user_name='System')
            return jsonify({'success': True, 'message': 'Segment data cleared successfully'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

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
    return render_template('updates.html',
                           search_query=search,
                           default_promo=default_promo,
                           total_results=len(all_promos))


@promo_bp.route('/approvers', endpoint='approvers_page')
def approvers_page():
    dm = _ensure_data_manager()
    try:
        target_promo_code = request.args.get('promo_code', '').strip()
        rdc_data = dm.get_all_promos()
        from data.storage import PromoDataManager as JSONManager
        json_manager = JSONManager()
        spe_data = json_manager.get_all_spe_promos()
        rebates_data = json_manager.get_all_rebates()
        all_promos = []
        for promo_key, promo in rdc_data.items():
            all_promos.append({'code': promo.get('code', promo_key), 'owner': promo.get('owner','Unknown'), 'type':'RDC'})
        for spe_key, spe in spe_data.items():
            all_promos.append({'code': spe.get('code', spe_key), 'owner': spe.get('owner','Unknown'), 'type':'SPE'})
        for rebate_key, rebate in rebates_data.items():
            all_promos.append({'code': rebate.get('code', rebate_key), 'owner': rebate.get('owner','Unknown'), 'type':'REBATE'})
        if target_promo_code:
            target_promos = [p for p in all_promos if p['code'] == target_promo_code]
            other_promos = [p for p in all_promos if p['code'] != target_promo_code]
            all_promos = target_promos + other_promos
        promo_codes = [p['code'] for p in all_promos]
        owners = [p['owner'] for p in all_promos]
        unique_owners = sorted(list(set(owners)))
        revenue_approvers = [
            {'name': 'John Smith', 'email': 'john.smith@company.com'},
            {'name': 'Sarah Davis', 'email': 'sarah.davis@company.com'},
            {'name': 'Mike Johnson', 'email': 'mike.johnson@company.com'},
            {'name': 'Lisa Chen', 'email': 'lisa.chen@company.com'}
        ]
        return render_template('approvers.html',
                               promo_codes=promo_codes,
                               owners=owners,
                               unique_owners=unique_owners,
                               revenue_approvers=revenue_approvers,
                               target_promo_code=target_promo_code)
    except Exception as e:
        flash(f'Error loading approvers data: {e}', 'error')
        return render_template('approvers.html', promo_codes=[], owners=[], unique_owners=[], revenue_approvers=[], target_promo_code='')

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
    return render_template('reviewers.html', promo_code=promo_code, promo_data=promo_data, error_message=error_message)

@promo_bp.route('/links', endpoint='links_main_page')
def links_main_page():
    return render_template('links.html')

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
            return render_template('links.html', promo_code=promo_code_upper, promo_data=None, error_message=error_message)
        if request.method == 'POST':
            promo_data['sku_link'] = request.form.get('skuLink', '')
            promo_data['tradein_link'] = request.form.get('tradeLink', '')
            promo_data['orbit_link'] = request.form.get('orbitLink', '')
            promo_data['legal_link'] = request.form.get('legalLink', '')
            promo_data['c2_article_link'] = request.form.get('c2ArticleLink', '')
            try:
                regular_promos = dm.get_all_promos()
                if promo_code_upper in regular_promos:
                    dm.save_promo(promo_code_upper, promo_data, user_name='Current User')
                else:
                    from data.storage import PromoDataManager as JSONManager
                    json_manager = JSONManager()
                    json_manager.save_spe_promo(promo_code_upper, promo_data, user_name='Current User')
                return redirect(url_for('promo.links_page', promo_code=promo_code_upper))
            except Exception as e:
                flash(f'Error saving links: {e}', 'error')
        return render_template('links.html', promo_code=promo_code_upper, promo_data=promo_data)
    except Exception as e:
        flash(f'Error loading links for promotion: {e}', 'error')
        return redirect(url_for('promo.promotions_page'))

@promo_bp.route('/edit_promo/<promo_code>', methods=['GET', 'POST'])
def edit_promo(promo_code):
    """Handle editing of promotion data"""
    dm = _ensure_data_manager()
    
    if request.method == 'POST':
        # Get the active tab
        active_tab = request.form.get('active_tab', 'Details')
        
        # Get current promo data
        promo_data = dm.get_promo(promo_code)
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
        
        # Handle SQL generation
        if request.form.get('generate_sql'):
            from promo.builders import generate_promo_eligibility_sql
            from datetime import datetime
            import time
            try:
                # Start timing SQL generation
                start_time = time.time()
                
                # Generate SQL using the dictionary data
                sql_content = generate_promo_eligibility_sql(promo_data)
                
                # End timing
                end_time = time.time()
                generation_time = end_time - start_time
                
                # Save SQL to promo with timestamp and performance data
                # Store full SQL - remove truncation to allow complete output
                promo_data['generated_sql'] = sql_content
                promo_data['sql_truncated'] = False
                    
                promo_data['sql_generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                promo_data['sql_generation_time'] = f"{generation_time:.4f}"
                promo_data['sql_length'] = len(sql_content)
                # Persist a physical .sql file for durability across reloads
                try:
                    from data.storage import PromoDataManager as _PDM
                    # Use existing manager's save_sql_file if present
                    dm.save_sql_file(promo_code, sql_content, f"{promo_code}_promo_eligibility_rules.sql")
                except Exception as save_file_err:
                    print(f"Failed to save SQL file for {promo_code}: {save_file_err}")
                # Save promo (does not store generated_sql itself in DB, but keeps audit/version info)
                dm.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
                
                # Flash message with performance info
                flash(f"SQL generated successfully in {generation_time:.2f} seconds ({len(sql_content):,} characters)", "success")

                # Record PCR Version event in version history
                try:
                    dm.record_sql_generation(promo_code, "Cade Holtzen", generation_time, len(sql_content))
                except Exception as vh_err:
                    print(f"Version history PCR record failed: {vh_err}")
                
                # Log performance warning if slow
                if generation_time > 5.0:
                    print(f"⚠️  WARNING: SQL generation for {promo_code} took {generation_time:.2f} seconds!")
                elif generation_time > 2.0:
                    print(f"⚠️  NOTICE: SQL generation for {promo_code} took {generation_time:.2f} seconds")
                    
            except Exception as e:
                flash(f"Error generating SQL: {str(e)}", "error")
        
        # Handle file uploads
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
                            
                            dm.save_promo(promo_code, promo_data)
                            
                            flash(f"{file_key.replace('_', ' ').title()} uploaded successfully", "success")
                        else:
                            flash(f"Failed to save {file_key.replace('_', ' ')}", "error")
                    except Exception as e:
                        flash(f"Error uploading {file_key}: {str(e)}", "error")
        
        # Update promo fields based on active tab
        updated_fields = []
        for field_name, field_value in request.form.items():
            if field_name not in ['active_tab', 'generate_sql']:
                # Check if it's a new field or existing field
                if field_name in promo_data or field_value.strip():  # Update if field exists or has value
                    old_value = promo_data.get(field_name)
                    if old_value != field_value:
                        promo_data[field_name] = field_value
                        updated_fields.append(field_name)
        
        # Save changes
        if updated_fields:
            promo_data['last_changes'] = f"Updated {', '.join(updated_fields)} on {active_tab} tab"
            dm.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
            flash(f"Saved {active_tab} successfully", "success")
        
        # Redirect to maintain the active tab
        return redirect(url_for('promo.edit_promo', promo_code=promo_code, tab=active_tab))
    
    # GET request
    tab = request.args.get('tab', 'Details')
    promo_data = dm.get_promo(promo_code)
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
    
    return render_template('edit_promo.html', 
                         promo=promo_data, 
                         active_tab=tab,
                         soc_groupings=dm.get_soc_groupings(),
                         soc_grouping_details=dm.get_soc_grouping_details(),
                         account_types=dm.get_account_types(),
                         account_type_details=dm.get_account_type_details(),
                         sales_applications=dm.get_sales_applications(),
                         sales_application_details=dm.get_sales_application_details(),
                         user_name="Cade Holtzen",
                         jira_dcd_ticket=os.getenv('JIRA_DCD_CURRENT_TICKET', 'DCOMM-13037'))

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
        dm.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
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
        dm.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
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
        dm.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
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
                'created_by': 'System'
            }

            if promo_type == 'spe':
                promo_data['spe_category'] = request.form.get('speCategory', '')
                promo_data['spe_type'] = request.form.get('speType', '')
                # SPE uses JSON manager still
                from data.storage import PromoDataManager as JSONManager
                JSONManager().save_spe_promo(generated_code, promo_data, user_name='System')
                flash(f'SPE promo code {generated_code} created successfully!', 'success')
                return redirect(url_for('promo.spe_page'))
            else:
                dm.save_promo(generated_code, promo_data, user_name='System')
                flash(f'RDC promo code {generated_code} created successfully!', 'success')
                return redirect(url_for('promo.promotions_page'))

        from datetime import datetime
        current_year = datetime.now().year
        return render_template('get_promo_codes.html', current_year=current_year)
    except Exception as e:
        flash(f"Error creating promo code: {str(e)}", 'error')
        from datetime import datetime
        current_year = datetime.now().year
        return render_template('get_promo_codes.html', current_year=current_year)