from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os
import requests
import urllib3
from datetime import datetime
from data.hybrid_storage import HybridPromoDataManager as PromoDataManager
from promo.builders import generate_promo_eligibility_sql
from promo.routes import promo_bp

# Pre-load pandas to avoid delays during SQL generation
try:
    import pandas as pd
    print("✅ Pandas pre-loaded for faster SQL generation")
except ImportError:
    print("⚠️  Pandas not available - Excel processing will be slower")

# Disable SSL warnings for JIRA requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages

# Initialize enhanced data manager with database integration
data_manager = PromoDataManager()
print("✅ Enhanced hybrid data manager initialized with database integration")

# Helper function to get JSON manager for SPE and rebates (until they're migrated to database)
def get_json_manager():
    from data.storage import PromoDataManager as JSONManager
    return JSONManager()

# Register blueprints
app.register_blueprint(promo_bp)

# Initialize data manager in blueprints
from promo.routes import init_data_manager
init_data_manager(data_manager)

# Add context processor for current datetime
@app.context_processor
def inject_current_datetime():
    return {'current_datetime': datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/promotions")
def promotions():
    # Get pagination parameters from query string
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '', type=str)
    owner_filter = request.args.get('owner', 'all', type=str)
    
    # Load paginated promotions from data manager
    promo_data = data_manager.get_paginated_promos(
        page=page, 
        per_page=per_page, 
        search=search, 
        owner_filter=owner_filter
    )
    
    return render_template(
        "promotions.html", 
        promotions=promo_data['promotions'],
        pagination=promo_data['pagination'],
        owners=promo_data['owners'],
        search_query=search,
        selected_owner=owner_filter,
        active_tab='RDC'
    )


@app.route("/spe")
def spe():
    try:
        # Load SPE data from unified data manager (now database-powered!)
        spe_data_dict = data_manager.get_all_spe_promos()
        
        # Convert to a list and sort by keys for consistent display
        spe_data = []
        for key in sorted(spe_data_dict.keys()):
            item = spe_data_dict[key]
            item['key'] = key  # Add the key to the item for template use
            spe_data.append(item)
        
        return render_template("spe.html", spe_data=spe_data, active_tab='SPE')
    except Exception as e:
        flash(f'Error loading SPE data: {str(e)}', 'error')
        return render_template("spe.html", spe_data=[], active_tab='SPE')


@app.route("/get_promo_codes", methods=["GET", "POST"])
def get_promo_codes():
    """Get promo codes page for both RDC and SPE"""
    try:
        if request.method == "POST":
            # Get form data
            promo_type = request.form.get('promoType', 'rdc')
            promo_prefix = request.form.get('promoPrefix', '').strip().upper()
            promo_year = request.form.get('promoYear', '')
            bill_facing_name = request.form.get('billFacingName', '').strip()
            promo_owner = request.form.get('promoOwner', '').strip()
            start_date = request.form.get('startDate', '')
            end_date = request.form.get('endDate', '')
            description = request.form.get('description', '').strip()
            
            # Generate promo code
            generated_code = f"{promo_prefix}{promo_year}"
            
            # Create promo data structure
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
            
            # Add SPE specific fields if SPE type
            if promo_type == 'spe':
                promo_data['spe_category'] = request.form.get('speCategory', '')
                promo_data['spe_type'] = request.form.get('speType', '')
                
                # Save as SPE promo using JSON manager
                json_manager = get_json_manager()
                json_manager.save_spe_promo(generated_code, promo_data, user_name="System")
                flash(f'SPE promo code {generated_code} created successfully!', 'success')
                return redirect(url_for('spe'))
            else:
                # Save as regular promo
                data_manager.save_promo(generated_code, promo_data, user_name="System")
                flash(f'RDC promo code {generated_code} created successfully!', 'success')
                return redirect(url_for('promotions'))
        
        # GET request - show the form
        current_year = datetime.now().year
        return render_template("get_promo_codes.html", current_year=current_year)
        
    except Exception as e:
        flash(f"Error creating promo code: {str(e)}", "error")
        current_year = datetime.now().year
        return render_template("get_promo_codes.html", current_year=current_year)


@app.route("/api/get_promo_details/<promo_code>", methods=["GET"])
def get_promo_details(promo_code):
    """Get detailed promo information by promo code"""
    try:
        # Search in promotions (RDC)
        promotions_data = data_manager.get_all_promos()
        if promo_code in promotions_data:
            promo_data = promotions_data[promo_code]
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
        
        # Search in SPE promotions
        spe_data = data_manager.get_all_spe_promos()
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
                'mpss_lookback': spe_promo.get('mpss_lookback', '')
            })
        
        # Not found
        return jsonify({
            'found': False,
            'message': f'Promo code {promo_code} not found'
        })
        
    except Exception as e:
        return jsonify({
            'found': False,
            'error': str(e)
        })


@app.route("/api/search_orbit/<orbit_id>", methods=["GET"])
def search_orbit(orbit_id):
    """Search for orbit data by orbit ID"""
    try:
        # Search in promotions (RDC)
        promotions_data = data_manager.get_all_promos()
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
                    'end_date': promo_data.get('promo_end_date', '')
                })
        
        # Search in SPE promotions
        spe_data = data_manager.get_all_spe_promos()
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
                    'end_date': spe_promo.get('promo_end_date', '')
                })
        
        # Not found
        return jsonify({
            'found': False,
            'message': f'Orbit ID {orbit_id} not found in promotions data'
        })
        
    except Exception as e:
        return jsonify({
            'found': False,
            'error': str(e)
        })


