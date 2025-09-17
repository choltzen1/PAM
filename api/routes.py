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
