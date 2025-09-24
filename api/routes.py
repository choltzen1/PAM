from flask import Blueprint, jsonify, request

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
                'version_history': promo_data.get('version_history', []),
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


@api_bp.route('/search_orbit/<orbit_id>', methods=['GET'])
def search_orbit(orbit_id):
    try:
        # First attempt: brute force using direct underlying JSON source by checking all promos for fresh edits
        if data_manager:
            try:
                import os, json
                promo_file = getattr(data_manager._original_manager, 'promo_file', None)
                if promo_file and os.path.exists(promo_file):
                    with open(promo_file, 'r', encoding='utf-8') as f:
                        json_promos = json.load(f)
                    for code, pdata in json_promos.items():
                        if pdata.get('orbit_id') == orbit_id:
                            return jsonify({
                                'found': True,
                                'type': 'RDC',
                                'promo_code': code,
                                'initiative_name': pdata.get('bill_facing_name', pdata.get('description', 'Unknown')),
                                'description': pdata.get('description', ''),
                                'owner': pdata.get('owner', ''),
                                'start_date': pdata.get('promo_start_date', ''),
                                'end_date': pdata.get('promo_end_date', ''),
                            })
            except Exception:
                pass
        # Fallback to cached/promoted set
        promotions_data = data_manager.get_all_promos() if data_manager else {}
        for promo_code, promo_data in promotions_data.items():
            if promo_data.get('orbit_id') == orbit_id:
                return jsonify({
                    'found': True,
                    'type': 'RDC',
                    'promo_code': promo_code,
                    'initiative_name': promo_data.get('bill_facing_name', promo_data.get('description', 'Unknown')),
                    'description': promo_data.get('description', ''),
                    'owner': promo_data.get('owner', ''),
                    'start_date': promo_data.get('promo_start_date', ''),
                    'end_date': promo_data.get('promo_end_date', ''),
                })
        spe_data = data_manager.get_all_spe_promos() if data_manager else {}
        for spe_code, spe_promo in spe_data.items():
            if spe_promo.get('orbit_id') == orbit_id:
                return jsonify({
                    'found': True,
                    'type': 'SPE',
                    'promo_code': spe_code,
                    'initiative_name': spe_promo.get('bill_facing_name', spe_promo.get('description', 'Unknown')),
                    'description': spe_promo.get('description', ''),
                    'owner': spe_promo.get('owner', ''),
                    'start_date': spe_promo.get('promo_start_date', ''),
                    'end_date': spe_promo.get('promo_end_date', ''),
                })
        # Final fallback: direct DB orbit-only lookup (record may not have code yet)
        try:
            from data.database import DatabaseManager
            dbm = DatabaseManager()
            orbit_row = dbm.get_orbit_record_by_orbit_id(orbit_id)
            if orbit_row:
                return jsonify({
                    'found': True,
                    'type': 'RDC',
                    'promo_code': '',  # intentionally blank; not yet assigned
                    'initiative_name': orbit_row.get('bill_facing_name', orbit_row.get('description','Unknown')),
                    'description': orbit_row.get('description',''),
                    'owner': orbit_row.get('owner',''),
                    'start_date': orbit_row.get('promo_start_date',''),
                    'end_date': orbit_row.get('promo_end_date',''),
                    'note': 'Orbit record located (no promo code assigned yet)'
                })
        except Exception:
            pass
        return jsonify({'found': False, 'message': f'Orbit ID {orbit_id} not found in promotions data'})
    except Exception as e:
        return jsonify({'found': False, 'error': str(e)})


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

@api_bp.route('/generate_next_promo_code', methods=['GET'])
def generate_next_promo_code():
    """Compute next promo code based on existing codes.

    Rules:
    - Consider codes matching ^[A-Z][0-9]{3}$.
    - Find highest letter; within that letter find max numeric.
    - Increment numeric; if > 999 roll to next letter and numeric=1 (formatted 001).
    - If rollover past 'Z', return error.
    - If no codes exist (unlikely in current state), start at 'A001'.
    """
    try:
        if not data_manager:
            return jsonify({'success': False, 'error': 'Data manager unavailable'}), 500
        # New simplified DB-first sequential logic
        from data.database import DatabaseManager
        from data.code_tracking import load_issued_codes, record_issued_code
        issued = load_issued_codes()
        dbm = DatabaseManager()
        highest = dbm.get_highest_sequential_promo_code()
        import re
        pat = re.compile(r'^([A-Z])(\d{1,4})$')
        rolled = False
        if not highest:
            # Seed at R1 => format R001
            letter = 'R'
            num = 1
        else:
            m = pat.match(highest.upper())
            if not m:
                letter = 'R'; num = 1
            else:
                letter = m.group(1)
                num = int(m.group(2)) + 1
                if num > 9999:  # safeguard upper bound (4 digits allowed by regex)
                    if letter == 'Z':
                        return jsonify({'success': False, 'error': 'Exhausted code space'}), 400
                    letter = chr(ord(letter) + 1)
                    num = 1
                    rolled = True
        # Skip any tombstoned codes (rare unless DB behind file state). Increment until free.
        while True:
            width = 3 if num <= 999 else 4
            candidate = f"{letter}{num:0{width}d}"
            if candidate not in issued:
                break
            num += 1
        record_issued_code(candidate)
        return jsonify({'success': True, 'next_code': candidate, 'base_letter': letter, 'rolled': rolled})
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
    try:
        if not data_manager:
            return jsonify({'success': False, 'error': 'Data manager unavailable'}), 500
        body = request.get_json() or {}
        orbit_id = (body.get('orbit_id') or '').strip()
        if not orbit_id:
            return jsonify({'success': False, 'error': 'orbit_id required'}), 400
        # Check if orbit already assigned
        existing = data_manager.get_all_promos() or {}
        for code, pdata in existing.items():
            if pdata.get('orbit_id') == orbit_id:
                return jsonify({'success': False, 'error': 'Orbit already assigned', 'existing_code': code}), 409
        # Generate next code (reuse logic - inline to avoid extra HTTP call)
        from data.database import DatabaseManager
        from data.code_tracking import load_issued_codes, record_issued_code
        issued = load_issued_codes()
        dbm = DatabaseManager()
        highest = dbm.get_highest_sequential_promo_code()
        import re
        pat = re.compile(r'^([A-Z])(\d{1,4})$')
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
        # Fetch orbit record from DB
        from data.database import DatabaseManager
        dbm = DatabaseManager()
        orbit_row = dbm.get_full_orbit_record_by_orbit_id(orbit_id)
        if not orbit_row:
            return jsonify({'success': False, 'error': f'Orbit {orbit_id} not found in DB'}), 404
        # Convert to JSON storage format if code present or not
        # Use existing convert helper if possible
        converted = dbm.convert_db_record_to_json_format(orbit_row) if hasattr(dbm, 'convert_db_record_to_json_format') else {}
        # Overlay essentials
        converted['code'] = next_code
        converted['orbit_id'] = orbit_id
        if not converted.get('description'):
            converted['description'] = orbit_row.get('description','')
        if not converted.get('bill_facing_name'):
            converted['bill_facing_name'] = orbit_row.get('bill_facing_name') or orbit_row.get('description','')
        # Persist
        data_manager.save_promo(next_code, converted, user_name='System')
        saved = data_manager.get_promo(next_code) or {}
        return jsonify({
            'success': True,
            'promo_code': next_code,
            'orbit_id': orbit_id,
            'rolled': rolled,
            'base_letter': base_letter,
            'fields_imported': len(converted.keys()),
            'owner': saved.get('owner'),
            'description': saved.get('description')
        })
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