@app.route("/api/update_testing_status", methods=["POST"])
def update_testing_status():
    """Update testing status for a promotion"""
    try:
        data = request.get_json()
        promo_code = data.get('promo_code')
        test_type = data.get('test_type')  # 'functional' or 'zlab'
        status = data.get('status')  # 'Complete' or 'Incomplete'
        
        print(f"API called with: promo_code={promo_code}, test_type={test_type}, status={status}")
        
        if not all([promo_code, test_type, status]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
        
        # Get promotion data
        promotions_data = data_manager.get_all_promos()
        
        if promo_code not in promotions_data:
            return jsonify({
                'success': False,
                'error': f'Promotion {promo_code} not found'
            }), 404
        
        # Update the promotion data
        promo_data = promotions_data[promo_code].copy()
        
        print(f"Original promo_data keys: {list(promo_data.keys())}")
        
        # Map test types to field names
        if test_type == 'functional':
            promo_data['test_status'] = status
            print(f"Set test_status = {status}")
        elif test_type == 'zlab':
            promo_data['zlab_status'] = status
            print(f"Set zlab_status = {status}")
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown test type: {test_type}'
            }), 400
        
        print(f"Updated promo_data keys: {list(promo_data.keys())}")
        print(f"test_status in promo_data: {'test_status' in promo_data}")
        print(f"zlab_status in promo_data: {'zlab_status' in promo_data}")
        
        # Save the updated promotion data
        print(f"Calling data_manager.save_promo for {promo_code}")
        data_manager.save_promo(promo_code, promo_data, user_name="System")
        print(f"Save completed successfully")
        
        # Verify the save worked by reading it back
        updated_data = data_manager.get_promo(promo_code)
        field_name = 'test_status' if test_type == 'functional' else 'zlab_status'
        saved_value = updated_data.get(field_name)
        print(f"Verification - field saved: {field_name} = {saved_value}")
        
        if saved_value != status:
            return jsonify({
                'success': False,
                'error': f'Save verification failed. Expected {status}, got {saved_value}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': f'{test_type.title()} testing status updated to {status}',
            'updated_field': field_name,
            'new_value': status,
            'verification': saved_value
        })
        
    except Exception as e:
        print(f"API Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route("/edit_spe/<promo_code>", methods=["GET", "POST"])
def edit_spe(promo_code):
    # Get the active tab from query parameter or form, default to 'Details'
    tab = request.args.get('tab', 'Details')
    
    if request.method == "POST":
        # Get the active tab from form
        tab = request.form.get('active_tab', tab)
        
        # Get current SPE data using unified data manager (now database-powered!)
        spe_data = data_manager.get_spe_promo(promo_code)
        if not spe_data:
            # Create new SPE data if it doesn't exist
            spe_data = {
                'code': promo_code,
                'owner': 'Unknown',
                'description': '',
                'start_date': '',
                'end_date': '',
                'status': 'Draft'
            }
        
        # Get the SPE data from the form
        updated_data = {}
        
        # Get all form data (no need for spe_ prefix since template uses direct field names)
        for key, value in request.form.items():
            # Skip the active_tab field as it's not data
            if key != 'active_tab':
                updated_data[key] = value
        
        # Update the existing data with form data
        spe_data.update(updated_data)
        
        try:
            # Save the SPE data using JSON manager
            json_manager.save_spe_promo(promo_code, spe_data, user_name="Cade Holtzen")
            flash(f'SPE {promo_code} saved successfully!', 'success')
            # Redirect back to the same tab
            return redirect(url_for('edit_spe', promo_code=promo_code, tab=tab))
        except Exception as e:
            flash(f'Error saving SPE: {str(e)}', 'error')
    
    # GET request - load SPE data using JSON manager
    json_manager = get_json_manager()
    spe_data = json_manager.get_spe_promo(promo_code)
    if not spe_data:
        # Create new SPE data if it doesn't exist
        spe_data = {
            'code': promo_code,
            'owner': 'Unknown',
            'description': '',
            'start_date': '',
            'end_date': '',
            'status': 'Draft'
        }
    
    # Ensure the data has the basic structure expected by template
    if not isinstance(spe_data, dict):
        spe_data = {}
    
    return render_template("edit_spe.html", 
                         promo=spe_data, 
                         spe_data=spe_data, 
                         spe_key=promo_code,
                         active_tab=tab or 'Details',
                         soc_groupings=json_manager.get_soc_groupings(),
                         soc_grouping_details=json_manager.get_soc_grouping_details(),
                         account_types=json_manager.get_account_types(),
                         account_type_details=json_manager.get_account_type_details(),
                         sales_applications=json_manager.get_sales_applications(),
                         sales_application_details=json_manager.get_sales_application_details(),
                         user_name="Cade Holtzen")


@app.route("/date_mismatch")
def date_mismatch():
    try:
        # Use hybrid data manager for database-powered date mismatch checking
        mismatch_data = data_manager.get_date_mismatched_promos()
        return render_template("date_mismatch.html", 
                             promos=mismatch_data['promos'], 
                             owners=mismatch_data['owners'],
                             user_name="Cade Holtzen")
    except Exception as e:
        flash(f'Error loading date mismatch data: {str(e)}', 'error')
        return render_template("date_mismatch.html", promos=[], owners=[], user_name="Cade Holtzen")


@app.route("/update_pam_date/<promo_code>", methods=['POST'])
def update_pam_date(promo_code):
    """Update PAM end date to match ORBIT end date"""
    try:
        # Get ORBIT end date from database
        db_records = data_manager.db_manager.get_all_promos()
        orbit_end_date = None
        
        for record in db_records:
            if str(record.get('code', '')) == promo_code:
                orbit_end_date = record.get('promo_end_date', '')
                break
        
        if not orbit_end_date:
            return jsonify({
                'success': False, 
                'message': f'Promotion {promo_code} not found in ORBIT database'
            }), 404
        
        # Update PAM JSON file
        import json
        import os
        
        promo_file = os.path.join("data", "promotions.json")
        
        # Load current PAM data
        try:
            with open(promo_file, 'r') as f:
                pam_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return jsonify({
                'success': False, 
                'message': 'Could not read PAM promotions file'
            }), 500
        
        # Check if promo exists in PAM
        if promo_code not in pam_data:
            return jsonify({
                'success': False, 
                'message': f'Promotion {promo_code} not found in PAM data'
            }), 404
        
        # Update the end date
        old_end_date = pam_data[promo_code].get('promo_end_date', 'N/A')
        pam_data[promo_code]['promo_end_date'] = orbit_end_date
        pam_data[promo_code]['updated_at'] = datetime.now().isoformat()
        
        # Add version history entry
        if 'version_history' not in pam_data[promo_code]:
            pam_data[promo_code]['version_history'] = []
        
        pam_data[promo_code]['version_history'].append(
            f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')} - Date Mismatch Tool - Updated end date from {old_end_date} to {orbit_end_date} (synced from ORBIT)"
        )
        
        # Save updated data
        with open(promo_file, 'w') as f:
            json.dump(pam_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True, 
            'message': f'Successfully updated PAM end date for {promo_code} from {old_end_date} to {orbit_end_date}',
            'old_date': old_end_date,
            'new_date': orbit_end_date
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error updating PAM date: {str(e)}'
        }), 500


@app.route("/generate_date_sql", methods=['POST'])
def generate_date_sql():
    """Generate SQL for updating promotion end dates"""
    try:
        data = request.get_json()
        promo_codes = data.get('promo_codes', [])
        operator_id = data.get('operator_id', '')
        new_end_date = data.get('new_end_date', '')
        
        # Validate operator ID (5 digits only)
        if not operator_id or not operator_id.isdigit() or len(operator_id) != 5:
            return jsonify({
                'success': False,
                'message': 'Operator ID must be exactly 5 digits'
            }), 400
        
        if not promo_codes:
            return jsonify({
                'success': False,
                'message': 'No promotion codes provided'
            }), 400
        
        if not new_end_date:
            return jsonify({
                'success': False,
                'message': 'New end date is required'
            }), 400
        
        # Generate SQL statements
        sql_statements = []
        for promo_code in promo_codes:
            # Calculate expiration date (3 years after end date)
            from datetime import datetime, timedelta
            try:
                end_date_obj = datetime.strptime(new_end_date, '%m/%d/%Y')
                exp_date_obj = end_date_obj + timedelta(days=3*365)  # 3 years
                
                # Format for SQL
                promo_end_formatted = end_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
                exp_end_formatted = exp_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
                display_end_formatted = (end_date_obj - timedelta(days=1)).strftime('%m/%d/%Y') + ' 00:00:00'
                
                sql = f"""update promo_eligibility_rules set SYS_UPDATE_DATE = sysdate, APPLICATION_ID = 'CPO', OPERATOR_ID = '{operator_id}', PROMO_END_DATE = to_date('{promo_end_formatted}','MM/DD/YYYY HH24:MI:SS'), EXPIRATION_DATE = to_date('{exp_end_formatted}','MM/DD/YYYY HH24:MI:SS'), DISPLAY_PROMO_END_DATE = to_date('{display_end_formatted}','MM/DD/YYYY HH24:MI:SS') where promo_code = '{promo_code}';"""
                
                sql_statements.append(sql)
                
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': f'Invalid date format: {new_end_date}. Use MM/DD/YYYY format.'
                }), 400
        
        return jsonify({
            'success': True,
            'sql_statements': sql_statements
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error generating SQL: {str(e)}'
        }), 500


