from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import requests
import urllib3
from datetime import datetime
from data.storage import PromoDataManager
from promo.builders import generate_promo_eligibility_sql
from promo.routes import promo_bp

# Pre-import pandas to avoid delays during SQL generation
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


@app.route("/edit_spe", methods=["GET", "POST"])
def edit_spe():
    if request.method == "POST":
        # Get the SPE data from the form
        spe_data = {}
        
        # Get all form data that starts with 'spe_'
        for key, value in request.form.items():
            if key.startswith('spe_'):
                # Remove the 'spe_' prefix to get the actual field name
                field_name = key[4:]
                spe_data[field_name] = value
        
        # Determine the key for this SPE (could be from existing or new)
        spe_key = request.form.get('spe_key', f"SPE_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        try:
            # Save the SPE data
            data_manager.save_spe(spe_key, spe_data)
            flash(f'SPE {spe_key} saved successfully!', 'success')
            return redirect(url_for('spe'))
        except Exception as e:
            flash(f'Error saving SPE: {str(e)}', 'error')
    
    # If it's a GET request or there was an error, show the form
    spe_key = request.args.get('spe_key')
    spe_data = {}
    
    if spe_key:
        try:
            all_spe = data_manager.get_all_spe()
            spe_data = all_spe.get(spe_key, {})
        except:
            pass
    
    return render_template("edit_spe.html", spe_data=spe_data, spe_key=spe_key)


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
