from flask import Blueprint, jsonify, request
from services.jira_utils import create_jira_summary

api_bp = Blueprint('api', __name__, url_prefix='/api')

data_manager = None  # set during app factory initialization


def init_data_manager(dm):
    global data_manager
    data_manager = dm


@api_bp.route('/get_promo_details/<promo_code>', methods=['GET'])
def get_promo_details(promo_code):
    try:
        promo_data = data_manager.get_promo(promo_code) if data_manager else {}
        if promo_data:
            return jsonify({
                'found': True,
                'type': 'RDC',
                'promo_code': promo_code,
                'owner': promo_data.get('owner', ''),
                'description': promo_data.get('description', ''),
                'bill_facing_name': promo_data.get('bill_facing_name', ''),
                'orbit_id': promo_data.get('orbit_id', ''),
                'bptcr': promo_data.get('bptcr', ''),
                'initiative_name': promo_data.get('initiative_name', ''),
                'jira_ticket': promo_data.get('jira_ticket', ''),
                'promo_start_date': promo_data.get('promo_start_date', ''),
                'promo_end_date': promo_data.get('promo_end_date', ''),
                'account_type': promo_data.get('account_type', ''),
                'activation_type': promo_data.get('activation_type', ''),
                'active_line_required': promo_data.get('active_line_required', ''),
                'dcd_web_cart': promo_data.get('dcd_web_cart', ''),
                'device_sales_type': promo_data.get('device_sales_type', ''),
                'finance_type': promo_data.get('finance_type', ''),
                'fpd_display': promo_data.get('fpd_display', ''),
                'maintain_active_line': promo_data.get('maintain_active_line', ''),
                'maintain_soc': promo_data.get('maintain_soc', ''),
                'market_group': promo_data.get('market_group', ''),
                'msip_drogs': promo_data.get('msip_drogs', ''),
                'product_type': promo_data.get('product_type', ''),
                'promo_duration': promo_data.get('promo_duration', ''),
                'sales_application': promo_data.get('sales_application', ''),
                'soc_grouping': promo_data.get('soc_grouping', ''),
                'store_group': promo_data.get('store_group', ''),
                'trade_in_grace': promo_data.get('trade_in_grace', ''),
                'trade_in': promo_data.get('bogo', ''),
                'broken_trade': promo_data.get('Broken_Trade', ''),
                'on_menu': promo_data.get('on_menu', ''),
                'mpss_lookback': promo_data.get('mpss_lookback', ''),
                # Version history removed
                'promo_notes': promo_data.get('promo_notes', ''),
                'status': 'Launched' if promo_data.get('promo_end_date') else 'In Progress'
            })

        spe_data = data_manager.get_all_spe_promos() if data_manager else {}
        if promo_code in spe_data:
            spe_promo = spe_data[promo_code]
            return jsonify({
                'found': True,
                'type': 'SPE',
                'promo_code': promo_code,
                'owner': spe_promo.get('owner', ''),
                'promo_start_date': spe_promo.get('promo_start_date', ''),
                'promo_end_date': spe_promo.get('promo_end_date', ''),
                'account_type': spe_promo.get('account_type', ''),
                'activation_type': spe_promo.get('activation_type', ''),
                'active_line_required': spe_promo.get('active_line_required', ''),
                'dcd_web_cart': spe_promo.get('dcd_web_cart', ''),
                'device_sales_type': spe_promo.get('device_sales_type', ''),
                'finance_type': spe_promo.get('finance_type', ''),
                'fpd_display': spe_promo.get('fpd_display', ''),
                'maintain_active_line': spe_promo.get('maintain_line_count_days', ''),
                'maintain_soc': spe_promo.get('maintain_soc', ''),
                'market_group': spe_promo.get('market_group', ''),
                'msip_drogs': spe_promo.get('msip_drogs', ''),
                'product_type': spe_promo.get('product_type', ''),
                'promo_duration': spe_promo.get('promo_duration', ''),
                'sales_application': spe_promo.get('sales_application', ''),
                'soc_grouping': spe_promo.get('soc_grouping', ''),
                'store_group': spe_promo.get('store_group', ''),
                'trade_in_grace': spe_promo.get('channel_grace_period', ''),
                'trade_in': spe_promo.get('trade_in', ''),
                'broken_trade': spe_promo.get('broken_trade', ''),
                'mpss_lookback': spe_promo.get('mpss_lookback', ''),
            })

        return jsonify({'found': False, 'message': f'Promo code {promo_code} not found'})
    except Exception as e:
        return jsonify({'found': False, 'error': str(e)})