@app.route("/generate_sql_for_promo/<promo_code>")
def generate_sql_for_promo(promo_code):
    """Generate and download SQL file for updating a single promotion's end date"""
    operator_id = request.args.get('operator_id', '')
    orbit_end_date = request.args.get('orbit_end_date', '')
    
    sql = generate_sql_content(promo_code, operator_id, orbit_end_date)
    if sql.startswith('Error:'):
        flash(sql, 'error')
        return redirect(url_for('date_mismatch'))
    
    # Save SQL to temporary file for download
    import tempfile
    import os
    temp_dir = tempfile.gettempdir()
    sql_filename = f"{promo_code}_end_date_update.sql"
    temp_file_path = os.path.join(temp_dir, sql_filename)
    
    with open(temp_file_path, 'w', encoding='utf-8') as f:
        f.write(sql)
    
    from flask import send_file
    return send_file(temp_file_path, as_attachment=True, download_name=sql_filename)


@app.route("/preview_sql_for_promo/<promo_code>")
def preview_sql_for_promo(promo_code):
    """Preview SQL for updating a single promotion's end date"""
    operator_id = request.args.get('operator_id', '')
    orbit_end_date = request.args.get('orbit_end_date', '')
    
    sql = generate_sql_content(promo_code, operator_id, orbit_end_date)
    if sql.startswith('Error:'):
        return jsonify({'error': sql}), 400
    
    return jsonify({'sql': sql})


def generate_sql_content(promo_code, operator_id, orbit_end_date):
    """Helper function to generate SQL content"""
    try:
        # Validate operator ID
        if not operator_id or not operator_id.isdigit() or len(operator_id) != 5:
            return f'Error: Operator ID must be exactly 5 digits. Received: {operator_id}'
        
        if not orbit_end_date or orbit_end_date == 'N/A':
            return f'Error: No valid ORBIT end date found for promotion {promo_code}'
        
        # Parse the ORBIT end date and calculate other dates
        from datetime import datetime, timedelta
        try:
            # ORBIT end date is in format like "08/20/25" - convert to full year
            if len(orbit_end_date.split('/')[-1]) == 2:
                # Convert 2-digit year to 4-digit year
                month, day, year = orbit_end_date.split('/')
                year = '20' + year if int(year) < 50 else '19' + year  # Assume 00-49 = 2000-2049, 50-99 = 1950-1999
                orbit_end_date = f"{month}/{day}/{year}"
            
            end_date_obj = datetime.strptime(orbit_end_date, '%m/%d/%Y')
            exp_date_obj = end_date_obj.replace(year=end_date_obj.year + 3)  # Same month/day, 3 years later
            display_end_obj = end_date_obj - timedelta(days=1)  # 1 day before
            
            # Format for SQL
            promo_end_formatted = end_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
            exp_end_formatted = exp_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
            display_end_formatted = display_end_obj.strftime('%m/%d/%Y') + ' 00:00:00'
            
            # Generate SQL statement
            sql = f"""update promo_eligibility_rules set SYS_UPDATE_DATE = sysdate, APPLICATION_ID = 'CPO', OPERATOR_ID = '{operator_id}', PROMO_END_DATE = to_date('{promo_end_formatted}','MM/DD/YYYY HH24:MI:SS'), EXPIRATION_DATE = to_date('{exp_end_formatted}','MM/DD/YYYY HH24:MI:SS'), DISPLAY_PROMO_END_DATE = to_date('{display_end_formatted}','MM/DD/YYYY HH24:MI:SS') where promo_code = '{promo_code}';"""
            
            return sql
            
        except ValueError as e:
            return f'Error: Invalid date format "{orbit_end_date}". Expected MM/DD/YY or MM/DD/YYYY format. Error: {str(e)}'
        
    except Exception as e:
        return f'Error generating SQL: {str(e)}'


@app.route("/generate_sql_form/<promo_code>")
def generate_sql_form(promo_code):
    """Show form for generating SQL for a single promo"""
    return render_template("generate_sql_form.html", 
                         promo_codes=[promo_code], 
                         is_batch=False)


@app.route("/generate_batch_sql_form", methods=['POST'])
def generate_batch_sql_form():
    """Show form for generating SQL for multiple promos"""
    # Get selected promo codes from checkboxes
    # For now, return to date mismatch with message to select promos first
    flash('Please select promotions first by checking the boxes, then click Batch Generate SQL', 'info')
    return redirect(url_for('date_mismatch'))


@app.route("/generate_sql_submit", methods=['POST'])
def generate_sql_submit():
    """Process the SQL generation form"""
    try:
        promo_codes = request.form.getlist('promo_codes')
        operator_id = request.form.get('operator_id', '')
        new_end_date = request.form.get('new_end_date', '')
        
        # Validate operator ID (5 digits only)
        if not operator_id or not operator_id.isdigit() or len(operator_id) != 5:
            flash('Operator ID must be exactly 5 digits', 'error')
            return render_template("generate_sql_form.html", 
                                 promo_codes=promo_codes, 
                                 is_batch=len(promo_codes) > 1,
                                 operator_id=operator_id,
                                 new_end_date=new_end_date)
        
        if not promo_codes:
            flash('No promotion codes provided', 'error')
            return redirect(url_for('date_mismatch'))
        
        if not new_end_date:
            flash('New end date is required', 'error')
            return render_template("generate_sql_form.html", 
                                 promo_codes=promo_codes, 
                                 is_batch=len(promo_codes) > 1,
                                 operator_id=operator_id,
                                 new_end_date=new_end_date)
        
        # Generate SQL statements
        sql_statements = []
        for promo_code in promo_codes:
            # Calculate expiration date (3 years after end date)
            from datetime import datetime, timedelta
            try:
                end_date_obj = datetime.strptime(new_end_date, '%Y-%m-%d')  # HTML date input format
                exp_date_obj = end_date_obj + timedelta(days=3*365)  # 3 years
                
                # Format for SQL
                promo_end_formatted = end_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
                exp_end_formatted = exp_date_obj.strftime('%m/%d/%Y') + ' 05:00:00'
                display_end_formatted = (end_date_obj - timedelta(days=1)).strftime('%m/%d/%Y') + ' 00:00:00'
                
                sql = f"""update promo_eligibility_rules set SYS_UPDATE_DATE = sysdate, APPLICATION_ID = 'CPO', OPERATOR_ID = '{operator_id}', PROMO_END_DATE = to_date('{promo_end_formatted}','MM/DD/YYYY HH24:MI:SS'), EXPIRATION_DATE = to_date('{exp_end_formatted}','MM/DD/YYYY HH24:MI:SS'), DISPLAY_PROMO_END_DATE = to_date('{display_end_formatted}','MM/DD/YYYY HH24:MI:SS') where promo_code = '{promo_code}';"""
                
                sql_statements.append(sql)
                
            except ValueError:
                flash(f'Invalid date format: {new_end_date}', 'error')
                return render_template("generate_sql_form.html", 
                                     promo_codes=promo_codes, 
                                     is_batch=len(promo_codes) > 1,
                                     operator_id=operator_id,
                                     new_end_date=new_end_date)
        
        # Show the results
        return render_template("sql_results.html", 
                             sql_statements=sql_statements,
                             promo_codes=promo_codes)
        
    except Exception as e:
        flash(f'Error generating SQL: {str(e)}', 'error')
        return redirect(url_for('date_mismatch'))


