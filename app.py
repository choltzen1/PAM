from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import requests
import urllib3
from datetime import datetime
from data.storage import PromoDataManager
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

# Initialize data manager
data_manager = PromoDataManager()

# Register blueprints
app.register_blueprint(promo_bp)


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
        # Load SPE data from data manager
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


@app.route("/edit_spe/<promo_code>", methods=["GET", "POST"])
def edit_spe(promo_code):
    # Get the active tab from query parameter or form, default to 'Details'
    tab = request.args.get('tab', 'Details')
    
    if request.method == "POST":
        # Get the active tab from form
        tab = request.form.get('active_tab', tab)
        
        # Get current SPE data
        spe_data = data_manager.get_spe_promo(promo_code)
        if not spe_data:
            flash(f"SPE {promo_code} not found", "error")
            return redirect(url_for('spe'))
        
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
            # Save the SPE data
            data_manager.save_spe_promo(promo_code, spe_data, user_name="Cade Holtzen")
            flash(f'SPE {promo_code} saved successfully!', 'success')
            # Redirect back to the same tab
            return redirect(url_for('edit_spe', promo_code=promo_code, tab=tab))
        except Exception as e:
            flash(f'Error saving SPE: {str(e)}', 'error')
    
    # GET request - load SPE data
    spe_data = data_manager.get_spe_promo(promo_code)
    if not spe_data:
        flash(f"SPE {promo_code} not found", "error")
        return redirect(url_for('spe'))
    
    # Ensure the data has the basic structure expected by template
    if not isinstance(spe_data, dict):
        spe_data = {}
    
    return render_template("edit_spe.html", 
                         promo=spe_data, 
                         spe_data=spe_data, 
                         spe_key=promo_code,
                         active_tab=tab or 'Details',
                         soc_groupings=data_manager.get_soc_groupings(),
                         soc_grouping_details=data_manager.get_soc_grouping_details(),
                         account_types=data_manager.get_account_types(),
                         account_type_details=data_manager.get_account_type_details(),
                         sales_applications=data_manager.get_sales_applications(),
                         sales_application_details=data_manager.get_sales_application_details(),
                         user_name="Cade Holtzen")


@app.route("/date_mismatch")
def date_mismatch():
    try:
        mismatch_data = data_manager.get_date_mismatched_promos()
        return render_template("date_mismatch.html", 
                             promos=mismatch_data['promos'], 
                             owners=mismatch_data['owners'],
                             user_name="Cade Holtzen")
    except Exception as e:
        flash(f'Error loading date mismatch data: {str(e)}', 'error')
        return render_template("date_mismatch.html", promos=[], owners=[], user_name="Cade Holtzen")


@app.route("/rebates")
def rebates():
    return render_template("rebates.html")


@app.route("/test")
def test():
    return render_template("test.html")


@app.route("/approvers")
def approvers():
    return render_template("approvers.html")


@app.route("/reviewers")
def reviewers():
    return render_template("reviewers.html")


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


@app.route("/admin")
def admin():
    return render_template("admin.html")


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


if __name__ == "__main__":
    app.run(debug=True)