@api_bp.route('/jira_summary/<promo_code>', methods=['GET'])
def jira_summary(promo_code):
    """Return standardized JIRA summary for a promo code (or orbit-only record fallback)."""
    try:
        promo_data = data_manager.get_promo(promo_code) if data_manager else {}
        if promo_data:
            return jsonify({'success': True, 'promo_code': promo_code, 'summary': create_jira_summary(promo_data)})
        # Fallback: attempt orbit-only lookup for summary components if promo not yet created
        orbit_id = (promo_code or '').strip() if (promo_code or '').upper().startswith('ORB') else ''
        if orbit_id and data_manager:
            # If promo_code itself looks like an orbit id, attempt to find record in orbit table
            from data.database import DatabaseManager
            dbm = DatabaseManager()
            orbit_record = dbm.get_orbit_record_by_orbit_id(orbit_id) or {}
            if orbit_record:
                pseudo = {
                    'code': '',
                    'orbit_id': orbit_record.get('orbit_id'),
                    'initiative_name': orbit_record.get('initiative_name') or orbit_record.get('bill_facing_name') or orbit_record.get('description'),
                    'promo_start_date': orbit_record.get('start_date')
                }
                return jsonify({'success': True, 'promo_code': '', 'summary': create_jira_summary(pseudo)})
        return jsonify({'success': False, 'error': 'Promotion not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/search_orbit/<orbit_id>', methods=['GET'])
def search_orbit(orbit_id):
    try:
        # Orbit-only lookup (no promo table fallback)
        from services.promo_codes_service import orbit_search
        from flask import request
        debug = request.args.get('debug') in ('1','true','yes')
        result = orbit_search(orbit_id)
        # Map standalone payload to legacy response shape if needed
        if not result.get('found'):
            msg = result.get('error') or f'Orbit ID {orbit_id} not located'
            payload = {'found': False, 'message': msg}
            if debug:
                import os
                payload['debug'] = {
                    'orbit_id': orbit_id,
                    'source_table': result.get('source_table'),
                    'env': {
                        'ORBIT_DB_SERVER': os.getenv('ORBIT_DB_SERVER'),
                        'ORBIT_DB_DATABASE': os.getenv('ORBIT_DB_DATABASE'),
                        'ORBIT_TABLE': os.getenv('ORBIT_TABLE'),
                        'ORBIT_CONNECTION_STRING': bool(os.getenv('ORBIT_CONNECTION_STRING'))
                    },
                    'used_connection_string': result.get('_used_connection'),
                }
            return jsonify(payload)
        return jsonify({
            'found': True,
            'type': 'RDC',  # execution type not derived from orbit table now
            'promo_code': '',
            'pending_creation': True,
                'initiative_name': result.get('initiative_name') or result.get('bill_facing_name') or result.get('description','Unknown'),
            'description': result.get('description',''),
            'owner': result.get('owner',''),
            'start_date': result.get('start_date',''),
            'end_date': result.get('end_date',''),
            'source_table': result.get('source_table')
        })
    except Exception as e:
        return jsonify({'found': False, 'error': str(e)})


@api_bp.route('/orbit_lookup_debug/<orbit_id>', methods=['GET'])
def orbit_lookup_debug(orbit_id):
    try:
        from data.database import DatabaseManager
        dbm = DatabaseManager()
        row = dbm.get_orbit_record_by_orbit_id(orbit_id)
        if row:
            return jsonify({'found': True, 'table': row.get('_table'), 'orbit_id': orbit_id})
        return jsonify({'found': False, 'orbit_id': orbit_id})
    except Exception as e:
        return jsonify({'found': False, 'error': str(e), 'orbit_id': orbit_id})


@api_bp.route('/update_testing_status', methods=['POST'])
def update_testing_status():
    try:
        data = request.get_json() or {}
        promo_code = data.get('promo_code')
        test_type = data.get('test_type')
        status = data.get('status')
        if not all([promo_code, test_type, status]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        if test_type not in ('functional','zlab'):
            return jsonify({'success': False, 'error': 'Invalid test_type'}), 400
        promo_data = data_manager.get_promo(promo_code) if data_manager else {}
        if not promo_data:
            return jsonify({'success': False, 'error': f'Promotion {promo_code} not found'}), 404
        field_name = 'test_status' if test_type == 'functional' else 'zlab_status'
        promo_data[field_name] = status
        if data_manager:
            data_manager.save_promo(promo_code, promo_data, user_name='System')
        updated_data = data_manager.get_promo(promo_code) if data_manager else {}
        saved_value = updated_data.get(field_name)
        if saved_value != status:
            return jsonify({'success': False, 'error': f'Save verification failed. Expected {status}, got {saved_value}'}), 500
        safe_test_type = (test_type or '').title()
        return jsonify({
            'success': True,
            'message': f'{safe_test_type} testing status updated to {status}',
            'updated_field': field_name,
            'new_value': status,
            'verification': saved_value,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/promo_code_by_orbit/<orbit_id>', methods=['GET'])
def promo_code_by_orbit(orbit_id):
    """Return promo code for a given orbit_id by scanning PAM promos.

    Implementation detail: current data_manager exposes get_all_promos() returning
    mapping code -> promo_data (each contains orbit_id). We iterate to locate match.
    If multiple promos share orbit_id, we return the first encountered (could refine with timestamp ordering later).
    """
    try:
        if not data_manager:
            return jsonify({'success': False, 'error': 'Data manager unavailable'}), 500
        oid = (orbit_id or '').strip()
        if not oid:
            return jsonify({'success': False, 'error': 'orbit_id required'}), 400
        promos = data_manager.get_all_promos() or {}
        # Normalize list form
        if isinstance(promos, list):
            norm = {}
            for rec in promos:
                c = str(rec.get('code','')).strip()
                if c:
                    norm[c] = rec
            promos = norm
        found_code = None
        found_record = None
        for code, pdata in promos.items():
            if str(pdata.get('orbit_id') or '').strip() == oid:
                found_code = code
                found_record = pdata
                break
        if not found_code:
            return jsonify({'success': False, 'error': 'No promo found for orbit_id'}), 404
        return jsonify({'success': True, 'promo_code': found_code, 'orbit_id': oid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/set_sales_application', methods=['POST'])
def set_sales_application():
    """Set sales_application for a given promo code.

    JSON body: { "promo_code": "R123", "sales_application": "S15" }
    Returns success flag and updated value.
    """
    try:
        if not data_manager:
            return jsonify({'success': False, 'error': 'Data manager unavailable'}), 500
        payload = request.get_json() or {}
        promo_code = (payload.get('promo_code') or '').strip()
        sales_app = (payload.get('sales_application') or '').strip()
        if not promo_code or not sales_app:
            return jsonify({'success': False, 'error': 'promo_code and sales_application required'}), 400
        # Load existing promo
        promo = data_manager.get_promo(promo_code)
        if not promo:
            return jsonify({'success': False, 'error': 'Promo not found'}), 404
        # Update field and persist
        promo['sales_application'] = sales_app
        data_manager.save_promo(promo_code, promo, user_name='System')
        return jsonify({'success': True, 'promo_code': promo_code, 'sales_application': sales_app})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/generate_next_promo_code', methods=['GET'])
def generate_next_promo_code():
        """Atomically create (or detect existing) a promo from an orbit record.

        REQUIRED Query Params:
            orbit_id: The source orbit record id to ingest.
        OPTIONAL:
            execution_type: Desired_Execution value (default RDC)

        Behavior:
            - If orbit already has a promo, returns existing_code (409).
            - Else generates next sequential code, inserts new row, records version history, returns payload.
        """
        try:
                if not data_manager:
                        return jsonify({'success': False, 'error': 'Data manager unavailable'}), 500
                orbit_id = (request.args.get('orbit_id') or '').strip()
                if not orbit_id:
                        return jsonify({'success': False, 'error': 'orbit_id required'}), 400
                exec_type = (request.args.get('execution_type') or 'RDC').strip() or 'RDC'
                config = (request.args.get('config') or '').strip().lower()
                from services.promo_code_workflow import PromoCodeWorkflow
                workflow = PromoCodeWorkflow(data_manager)
                result = workflow.create_from_orbit(orbit_id, execution_type=exec_type, user='System', config=config)
                if result.get('success') and 'code' in result:
                        result['promo_code'] = result['code']
                status = 200 if result.get('success') else (409 if result.get('existing_code') else 400)
                return jsonify(result), status
        except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/generate_and_ingest', methods=['POST'])
def generate_and_ingest():
    """Generate the next promo code and ingest orbit data into PAM storage.

    Expected JSON: { "orbit_id": "####" }
    Flow:
      1. Validate orbit_id.
      2. Ensure no existing promo already linked to this orbit_id.
      3. Generate next code (internal call to logic mirroring generate_next_promo_code).
      4. Fetch full orbit record from DB; if missing -> 404.
      5. Map DB record to JSON promo schema; set code + orbit_id.
      6. Save via data_manager.save_promo.
      7. Return success payload.
    """
    if not data_manager:
        return jsonify({'success': False, 'error': 'Data manager unavailable'}), 500
    try:
        body = request.get_json() or {}
        orbit_id = (body.get('orbit_id') or '').strip()
        if not orbit_id:
            return jsonify({'success': False, 'error': 'orbit_id required'}), 400
        # Existing promo check
        existing = data_manager.get_all_promos() or {}
        for code, pdata in existing.items():
            if pdata.get('orbit_id') == orbit_id:
                return jsonify({'success': False, 'error': 'Orbit already assigned', 'existing_code': code}), 409
        # Generate next sequential code using issued codes file
        from data.code_tracking import load_issued_codes, record_issued_code
        issued = load_issued_codes()
        import re
        pat = re.compile(r'^([A-Z])(\d{1,4})$')
        seq_codes = [c for c in issued if pat.match(c)]
        highest = None
        if seq_codes:
            def key(c):
                m = pat.match(c)
                if not m:
                    return ('', -1)
                return (m.group(1), int(m.group(2)))
            highest = sorted(seq_codes, key=key)[-1]
        rolled = False
        if not highest:
            base_letter = 'R'; num = 1
        else:
            m = pat.match(highest.upper())
            if not m:
                base_letter = 'R'; num = 1
            else:
                base_letter = m.group(1)
                num = int(m.group(2)) + 1
            if num > 9999:
                if base_letter == 'Z':
                    return jsonify({'success': False, 'error': 'Exhausted code space'}), 400
                base_letter = chr(ord(base_letter)+1)
                num = 1
                rolled = True
        while True:
            width = 3 if num <= 999 else 4
            next_code = f"{base_letter}{num:0{width}d}"
            if next_code not in issued:
                break
            num += 1
        record_issued_code(next_code)
        # Orbit fetch
        from data.orbit_database import OrbitDatabaseManager
        odm = OrbitDatabaseManager()
        orbit_row = odm.get_orbit_record(orbit_id)
        if not orbit_row or orbit_row.get('_error'):
            # Fallback to legacy DatabaseManager for test compatibility
            try:
                from data.database import DatabaseManager
                legacy_dbm = DatabaseManager()
                legacy_row = legacy_dbm.get_full_orbit_record_by_orbit_id(orbit_id)
            except Exception:
                legacy_row = None
            if legacy_row:
                orbit_row = legacy_row if isinstance(legacy_row, dict) else dict(legacy_row)
            else:
                err = orbit_row.get('_error') if isinstance(orbit_row, dict) else 'unknown error'
                status = 404 if err == 'not found' else 500
                return jsonify({'success': False, 'error': f'Orbit {orbit_id} not found' if status == 404 else err}), status
        converted = {
            'code': next_code,
            'orbit_id': orbit_id,
            'bill_facing_name': orbit_row.get('bill_facing_name') or orbit_row.get('description',''),
            'description': orbit_row.get('description',''),
            'owner': orbit_row.get('Owner') or orbit_row.get('owner')
        }
        if orbit_row.get('promo_start_date'):
            converted['start_date'] = orbit_row.get('promo_start_date')
        if orbit_row.get('promo_end_date'):
            converted['end_date'] = orbit_row.get('promo_end_date')
        data_manager.save_promo(next_code, converted, user_name='System')
        saved = data_manager.get_promo(next_code) or {}
        return jsonify({'success': True, 'promo_code': next_code, 'orbit_id': orbit_id, 'rolled': rolled, 'base_letter': base_letter, 'fields_imported': len(converted), 'owner': saved.get('owner'), 'description': saved.get('description')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/create_from_orbit', methods=['POST'])
def create_from_orbit():
    """Create a new promotion by supplying an orbit_id.

    JSON Body: { "orbit_id": "12345", "execution_type": "RDC" }

    Returns: success flag, new promo_code, orbit_id, and basic promo fields.
    """
    try:
        if not data_manager:
            return jsonify({'success': False, 'error': 'Data manager unavailable'}), 500
        body = request.get_json() or {}
        orbit_id = (body.get('orbit_id') or '').strip()
        desired_exec = (body.get('execution_type') or 'RDC').strip() or 'RDC'
        if not orbit_id:
            return jsonify({'success': False, 'error': 'orbit_id required'}), 400
        from services.promo_code_workflow import PromoCodeWorkflow
        workflow = PromoCodeWorkflow(data_manager)
        result = workflow.create_from_orbit(orbit_id, execution_type=desired_exec, user='System')
        status_code = 200 if result.get('success') else (409 if result.get('existing_code') else 400)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/recent_generated_promos', methods=['GET'])
def recent_generated_promos():
    """Return last 10 generated promos (RDC + SPE) using created_at descending.

    Data source: merged hybrid manager promos & SPE promos. Falls back to JSON timestamps.
    """
    try:
        if not data_manager:
            return jsonify({'success': False, 'promos': []})
        import datetime
        promos = data_manager.get_all_promos() or {}
        # promos returns dict (code->data) or list depending on manager; normalize
        if isinstance(promos, list):
            # convert list of dicts with 'code'
            norm = {}
            for rec in promos:
                c = str(rec.get('code','')).strip()
                if c:
                    norm[c] = rec
            promos = norm
        spe = {}
        try:
            spe = data_manager.get_all_spe_promos() or {}
            if isinstance(spe, list):
                conv = {}
                for rec in spe:
                    c = str(rec.get('code','')).strip()
                    if c:
                        conv[c] = rec
                spe = conv
        except Exception:
            spe = {}
        combined = {}
        combined.update(promos)
        combined.update(spe)
        rows = []
        for code, pdata in combined.items():
            created_raw = pdata.get('created_at') or pdata.get('updated_at') or ''
            try:
                created_dt = datetime.datetime.fromisoformat(created_raw.replace('Z','+00:00')) if created_raw else datetime.datetime.min
            except Exception:
                created_dt = datetime.datetime.min
            rows.append({
                'code': code,
                'orbit_id': pdata.get('orbit_id',''),
                'description': pdata.get('bill_facing_name') or pdata.get('description',''),
                'created_at': created_dt.isoformat(),
                'type': pdata.get('Desired_Execution') or ('SPE' if code.startswith('SP') else 'RDC')
            })
        rows.sort(key=lambda r: r['created_at'], reverse=True)
        latest = rows[:10]
        return jsonify({'success': True, 'promos': latest, 'count': len(latest)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'promos': []}), 500