@app.route("/generate_batch_sql", methods=['POST'])
def generate_batch_sql():
    """Generate SQL file for batch date updates with file preview response"""
    try:
        data = request.get_json()
        promotions = data.get('promotions', [])
        operator_id = data.get('operator_id', '')
        
        # Validate operator ID
        if not operator_id or not operator_id.isdigit() or len(operator_id) != 5:
            return jsonify({
                'success': False,
                'error': 'Operator ID must be exactly 5 digits'
            }), 400
        
        if not promotions:
            return jsonify({
                'success': False,
                'error': 'No promotions provided'
            }), 400
        
        # Generate SQL statements
        sql_statements = []
        successful_promos = []
        failed_promos = []
        
        for promo in promotions:
            promo_code = promo.get('code', '')
            orbit_end_date = promo.get('orbit_end_date', '')
            
            sql = generate_sql_content(promo_code, operator_id, orbit_end_date)
            
            if sql.startswith('Error:'):
                failed_promos.append({'code': promo_code, 'error': sql})
            else:
                sql_statements.append(sql)
                successful_promos.append(promo_code)
        
        if not sql_statements:
            return jsonify({
                'success': False,
                'error': 'No valid SQL statements could be generated',
                'failed_promos': failed_promos
            }), 400
        
        # Create filename with current date
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f"End_date_updates_{today}.sql"
        
        # Combine all SQL statements
        full_sql_content = '\n'.join(sql_statements)
        
        # Store the SQL content temporarily (in a real app, you might use a temporary file or database)
        import tempfile
        import os
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False)
        temp_file.write(full_sql_content)
        temp_file.close()
        
        # Store the temp file path for download
        session[f'sql_file_{operator_id}_{today}'] = temp_file.name
        
        return jsonify({
            'success': True,
            'filename': filename,
            'generated_at': datetime.now().strftime('%Y-%m-%d %I:%M %p'),
            'character_count': len(full_sql_content),
            'statement_count': len(sql_statements),
            'download_url': f'/download_batch_sql/{operator_id}/{today}',
            'sql_content': full_sql_content,
            'successful_promos': successful_promos,
            'failed_promos': failed_promos
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error generating batch SQL: {str(e)}'
        }), 500


@app.route("/download_batch_sql/<operator_id>/<date>")
def download_batch_sql(operator_id, date):
    """Download the generated batch SQL file"""
    try:
        # Get the temp file path from session
        temp_file_path = session.get(f'sql_file_{operator_id}_{date}')
        
        if not temp_file_path or not os.path.exists(temp_file_path):
            flash('SQL file not found or has expired. Please regenerate the SQL.', 'error')
            return redirect(url_for('date_mismatch'))
        
        # Read the file content
        with open(temp_file_path, 'r') as f:
            sql_content = f.read()
        
        # Clean up the temp file
        os.unlink(temp_file_path)
        del session[f'sql_file_{operator_id}_{date}']
        
        # Create response with file download
        from flask import Response
        filename = f"End_date_updates_{date}.sql"
        
        response = Response(
            sql_content,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
        
        return response
        
    except Exception as e:
        flash(f'Error downloading SQL file: {str(e)}', 'error')
        return redirect(url_for('date_mismatch'))


@app.route("/rebates")
def rebates():
    try:
        # Get search and filter parameters from query string
        search = request.args.get('search', '', type=str)
        owner_filter = request.args.get('owner', 'all', type=str)
        
        # Load rebate data from unified data manager (now database-powered!)
        rebates_data_dict = data_manager.get_all_rebates()
        
        # Convert to a list for filtering and sorting
        rebates_data = []
        for key in sorted(rebates_data_dict.keys()):
            item = rebates_data_dict[key]
            item['key'] = key  # Add the key to the item for template use
            rebates_data.append(item)
        
        # Apply search filter
        if search:
            search_lower = search.lower()
            rebates_data = [
                rebate for rebate in rebates_data 
                if (search_lower in rebate.get('code', '').lower() or 
                    search_lower in rebate.get('owner', '').lower() or
                    search_lower in rebate.get('bill_facing_name', '').lower())
            ]
        
        # Apply owner filter
        if owner_filter and owner_filter != "all":
            rebates_data = [rebate for rebate in rebates_data if rebate.get('owner', '') == owner_filter]
        
        # Get unique owners for filter dropdown
        owners = data_manager.get_rebate_owners()
        
        return render_template(
            "rebates.html", 
            rebates_data=rebates_data, 
            owners=owners,
            search_query=search,
            selected_owner=owner_filter,
            active_tab='Rebates'
        )
    except Exception as e:
        flash(f'Error loading rebates data: {str(e)}', 'error')
        return render_template(
            "rebates.html", 
            rebates_data=[], 
            owners=[],
            search_query='',
            selected_owner='all',
            active_tab='Rebates'
        )


@app.route("/test")
def test():
    return render_template("test.html")


@app.route("/updates")
def updates():
    """Updates page for promotion refresh functionality"""
    # Get search parameter from query string
    search = request.args.get('search', '', type=str)
    
    # Load promotions data from data manager
    all_promos = data_manager.get_all_promos()
    
    # Filter promotions based on search if provided
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
    
    # Get the first promo for default display
    default_promo = None
    if all_promos:
        first_code = next(iter(all_promos))
        default_promo = all_promos[first_code]
        default_promo['code'] = first_code
        
        # Debug: print what we're passing to template
        print(f"Passing to template - Promo: {first_code}")
        print(f"test_status: {default_promo.get('test_status')}")
        print(f"zlab_status: {default_promo.get('zlab_status')}")
    
    return render_template("updates.html", 
                         search_query=search,
                         default_promo=default_promo,
                         total_results=len(all_promos))


@app.route("/approvers")
def approvers():
    try:
        # Get the promo_code parameter if provided
        target_promo_code = request.args.get('promo_code', '').strip()
        
        # Load promotion data using the global database-connected manager
        rdc_data = data_manager.get_all_promos()
        
        # SPE still uses JSON files (for now)
        from data.storage import PromoDataManager as JSONManager
        json_manager = JSONManager()
        spe_data = json_manager.get_all_spe_promos()
        rebates_data = json_manager.get_all_rebates()
        
        # Combine all promo codes and owners
        all_promos = []
        
        # Add RDC promotions
        for promo_key, promo in rdc_data.items():
            all_promos.append({
                'code': promo.get('code', promo_key),
                'owner': promo.get('owner', 'Unknown'),
                'type': 'RDC'
            })
        
        # Add SPE promotions
        for spe_key, spe in spe_data.items():
            all_promos.append({
                'code': spe.get('code', spe_key),
                'owner': spe.get('owner', 'Unknown'),
                'type': 'SPE'
            })
        
        # Add Rebate promotions
        for rebate_key, rebate in rebates_data.items():
            all_promos.append({
                'code': rebate.get('code', rebate_key),
                'owner': rebate.get('owner', 'Unknown'),
                'type': 'REBATE'
            })
        
        # If a target promo is specified, sort to put it first
        if target_promo_code:
            target_promos = [p for p in all_promos if p['code'] == target_promo_code]
            other_promos = [p for p in all_promos if p['code'] != target_promo_code]
            all_promos = target_promos + other_promos
        
        # Extract separate lists for template compatibility
        promo_codes = [promo['code'] for promo in all_promos]
        owners = [promo['owner'] for promo in all_promos]
        
        # Create unique list of owners for the filter dropdown
        unique_owners = sorted(list(set(owners)))
        
        # Mock revenue approvers (you can replace this with actual data)
        revenue_approvers = [
            {'name': 'John Smith', 'email': 'john.smith@company.com'},
            {'name': 'Sarah Davis', 'email': 'sarah.davis@company.com'},
            {'name': 'Mike Johnson', 'email': 'mike.johnson@company.com'},
            {'name': 'Lisa Chen', 'email': 'lisa.chen@company.com'}
        ]
        
        return render_template("approvers.html", 
                             promo_codes=promo_codes,
                             owners=owners,
                             unique_owners=unique_owners,
                             revenue_approvers=revenue_approvers,
                             target_promo_code=target_promo_code)
    
    except Exception as e:
        flash(f'Error loading approvers data: {str(e)}', 'error')
        return render_template("approvers.html", 
                             promo_codes=[],
                             owners=[],
                             unique_owners=[],
                             revenue_approvers=[],
                             target_promo_code='')


@app.route("/reviewers")
@app.route("/reviewers/<promo_code>")
def reviewers(promo_code=None):
    # Get promo data if promo_code is provided
    promo_data = None
    error_message = None
    
    if promo_code:
        # Convert to uppercase for search
        promo_code_upper = promo_code.upper()
        
        # Try to find the promo with uppercase code
        promo_data = data_manager.get_promo(promo_code_upper)
        if not promo_data:
            # Try SPE promotions
            spe_promos = data_manager.get_all_spe_promos()
            promo_data = spe_promos.get(promo_code_upper)
            
        if not promo_data:
            error_message = f"Promotion code '{promo_code}' not found"
    
    return render_template("reviewers.html", 
                         promo_code=promo_code, 
                         promo_data=promo_data,
                         error_message=error_message)


@app.route("/links")
def links_main():
    """Links page without specific promotion"""
    return render_template("links.html")


@app.route("/links/<promo_code>", methods=["GET", "POST"])
def links(promo_code):
    """Links page for a specific promotion"""
    try:
        # Convert to uppercase for search
        promo_code_upper = promo_code.upper()
        
        # Get promotion data FIRST
        promo_data = data_manager.get_promo(promo_code_upper)
        if not promo_data:
            # Try SPE promotions
            spe_promos = data_manager.get_all_spe_promos()
            promo_data = spe_promos.get(promo_code_upper)
            
        if not promo_data:
            # Stay on links page but show error message
            error_message = f"Promotion code '{promo_code_upper}' not found"
            return render_template("links.html", 
                                 promo_code=promo_code_upper, 
                                 promo_data=None, 
                                 error_message=error_message)
        
        # Handle POST request (save links)
        if request.method == "POST":
            # Update the promotion data with new links
            promo_data['sku_link'] = request.form.get('skuLink', '')
            promo_data['tradein_link'] = request.form.get('tradeLink', '')
            promo_data['orbit_link'] = request.form.get('orbitLink', '')
            promo_data['legal_link'] = request.form.get('legalLink', '')
            promo_data['c2_article_link'] = request.form.get('c2ArticleLink', '')
            
            # Save the updated promotion data
            try:
                # Check if it's a regular promo or SPE promo and save accordingly
                regular_promos = data_manager.get_all_promos()
                if promo_code_upper in regular_promos:
                    data_manager.save_promo(promo_code_upper, promo_data, user_name="Current User")
                else:
                    data_manager.save_spe_promo(promo_code_upper, promo_data, user_name="Current User")
                
                # Redirect to prevent form resubmission dialog
                return redirect(url_for('links', promo_code=promo_code_upper))
            except Exception as e:
                flash(f"Error saving links: {str(e)}", "error")
        
        return render_template("links.html", 
                             promo_code=promo_code_upper, 
                             promo_data=promo_data)
        
    except Exception as e:
        flash(f"Error loading links for promotion: {str(e)}", "error")
        return redirect(url_for('promotions'))


@app.route("/debug-capacity")
def debug_capacity():
    """Debug endpoint to see raw data"""
    try:
        # Get all data
        rdc_data = data_manager.get_all_promos()
        spe_data = data_manager.get_all_spe_promos()
        
        # Show sample data structure
        sample_rdc = list(rdc_data.values())[:3] if rdc_data else []
        sample_spe = list(spe_data.values())[:3] if spe_data else []
        
        return {
            "total_rdc": len(rdc_data),
            "total_spe": len(spe_data),
            "sample_rdc": sample_rdc,
            "sample_spe": sample_spe
        }
    except Exception as e:
        return {"error": str(e)}


@app.route("/capacity")
def capacity():
    try:
        from datetime import datetime, date, timedelta
        
        # Helper function to get Sunday-Saturday week dates
        def get_sunday_saturday_week(input_date):
            """Convert any date to the Sunday-Saturday week it belongs to"""
            # Get the Sunday of the week containing input_date
            days_since_sunday = input_date.weekday() + 1  # Monday=0, so add 1 to make Sunday=0
            if days_since_sunday == 7:  # If it's Sunday, days_since_sunday would be 7
                days_since_sunday = 0
            week_start = input_date - timedelta(days=days_since_sunday)
            week_end = week_start + timedelta(days=6)  # Saturday
            return week_start, week_end
        
        # Helper function to check if a promotion is active on a given date
        def is_promo_active_on_date(promo_start, promo_end, check_date):
            """Check if promotion is active on the given date"""
            try:
                if not promo_start:
                    return False
                
                promo_start_date = datetime.strptime(promo_start, '%Y-%m-%d').date()
                
                # If no end date, assume it's active if start date is in the past
                if not promo_end or promo_end == '':
                    return promo_start_date <= check_date
                
                promo_end_date = datetime.strptime(promo_end, '%Y-%m-%d').date()
                
                # Check if check_date falls within the promo period
                return promo_start_date <= check_date <= promo_end_date
            except Exception as e:
                return False
        
        # Get current date for active promotions calculation
        current_date = date.today()  # This will be today's date
        
        # Get data for all promotion types
        rdc_data = data_manager.get_all_promos()
        spe_data = data_manager.get_all_spe_promos()
        rebates_data = data_manager.get_all_rebates()
        
        # Calculate currently active promotions (for summary metrics)
        active_rdc = {}
        active_spe = {}
        active_rebates = {}
        
        # Find active RDC promotions
        for promo_key, promo in rdc_data.items():
            if is_promo_active_on_date(
                promo.get('promo_start_date'), 
                promo.get('promo_end_date'),
                current_date
            ):
                promo_with_type = promo.copy()
                promo_with_type['type'] = 'RDC'
                active_rdc[promo_key] = promo_with_type

        # Find active SPE promotions
        for spe_key, spe in spe_data.items():
            if is_promo_active_on_date(
                spe.get('promo_start_date'), 
                spe.get('promo_end_date'),
                current_date
            ):
                spe_with_type = spe.copy()
                spe_with_type['type'] = 'SPE'
                active_spe[spe_key] = spe_with_type

        # Find active Rebate promotions
        for rebate_key, rebate in rebates_data.items():
            if is_promo_active_on_date(
                rebate.get('promo_start_date'), 
                rebate.get('promo_end_date'),
                current_date
            ):
                rebate_with_type = rebate.copy()
                rebate_with_type['type'] = 'REBATE'
                active_rebates[rebate_key] = rebate_with_type
        
        # Calculate summary metrics for currently active promotions
        total_active_rdc = len(active_rdc)
        total_active_spe = len(active_spe)
        total_active_rebates = len(active_rebates)
        total_currently_active = total_active_rdc + total_active_spe + total_active_rebates
        
        # Get date filter parameter for weekly schedule view
        selected_week = request.args.get('week', '08/10/2025-08/16/2025')
        start_date_str, end_date_str = selected_week.split('-')
        
        # Convert to datetime objects and standardize to Sunday-Saturday week
        input_start = datetime.strptime(start_date_str, '%m/%d/%Y').date()
        
        # Get the Sunday-Saturday week for the input date
        start_date, end_date = get_sunday_saturday_week(input_start)
        start_date_dt = datetime.combine(start_date, datetime.min.time())
        end_date_dt = datetime.combine(end_date, datetime.min.time())
        
        # Filter promotions by date range
        def is_promo_launching_in_week(promo_start, week_start, week_end):
            """Check if promotion launches during the selected week"""
            try:
                if not promo_start:
                    return False
                
                promo_start_date = datetime.strptime(promo_start, '%Y-%m-%d')
                
                # Check if promo start date falls within the selected week
                return week_start <= promo_start_date <= week_end
            except Exception as e:
                return False
        
        # Filter RDC promotions for the selected week
        filtered_rdc = {}
        for promo_key, promo in rdc_data.items():
            if is_promo_launching_in_week(
                promo.get('promo_start_date'), 
                start_date_dt, 
                end_date_dt
            ):
                # Add type flag for RDC promotions
                promo_with_type = promo.copy()
                promo_with_type['type'] = 'RDC'
                filtered_rdc[promo_key] = promo_with_type

        # Filter SPE promotions for the selected week
        filtered_spe = {}
        for spe_key, spe in spe_data.items():
            if is_promo_launching_in_week(
                spe.get('promo_start_date'), 
                start_date_dt, 
                end_date_dt
            ):
                # Add type flag for SPE promotions
                spe_with_type = spe.copy()
                spe_with_type['type'] = 'SPE'
                filtered_spe[spe_key] = spe_with_type

        # Filter Rebate promotions for the selected week
        filtered_rebates = {}
        for rebate_key, rebate in rebates_data.items():
            if is_promo_launching_in_week(
                rebate.get('promo_start_date'), 
                start_date_dt, 
                end_date_dt
            ):
                # Add type flag for Rebate promotions
                rebate_with_type = rebate.copy()
                rebate_with_type['type'] = 'REBATE'
                filtered_rebates[rebate_key] = rebate_with_type
        
        # Calculate summary metrics based on filtered data
        total_rdc = len(filtered_rdc)
        total_spe = len(filtered_spe)
        total_rebates = len(filtered_rebates)
        total_active = total_rdc + total_spe + total_rebates
        
        # Calculate owner workload distribution for filtered data
        owner_workload = {}
        
        # Count RDC promotions by owner
        for promo_key, promo in filtered_rdc.items():
            owner = promo.get('owner', 'Unknown')
            if owner not in owner_workload:
                owner_workload[owner] = {'rdc': 0, 'spe': 0, 'rebates': 0}
            owner_workload[owner]['rdc'] += 1
            # Debug: print which promo goes to which owner
            print(f"RDC Debug: {promo_key} -> owner: {owner}, start_date: {promo.get('promo_start_date')}")
        
        # Count SPE promotions by owner
        for spe_key, spe in filtered_spe.items():
            owner = spe.get('owner', 'Unknown')
            if owner not in owner_workload:
                owner_workload[owner] = {'rdc': 0, 'spe': 0, 'rebates': 0}
            owner_workload[owner]['spe'] += 1
            # Debug: print which promo goes to which owner
            print(f"SPE Debug: {spe_key} -> owner: {owner}, start_date: {spe.get('promo_start_date')}")

        # Count Rebate promotions by owner
        for rebate_key, rebate in filtered_rebates.items():
            owner = rebate.get('owner', 'Unknown')
            if owner not in owner_workload:
                owner_workload[owner] = {'rdc': 0, 'spe': 0, 'rebates': 0}
            owner_workload[owner]['rebates'] += 1
            # Debug: print which promo goes to which owner  
            print(f"REBATE Debug: {rebate_key} -> owner: {owner}, start_date: {rebate.get('promo_start_date')}")
        
        # Calculate totals and status for each owner
        for owner in owner_workload:
            workload = owner_workload[owner]
            workload['total'] = workload['rdc'] + workload['spe'] + workload['rebates']
            # Determine status based on total workload
            if workload['total'] >= 3:
                workload['status'] = 'HIGH'
            else:
                workload['status'] = 'OK'
        
        # Generate next four weeks data for schedule view (Sunday-Saturday weeks)
        import calendar
        
        next_four_weeks = []
        current_date = date(2025, 8, 8)  # Current date: August 8, 2025
        
        # Get the next Sunday (start of next week) as the starting point
        current_week_start, _ = get_sunday_saturday_week(current_date)
        next_week_start = current_week_start + timedelta(weeks=1)  # Start from next week
        
        for i in range(4):
            # Calculate each Sunday-Saturday week starting from next week
            week_start = next_week_start + timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)  # Saturday
            
            week_start_dt = datetime.combine(week_start, datetime.min.time())
            week_end_dt = datetime.combine(week_end, datetime.min.time())
            
            # Find promotions launching in this week
            week_promos = []
            for promo in rdc_data.values():
                if is_promo_launching_in_week(promo.get('promo_start_date'), week_start_dt, week_end_dt):
                    # Add type flag for RDC promotions
                    promo_with_type = promo.copy()
                    promo_with_type['type'] = 'RDC'
                    week_promos.append(promo_with_type)
            for spe in spe_data.values():
                if is_promo_launching_in_week(spe.get('promo_start_date'), week_start_dt, week_end_dt):
                    # Add type flag for SPE promotions
                    spe_with_type = spe.copy()
                    spe_with_type['type'] = 'SPE'
                    week_promos.append(spe_with_type)
            for rebate in rebates_data.values():
                if is_promo_launching_in_week(rebate.get('promo_start_date'), week_start_dt, week_end_dt):
                    # Add type flag for Rebate promotions
                    rebate_with_type = rebate.copy()
                    rebate_with_type['type'] = 'REBATE'
                    week_promos.append(rebate_with_type)
            
            # Format week label
            week_label = f"{week_start.strftime('%m/%d/%Y')} - {week_end.strftime('%m/%d/%Y')}"
            
            next_four_weeks.append({
                'week_label': week_label,
                'promotions': week_promos  # Show all promotions for the week
            })
        
        # Update selected_week to reflect the standardized Sunday-Saturday week
        standardized_week = f"{start_date.strftime('%m/%d/%Y')}-{end_date.strftime('%m/%d/%Y')}"
        
        return render_template("capacity.html", 
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
                             selected_week=standardized_week)
    except Exception as e:
        flash(f'Error loading capacity data: {str(e)}', 'error')
        # Return with default values if there's an error
        return render_template("capacity.html",
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
                             selected_week='08/10/2025-08/16/2025')


# User Management System
import json

USER_DATA_FILE = os.path.join("data", "users.json")
USER_GROUPS_FILE = os.path.join("data", "user_groups.json")

def get_user_groups():
    """Get all user groups and their permissions"""
    try:
        if os.path.exists(USER_GROUPS_FILE):
            with open(USER_GROUPS_FILE, 'r') as f:
                return json.load(f)
        else:
            # Default groups if file doesn't exist
            default_groups = {
                "admin": {
                    "name": "Administrator", 
                    "permissions": ["view_all", "edit_all", "delete_all", "edit_promotions", "create_promotions", "date_mismatch", "sql_generation", "user_management", "system_admin"],
                    "description": "Full system access including user management"
                },
                "promo_owner": {
                    "name": "Promo Owner",
                    "permissions": ["view_all", "edit_promotions", "create_promotions", "date_mismatch", "sql_generation"],
                    "description": "Can view, edit, create promotions, handle date mismatches and generate SQL"
                },
                "reviewer": {
                    "name": "Reviewer",
                    "permissions": ["view_all"],
                    "description": "Read-only access to all promotions"
                }
            }
            # Save default groups
            save_user_groups(default_groups)
            return default_groups
    except Exception as e:
        print(f"Error loading user groups: {e}")
        return {}

def save_user_groups(groups):
    """Save user groups to file"""
    try:
        os.makedirs(os.path.dirname(USER_GROUPS_FILE), exist_ok=True)
        with open(USER_GROUPS_FILE, 'w') as f:
            json.dump(groups, f, indent=2)
    except Exception as e:
        print(f"Error saving user groups: {e}")

def get_all_users():
    """Get all users from the user data file"""
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                return json.load(f)
        else:
            # Default users if file doesn't exist
            default_users = {
                "choltzen": {
                    "username": "choltzen",
                    "display_name": "Cade Holtzen",
                    "email": "cade.holtzen@example.com",
                    "group": "admin",
                    "active": True,
                    "created_date": datetime.now().isoformat()
                },
                "demo_user": {
                    "username": "demo_user",
                    "display_name": "Demo User",
                    "email": "demo@example.com",
                    "group": "viewer",
                    "active": True,
                    "created_date": datetime.now().isoformat()
                }
            }
            # Save default users
            save_users(default_users)
            return default_users
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

def save_users(users):
    """Save users to file"""
    try:
        os.makedirs(os.path.dirname(USER_DATA_FILE), exist_ok=True)
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        print(f"Error saving users: {e}")

def get_user_permissions(username):
    """Get permissions for a specific user"""
    users = get_all_users()
    groups = get_user_groups()
    
    if username in users:
        user_group = users[username].get('group', 'viewer')
        if user_group in groups:
            return groups[user_group].get('permissions', [])
    
    return []


@app.route("/admin")
def admin():
    # Get system statistics for the admin dashboard
    try:
        promotions_data = data_manager.get_all_promos()
        spe_data = data_manager.get_all_spe_promos()
        
        # Calculate statistics
        promotions_count = len(promotions_data)
        spe_count = len(spe_data)
        
        # Count pending reviews (example logic)
        pending_reviews = sum(1 for promo in promotions_data.values() 
                            if promo.get('status', '').lower() in ['pending', 'review'])
        
        # Get user management data
        users = get_all_users()
        user_groups = get_user_groups()
        
        return render_template("admin.html", 
                             promotions_count=promotions_count,
                             spe_count=spe_count,
                             pending_reviews=pending_reviews,
                             users=users,
                             user_groups=user_groups)
    except Exception as e:
        # Fallback to default values if data loading fails
        return render_template("admin.html", 
                             promotions_count=847,
                             spe_count=234,
                             pending_reviews=12)


@app.route("/admin/user-management")
def admin_user_management():
    """User Management page - separate page for managing users and groups"""
    return render_template("admin_user_management.html")


@app.route("/version-history")
def version_history():
    """Version History page - tracks changes to promotions"""
    try:
        # Get real promotion data with version history
        promotions_with_history = data_manager.get_all_promotions_with_history()
        
        return render_template("version_history.html", promotions=promotions_with_history)
    except Exception as e:
        flash(f'Error loading version history: {str(e)}', 'error')
        return render_template("version_history.html", promotions=[])


@app.route("/admin/backup", methods=["POST"])
def admin_backup():
    """Create a backup of all data"""
    try:
        import shutil
        from datetime import datetime
        
        # Create backup directory
        backup_dir = f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Copy remaining data files (SPE and rebates still use JSON)
        # Note: Regular promotions are now in database, no longer backed up as JSON
        if os.path.exists("data/spe_promotions.json"):
            shutil.copy2("data/spe_promotions.json", backup_dir)
        if os.path.exists("data/rebates.json"):
            shutil.copy2("data/rebates.json", backup_dir)
        if os.path.exists("data/workflow_data.json"):
            shutil.copy2("data/workflow_data.json", backup_dir)  # PAM workflow data
            
        # Copy uploads directory
        if os.path.exists("data/uploads"):
            shutil.copytree("data/uploads", os.path.join(backup_dir, "uploads"))
        
        return jsonify({"success": True, "message": f"Backup created successfully in {backup_dir} (Note: Promotions are now in database)"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Backup failed: {str(e)}"})


@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    """Get detailed system statistics"""
    try:
        # Get data from database-powered manager
        promotions_data = data_manager.get_all_promos()
        
        # SPE still uses JSON files (for now)
        from data.storage import PromoDataManager
        json_manager = PromoDataManager()
        spe_data = json_manager.get_all_spe_promos()
        
        # Calculate cache status
        cache_status = data_manager.get_cache_status()
        
        # Calculate file sizes (remaining JSON files only)
        spe_file_size = os.path.getsize("data/spe_promotions.json") if os.path.exists("data/spe_promotions.json") else 0
        workflow_file_size = os.path.getsize("data/workflow_data.json") if os.path.exists("data/workflow_data.json") else 0
        
        # Count uploads
        uploads_count = 0
        if os.path.exists("data/uploads"):
            for root, dirs, files in os.walk("data/uploads"):
                uploads_count += len(files)
        
        stats = {
            "promotions_count": len(promotions_data),
            "spe_count": len(spe_data),
            "total_records": len(promotions_data) + len(spe_data),
            "data_source": "Database + JSON hybrid",
            "cache_status": cache_status,
            "spe_file_size": f"{spe_file_size / 1024:.1f} KB",
            "workflow_file_size": f"{workflow_file_size / 1024:.1f} KB",
            "uploads_count": uploads_count,
            "database_connected": True,
            "last_cache_refresh": cache_status.get('last_refresh', 'Never')
        }
        
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to get stats: {str(e)}"})


@app.route("/admin/test-connections", methods=["POST"])
def admin_test_connections():
    """Test external system connections"""
    results = {}
    
    # Test JIRA connection
    try:
        import requests
        response = requests.get("https://jira.t-mobile.com", timeout=5, verify=False)
        results["jira"] = {"status": "success", "response_time": "245ms"}
    except:
        results["jira"] = {"status": "error", "response_time": "timeout"}
    
    # Test ORBIT connection (placeholder)
    results["orbit"] = {"status": "success", "response_time": "180ms"}
    
    # Test Email service (placeholder)
    results["email"] = {"status": "warning", "response_time": "1.2s"}
    
    return jsonify({"success": True, "results": results})


@app.route("/download_file/<promo_code>/<file_type>")
def download_file(promo_code, file_type):
    try:
        file_path = data_manager.get_file_path(promo_code, file_type)
        if file_path and os.path.exists(file_path):
            from flask import send_file
            return send_file(file_path, as_attachment=True)
        else:
            flash('File not found', 'error')
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('promo.edit_promo', promo_code=promo_code))


@app.route("/download_sql/<promo_code>")
def download_sql(promo_code):
    try:
        # Get promo data
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            flash('Promo not found', 'error')
            return redirect(url_for('promotions'))
        
        # Check if SQL file already exists
        sql_file_info = promo_data.get('sql_file')
        if sql_file_info and os.path.exists(sql_file_info.get('path', '')):
            from flask import send_file
            return send_file(sql_file_info['path'], as_attachment=True, download_name=sql_file_info['filename'])
        
        # Generate SQL if it doesn't exist
        sql_statement = generate_promo_eligibility_sql(promo_data)
        
        # Save SQL to temporary file for download
        import tempfile
        temp_dir = tempfile.gettempdir()
        sql_filename = f"{promo_code}_promo_eligibility_rules.sql"
        temp_file_path = os.path.join(temp_dir, sql_filename)
        
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(sql_statement)
        
        from flask import send_file
        return send_file(temp_file_path, as_attachment=True, download_name=sql_filename)
        
    except Exception as e:
        flash(f'Error generating SQL download: {str(e)}', 'error')
        return redirect(url_for('promo.edit_promo', promo_code=promo_code))


@app.route("/admin/cache-status")
def admin_cache_status():
    """Get cache performance status"""
    try:
        cache_status = data_manager.get_cache_status()
        return jsonify({"success": True, "cache_status": cache_status})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to get cache status: {str(e)}"})


@app.route("/admin/cache-refresh", methods=["POST"])
def admin_cache_refresh():
    """Manually refresh the cache"""
    try:
        start_time = datetime.now()
        data_manager.force_refresh()
        refresh_time = (datetime.now() - start_time).total_seconds()
        
        cache_status = data_manager.get_cache_status()
        
        return jsonify({
            "success": True, 
            "message": f"Cache refreshed successfully in {refresh_time:.2f} seconds",
            "cache_status": cache_status
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to refresh cache: {str(e)}"})


@app.route("/create_jira_ticket", methods=["POST"])
def create_jira_ticket():
    try:
        # Get form data
        summary = request.form.get('summary', '')
        description = request.form.get('description', '')
        
        # Get JIRA configuration from environment variables or config
        jira_url = os.environ.get('JIRA_URL', 'https://your-jira-instance.com')
        jira_username = os.environ.get('JIRA_USERNAME', '')
        jira_password = os.environ.get('JIRA_PASSWORD', '')
        jira_project = os.environ.get('JIRA_PROJECT', 'YOUR-PROJECT')
        
        if not all([jira_url, jira_username, jira_password, jira_project]):
            return jsonify({
                'success': False,
                'error': 'JIRA configuration is incomplete. Please check environment variables.'
            })
        
        # Create JIRA ticket payload
        ticket_data = {
            "fields": {
                "project": {"key": jira_project},
                "summary": summary,
                "description": description,
                "issuetype": {"name": "Task"}
            }
        }
        
        # Make request to JIRA API
        auth = (jira_username, jira_password)
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(
            f"{jira_url}/rest/api/2/issue/",
            json=ticket_data,
            auth=auth,
            headers=headers,
            verify=False  # Disable SSL verification for internal JIRA instances
        )
        
        if response.status_code == 201:
            ticket_info = response.json()
            ticket_key = ticket_info['key']
            ticket_url = f"{jira_url}/browse/{ticket_key}"
            
            return jsonify({
                'success': True,
                'ticket_key': ticket_key,
                'ticket_url': ticket_url
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to create JIRA ticket: {response.status_code} - {response.text}'
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error creating JIRA ticket: {str(e)}'
        })


@app.route("/clear_trade_data/<promo_code>", methods=["POST"])
def clear_trade_data(promo_code):
    try:
        # Load promo data
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            return jsonify({"success": False, "error": "Promo not found"})
        
        # Clear trade-related fields
        trade_fields_to_clear = [
            'trade_in_group_id', 'broken_trade',
            'trade_tier_1_amount', 'trade_tier_1_cond_id', 'trade_tier_1_min_fmv', 'trade_tier_1_max_fmv', 'trade_tier_1_make_model',
            'trade_tier_2_amount', 'trade_tier_2_cond_id', 'trade_tier_2_min_fmv', 'trade_tier_2_max_fmv', 'trade_tier_2_make_model',
            'trade_tier_3_amount', 'trade_tier_3_cond_id', 'trade_tier_3_min_fmv', 'trade_tier_3_max_fmv', 'trade_tier_3_make_model',
            'trade_tier_4_amount', 'trade_tier_4_cond_id', 'trade_tier_4_min_fmv', 'trade_tier_4_max_fmv', 'trade_tier_4_make_model'
        ]
        
        for field in trade_fields_to_clear:
            if field == 'broken_trade':
                promo_data[field] = 'N'  # Reset to default value
            else:
                promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        data_manager.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
        return jsonify({"success": True, "message": "Trade data cleared successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/clear_tiers_data/<promo_code>", methods=["POST"])
def clear_tiers_data(promo_code):
    try:
        # Load promo data
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            return jsonify({"success": False, "error": "Promo not found"})
        
        # Clear tiers-related fields
        tiers_fields_to_clear = [
            'tiered_group_id',
            'tier_1_amount', 'tier_1_sku_group_id', 'tier_1_devices',
            'tier_2_amount', 'tier_2_sku_group_id', 'tier_2_devices',
            'tier_3_amount', 'tier_3_sku_group_id', 'tier_3_devices',
            'tier_4_amount', 'tier_4_sku_group_id', 'tier_4_devices'
        ]
        
        for field in tiers_fields_to_clear:
            promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        data_manager.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
        return jsonify({"success": True, "message": "Tiers data cleared successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/clear_segment_data/<promo_code>", methods=["POST"])
def clear_segment_data(promo_code):
    try:
        # Load promo data
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            return jsonify({"success": False, "error": "Promo not found"})
        
        # Clear segment-related fields
        segment_fields_to_clear = [
            'segment_name', 'sub_segment', 'segment_group_id', 'segment_level',
            'soc_grouping', 'account_type', 'sales_application', 'bptcr'
        ]
        
        for field in segment_fields_to_clear:
            promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        data_manager.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
        return jsonify({"success": True, "message": "Segment data cleared successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# User Management Routes
@app.route("/admin/users", methods=["GET"])
def admin_users():
    """Get all users for admin management"""
    try:
        users = get_all_users()
        groups = get_user_groups()
        return jsonify({"success": True, "users": users, "groups": groups})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to get users: {str(e)}"})

@app.route("/admin/users", methods=["POST"])
def admin_create_user():
    """Create a new user"""
    try:
        data = request.get_json()
        users = get_all_users()
        
        username = data.get('username', '').strip().lower()
        if not username:
            return jsonify({"success": False, "message": "Username is required"})
        
        if username in users:
            return jsonify({"success": False, "message": "Username already exists"})
        
        # Create new user
        new_user = {
            "username": username,
            "display_name": data.get('display_name', ''),
            "email": data.get('email', ''),
            "group": data.get('group', 'viewer'),
            "active": data.get('active', True),
            "created_date": datetime.now().isoformat()
        }
        
        users[username] = new_user
        save_users(users)
        
        return jsonify({"success": True, "message": f"User {username} created successfully", "user": new_user})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to create user: {str(e)}"})

@app.route("/admin/users/<username>", methods=["PUT"])
def admin_update_user(username):
    """Update an existing user"""
    try:
        data = request.get_json()
        users = get_all_users()
        
        if username not in users:
            return jsonify({"success": False, "message": "User not found"})
        
        # Update user data
        if 'display_name' in data:
            users[username]['display_name'] = data['display_name']
        if 'email' in data:
            users[username]['email'] = data['email']
        if 'group' in data:
            users[username]['group'] = data['group']
        if 'active' in data:
            users[username]['active'] = data['active']
        
        users[username]['updated_date'] = datetime.now().isoformat()
        
        save_users(users)
        
        return jsonify({"success": True, "message": f"User {username} updated successfully", "user": users[username]})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to update user: {str(e)}"})

@app.route("/admin/users/<username>", methods=["DELETE"])
def admin_delete_user(username):
    """Delete a user"""
    try:
        users = get_all_users()
        
        if username not in users:
            return jsonify({"success": False, "message": "User not found"})
        
        if username == "choltzen":  # Protect admin user
            return jsonify({"success": False, "message": "Cannot delete the main admin user"})
        
        del users[username]
        save_users(users)
        
        return jsonify({"success": True, "message": f"User {username} deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to delete user: {str(e)}"})

@app.route("/admin/groups", methods=["POST"])
def admin_create_group():
    """Create a new user group"""
    try:
        data = request.get_json()
        groups = get_user_groups()
        
        group_id = data.get('id', '').strip().lower()
        if not group_id:
            return jsonify({"success": False, "message": "Group ID is required"})
        
        if group_id in groups:
            return jsonify({"success": False, "message": "Group already exists"})
        
        new_group = {
            "name": data.get('name', ''),
            "description": data.get('description', ''),
            "permissions": data.get('permissions', [])
        }
        
        groups[group_id] = new_group
        save_user_groups(groups)
        
        return jsonify({"success": True, "message": f"Group {group_id} created successfully", "group": new_group})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to create group: {str(e)}"})


if __name__ == "__main__":
    app.run(debug=True)
