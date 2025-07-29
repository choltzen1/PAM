from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import requests
import urllib3
from datetime import datetime
from data.storage import PromoDataManager

# Disable SSL warnings for JIRA requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages

# Initialize data manager
data_manager = PromoDataManager()


def generate_promo_eligibility_sql(promo_data):
    """Generate PROMO_ELIGIBILITY_RULES INSERT statement from promo data"""
    
    # Helper function to safely get integer values
    def safe_get_int(data, key, default=None):
        try:
            value = data.get(key, default)
            if value == '' or value is None:
                return default
            return int(float(value)) if isinstance(value, str) and '.' in value else int(value)
        except (ValueError, TypeError):
            return default
    
    # Helper function to format values for SQL
    def fmt_sql_value(val):
        if val is None or val == '' or str(val).upper() == 'NULL':
            return 'NULL'
        if isinstance(val, str):
            if val.startswith('to_date('):
                return val
            # Escape single quotes and wrap in quotes
            return f"'{val.replace(chr(39), chr(39) + chr(39))}'"
        return str(val)    # Helper function to format dates
    def fmt_date(date_str, date_type='display'):
        """
        Format dates based on type:
        - 'display': Use exact date with 20:00:00 (for DISPLAY_PROMO_START_DATE, DISPLAY_PROMO_END_DATE)
        - 'start': Subtract one day and use 20:00:00 (for PROMO_START_DATE, EFFECTIVE_DATE)
        - 'end': Add one day and use 05:00:00 (for PROMO_END_DATE, EXPIRATION_DATE)
        """
        if not date_str:
            return 'NULL'
        
        from datetime import datetime, timedelta
        
        try:
            # Parse the date string (YYYY-MM-DD format)
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            
            if date_type == 'start':
                # For start dates: subtract one day and set time to 20:00:00
                date_obj = date_obj - timedelta(days=1)
                time_str = '20:00:00'
            elif date_type == 'end':
                # For end dates: add one day and set time to 05:00:00
                date_obj = date_obj + timedelta(days=1)
                time_str = '05:00:00'
            else:  # 'display' or default
                # For display dates: use exact date with 20:00:00
                time_str = '20:00:00'
            
            formatted_date = date_obj.strftime('%Y-%m-%d')
            return f"to_date('{formatted_date} {time_str}','YYYY-MM-DD HH24:MI:SS')"
        except ValueError:
            return 'NULL'
      # Map promo data to SQL fields
    sql_values = {        'promo_code': promo_data.get('code') if promo_data.get('code') else 'NULL',        'promo_start_date': fmt_date(promo_data.get('promo_start_date'), 'start'),
        'promo_end_date': fmt_date(promo_data.get('promo_end_date'), 'end'),
        'operator_id': promo_data.get('operator_id') if promo_data.get('operator_id') else 'NULL',
        'promo_description': promo_data.get('bill_facing_name') if promo_data.get('bill_facing_name') else 'NULL',
        'promo_duration': safe_get_int(promo_data, 'promo_duration') if promo_data.get('promo_duration') else 'NULL',
        'promo_amount': safe_get_int(promo_data, 'amount') if promo_data.get('amount') else 'NULL',        'effective_date': fmt_date(promo_data.get('promo_start_date'), 'start'),        'expiration_date': fmt_date(promo_data.get('promo_end_date'), 'end'),
        'sku_group_id': promo_data.get('sku_group_id') if promo_data.get('sku_group_id') else 'NULL',
        'prim_sku_group_id': 'NULL',  # Not used in current form
        'soc_group_id': promo_data.get('soc_grouping') if promo_data.get('soc_grouping') else 'NULL',
        'atst_group_id': promo_data.get('account_type') if promo_data.get('account_type') else 'NULL',
        'appl_group_id': promo_data.get('sales_application') if promo_data.get('sales_application') else 'NULL',
        'device_st_group_id': promo_data.get('device_sales_type') if promo_data.get('device_sales_type') else 'NULL',
        'finance_type': promo_data.get('finance_type') if promo_data.get('finance_type') else 'NULL',
        'act_line_req_ind': promo_data.get('maintain_soc') if promo_data.get('maintain_soc') else 'NULL',        'app_grace_group_id': promo_data.get('application_grace_period') if promo_data.get('application_grace_period') else 'NULL',
        'trade_in_grp_id': promo_data.get('trade_in_group_id') if promo_data.get('trade_in_group_id') else 'NULL',
        'trade_in_grace_period': promo_data.get('trade_in_grace') if promo_data.get('trade_in_grace') else 'NULL',
        'maint_act_line_chk_ind': promo_data.get('maintain_soc') if promo_data.get('maintain_soc') else 'NULL',
        'maint_soc_chk_ind': promo_data.get('maintain_soc') if promo_data.get('maintain_soc') else 'NULL',
        'store_grp_id': promo_data.get('store_group') if promo_data.get('store_group') else 'NULL',
        'market_grp_id': promo_data.get('market_group') if promo_data.get('market_group') else 'NULL',        'limit_per_ban': safe_get_int(promo_data, 'limit_per_ban') if promo_data.get('limit_per_ban') else 'NULL',
        'tenure_group_id': 'NULL',  # Not used in current form
        'portin_group_id': promo_data.get('port_in_group_id') if promo_data.get('port_in_group_id') else 'NULL',
        'promo_perc_disc': safe_get_int(promo_data, 'discount') if promo_data.get('discount') else 'NULL',
        'c2_link': f"https://c2.t-mobile.com/offers/{promo_data.get('bptcr', '')}" if promo_data.get('bptcr') else 'NULL',
        'min_gsm_count': safe_get_int(promo_data, 'min_gsm_count') if promo_data.get('min_gsm_count') else 'NULL',
        'max_gsm_count': safe_get_int(promo_data, 'max_gsm_count') if promo_data.get('max_gsm_count') else 'NULL',        'display_promo': promo_data.get('fpd_display_promo') if promo_data.get('fpd_display_promo') else 'NULL',
        'tiered_grp_id': 'NULL',  # Not used in current form
        'segment_grp_id': promo_data.get('segment_group_id') if promo_data.get('segment_group_id') else 'NULL',
        'bolton_trade_in_grp_id': promo_data.get('bolton_trade_in_grp_id') if promo_data.get('bolton_trade_in_grp_id') else 'NULL',
        'product_type': promo_data.get('product_type') if promo_data.get('product_type') else 'NULL',
        'pr_date': 'NULL',  # Set to NULL as requested
        'promo_grace_period': safe_get_int(promo_data, 'promo_grace') if promo_data.get('promo_grace') else 'NULL',
        'line_st_group_id': promo_data.get('activation_type') if promo_data.get('activation_type') else 'NULL',
        'nseip_drop_ind': promo_data.get('nseip_drop') if promo_data.get('nseip_drop') else 'NULL',        'delay_time': safe_get_int(promo_data, 'delay_time') if promo_data.get('delay_time') else 'NULL',        'display_promo_start_date': fmt_date(promo_data.get('promo_start_date'), 'display'),
        'display_promo_end_date': fmt_date(promo_data.get('promo_end_date'), 'display'),
        'mpss_lookback': safe_get_int(promo_data, 'mpss_lookback') if promo_data.get('mpss_lookback') else 'NULL',
        'flow_indicator': promo_data.get('flow_indicator') if promo_data.get('flow_indicator') else 'NULL',
        'document_id': promo_data.get('bptcr') if promo_data.get('bptcr') else 'NULL',
        'dvc_sts_grp_id': promo_data.get('device_status_group_id') if promo_data.get('device_status_group_id') else 'NULL',
        'clawback_ind': promo_data.get('clawback_indicator') if promo_data.get('clawback_indicator') else 'NULL'
    }
      # Format all values for SQL
    formatted_values = []
    fields = [
        'promo_code', 'promo_start_date', 'promo_end_date', 'operator_id',
        'promo_description', 'promo_duration', 'promo_amount', 'effective_date',
        'expiration_date', 'sku_group_id', 'prim_sku_group_id', 'soc_group_id', 
        'atst_group_id', 'appl_group_id', 'device_st_group_id', 'finance_type', 
        'act_line_req_ind', 'app_grace_group_id', 'trade_in_grp_id', 'trade_in_grace_period',
        'maint_act_line_chk_ind', 'maint_soc_chk_ind', 'store_grp_id', 'market_grp_id', 
        'limit_per_ban', 'tenure_group_id', 'portin_group_id', 'promo_perc_disc', 
        'c2_link', 'min_gsm_count', 'max_gsm_count', 'display_promo', 'tiered_grp_id',
        'segment_grp_id', 'bolton_trade_in_grp_id', 'product_type', 'pr_date',
        'promo_grace_period', 'line_st_group_id', 'nseip_drop_ind', 'delay_time',
        'display_promo_start_date', 'display_promo_end_date', 'mpss_lookback',
        'flow_indicator', 'document_id', 'dvc_sts_grp_id', 'clawback_ind'
    ]
    for field in fields:
        val = sql_values.get(field)
        if field in ['promo_start_date', 'promo_end_date', 'effective_date', 
                     'expiration_date', 'display_promo_start_date', 'display_promo_end_date']:
            formatted_values.append(val)  # Already formatted by fmt_date
        else:
            formatted_values.append(fmt_sql_value(val))    # Build the SQL statement - column order must match the sample SQL exactly
    columns = [
        'RULE_ID', 'PROMO_CODE', 'PROMO_START_DATE', 'PROMO_END_DATE', 'SYS_CREATION_DATE',
        'OPERATOR_ID', 'APPLICATION_ID', 'DL_SERVICE_CODE', 'PROMO_DESCRIPTION', 'PROMO_DURATION',
        'PROMO_AMOUNT', 'EFFECTIVE_DATE', 'EXPIRATION_DATE', 'SKU_GROUP_ID', 'PRIM_SKU_GROUP_ID',
        'SOC_GROUP_ID', 'ATST_GROUP_ID', 'APPL_GROUP_ID', 'DEVICE_ST_GROUP_ID', 'FINANCE_TYPE',
        'ACT_LINE_REQ_IND', 'APP_GRACE_GROUP_ID', 'TRADE_IN_GRP_ID', 'TRADE_IN_GRACE_PERIOD',
        'MAINT_ACT_LINE_CHK_IND', 'MAINT_SOC_CHK_IND', 'STORE_GRP_ID', 'MARKET_GRP_ID',
        'LIMIT_PER_BAN', 'TENURE_GROUP_ID', 'PORTIN_GROUP_ID', 'PROMO_PERC_DISC', 'C2_LINK',
        'MIN_GSM_COUNT', 'MAX_GSM_COUNT', 'DISPLAY_PROMO', 'TIERED_GRP_ID', 'SEGMENT_GRP_ID',
        'BOLTON_TRADE_IN_GRP_ID', 'PRODUCT_TYPE', 'PR_DATE', 'PROMO_GRACE_PERIOD',
        'LINE_ST_GROUP_ID', 'NSEIP_DROP_IND', 'DELAY_TIME', 'DISPLAY_PROMO_START_DATE',
        'DISPLAY_PROMO_END_DATE', 'MPSS_LOOKBACK', 'FLOW_INDICATOR', 'DOCUMENT_ID',
        'DVC_STS_GRP_ID', 'CLAWBACK_IND'
    ]
    
    # Create the VALUES part matching the sample SQL structure
    values_list = [
        'PROMO_ELIGIBILITY_RULES_1SQ.NEXTVAL',  # RULE_ID
        formatted_values[0],  # promo_code
        formatted_values[1],  # promo_start_date
        formatted_values[2],  # promo_end_date
        'sysdate',           # SYS_CREATION_DATE
        formatted_values[3],  # operator_id
        "'CPO'",             # APPLICATION_ID
        "'USRST'",           # DL_SERVICE_CODE
        formatted_values[4],  # promo_description
        formatted_values[5],  # promo_duration
        formatted_values[6],  # promo_amount
        formatted_values[7],  # effective_date
        formatted_values[8],  # expiration_date
        formatted_values[9],  # sku_group_id
        formatted_values[10], # prim_sku_group_id
        formatted_values[11], # soc_group_id
        formatted_values[12], # atst_group_id
        formatted_values[13], # appl_group_id
        formatted_values[14], # device_st_group_id
        formatted_values[15], # finance_type
        formatted_values[16], # act_line_req_ind
        formatted_values[17], # app_grace_group_id
        formatted_values[18], # trade_in_grp_id
        formatted_values[19], # trade_in_grace_period
        formatted_values[20], # maint_act_line_chk_ind
        formatted_values[21], # maint_soc_chk_ind
        formatted_values[22], # store_grp_id
        formatted_values[23], # market_grp_id
        formatted_values[24], # limit_per_ban
        formatted_values[25], # tenure_group_id
        formatted_values[26], # portin_group_id
        formatted_values[27], # promo_perc_disc
        formatted_values[28], # c2_link
        formatted_values[29], # min_gsm_count
        formatted_values[30], # max_gsm_count
        formatted_values[31], # display_promo
        formatted_values[32], # tiered_grp_id
        formatted_values[33], # segment_grp_id
        formatted_values[34], # bolton_trade_in_grp_id
        formatted_values[35], # product_type
        formatted_values[36], # pr_date
        formatted_values[37], # promo_grace_period
        formatted_values[38], # line_st_group_id
        formatted_values[39], # nseip_drop_ind
        formatted_values[40], # delay_time
        formatted_values[41], # display_promo_start_date
        formatted_values[42], # display_promo_end_date
        formatted_values[43], # mpss_lookback
        formatted_values[44], # flow_indicator
        formatted_values[45], # document_id
        formatted_values[46], # dvc_sts_grp_id
        formatted_values[47]  # clawback_ind
    ]
    sql = f"INSERT INTO PROMO_ELIGIBILITY_RULES ({','.join(columns)}) VALUES ({','.join(values_list)});"
    
    return sql


@app.route("/")
def home():
    return render_template("index.html")
@app.route("/edit_promo", methods=["GET", "POST"])
@app.route("/edit_promo/<promo_code>", methods=["GET", "POST"])
def edit_promo(promo_code=None):
    # Get promo code from URL or request args
    if not promo_code:
        promo_code = request.args.get('promo_code', 'P0472022')
    
    # Load promo data from storage
    promo_data = data_manager.get_promo(promo_code)
      # If promo doesn't exist, create a new one with default values
    if not promo_data:
        promo_data = {
            "code": promo_code,
            "owner": "New Owner",
            "bill_facing_name": "New Promotion",
            "initiative_name": "",
            "orbit_id": "",
            "pj_code": "",
            "description": "",
            "promo_notes": "",
            "discount": 0,
            "amount": 0,
            "nseip_drop": "N",
            "dcd_web_cart": "N",
            "product_type": "",
            "bogo": "N",
            "trade_in_group_id": "",
            "fpd_display_promo": "N",
            "on_menu": "N",
            "market_group": "*",
            "store_group": "*",
            "sku_link": "",
            "tradein_link": "",
            "promo_start_date": "",
            "promo_end_date": "",
            "comm_end_date": "",
            "promo_duration": 0,
            "delay_time": 0,
            "application_grace_period": "",
            "promo_grace": "",
            "trade_in_grace": "",
            "mpss_lookback": "",
            "device_sales_type": "",
            "activation_type": "*",
            "maintain_soc": "N",
            "limit_per_ban": 0,
            "min_gsm_count": "",
            "max_gsm_count": 0,
            "port_in_group_id": "",
            "segment_name": "",
            "sub_segment": "",
            "segment_group_id": "",
            "segment_level": "",
            "soc_grouping": "",
            "account_type": "",
            "sales_application": "",
            "bptcr": "",
            "operator_id": "16085",
            "sku_group_id": "",
            "device_status_group_id": "",
            "clawback_indicator": "N",
            "flow_indicator": "NULL",
            "version_history": []
        }

    # Determine active tab from GET or POST
    active_tab = request.args.get('tab')
    if request.method == 'POST':
        active_tab = request.form.get('active_tab', active_tab)        # Helper function to safely convert to integer
        def safe_int_convert(value, field_name, default=0):
            if not value:
                return default
            try:
                # Handle float strings by converting to float first, then int
                if isinstance(value, str) and '.' in value:
                    float_val = float(value)
                    if float_val != int(float_val):
                        flash(f'{field_name} must be a whole number. Decimal values are not allowed.', 'error')
                        return default
                    return int(float_val)
                return int(value)
            except (ValueError, TypeError):
                flash(f'{field_name} must be a valid whole number.', 'error')
                return default

        # Helper function for nullable integer fields (returns None if empty)
        def safe_int_convert_nullable(value, field_name):
            if not value or value.strip() == '':
                return None
            try:
                # Handle float strings by converting to float first, then int
                if isinstance(value, str) and '.' in value:
                    float_val = float(value)
                    if float_val != int(float_val):
                        flash(f'{field_name} must be a whole number. Decimal values are not allowed.', 'error')
                        return None
                    return int(float_val)
                return int(value)
            except (ValueError, TypeError):
                flash(f'{field_name} must be a valid whole number.', 'error')
                return None        # Handle form submission for each tab
        if active_tab == 'Details':            # Update Details tab fields
            promo_data.update({
                'bill_facing_name': request.form.get('bill_facing_name', ''),
                'initiative_name': request.form.get('initiative_name', ''),
                'discount': request.form.get('discount', ''),
                'amount': request.form.get('amount', ''),
                'nseip_drop': request.form.get('nseip_drop', 'N'),
                'dcd_web_cart': request.form.get('dcd_web_cart', 'N'),
                'product_type': request.form.get('product_type', ''),
                'bogo': request.form.get('bogo', 'N'),
                'trade_in_group_id': request.form.get('trade_in_group_id', ''),
                'fpd_display_promo': request.form.get('fpd_display_promo', 'N'),
                'on_menu': request.form.get('on_menu', 'N'),
                'market_group': request.form.get('market_group', '*'),
                'store_group': request.form.get('store_group', '*'),
                'sku_link': request.form.get('sku_link', ''),
                'tradein_link': request.form.get('tradein_link', '')            })
        
        elif active_tab == 'Dates & Times':            # Update Dates & Times tab fields
            promo_data.update({
                'promo_start_date': request.form.get('promo_start_date', ''),
                'promo_end_date': request.form.get('promo_end_date', ''),
                'comm_end_date': request.form.get('comm_end_date', ''),
                'promo_duration': request.form.get('promo_duration', ''),
                'delay_time': request.form.get('delay_time', ''),
                'application_grace_period': request.form.get('application_grace_period', ''),
                'promo_grace': request.form.get('promo_grace', ''),
                'trade_in_grace': request.form.get('trade_in_grace', ''),
                'mpss_lookback': request.form.get('mpss_lookback', '')
            })
        elif active_tab == 'Requirements':
            # Update Requirements tab fields
            promo_data.update({
                'device_sales_type': request.form.get('device_sales_type', ''),
                'activation_type': request.form.get('activation_type', '*'),
                'active_line_required': request.form.get('active_line_required', 'N'),
                'maintain_soc': request.form.get('maintain_soc', 'N'),
                'maintain_active_line': request.form.get('maintain_active_line', 'N'),
                'limit_per_ban': request.form.get('limit_per_ban', ''),
                'min_gsm_count': request.form.get('min_gsm_count', ''),
                'max_gsm_count': request.form.get('max_gsm_count', ''),
                'port_in_group_id': request.form.get('port_in_group_id', ''),
                'operator_id': request.form.get('operator_id', '16085'),
                'sku_group_id': request.form.get('sku_group_id', ''),
                'device_status_group_id': request.form.get('device_status_group_id', ''),
                'clawback_indicator': request.form.get('clawback_indicator', 'N'),
                'flow_indicator': request.form.get('flow_indicator', 'NULL')
            })
        
        elif active_tab == 'Segmentation':
            # Update Segmentation tab fields
            promo_data.update({
                'segment_name': request.form.get('segment_name', ''),
                'sub_segment': request.form.get('sub_segment', ''),
                'segment_group_id': request.form.get('segment_group_id', ''),
                'segment_level': request.form.get('segment_level', '')
            })
        
        elif active_tab == 'Groupings':
            # Update Groupings tab fields
            promo_data.update({
                'soc_grouping': request.form.get('soc_grouping', ''),
                'account_type': request.form.get('account_type', ''),
                'sales_application': request.form.get('sales_application', '')
            })
        
        elif active_tab == 'BPTCR':
            # Update BPTCR tab fields
            promo_data['bptcr'] = request.form.get('bptcr', '')
        
        elif active_tab == 'SQL Generation':
            # Handle file uploads for SQL Generation tab
            uploaded_files = promo_data.get('uploaded_files', {})
            
            # Handle SKU Excel file upload
            if 'sku_excel' in request.files:
                sku_file = request.files['sku_excel']
                if sku_file and sku_file.filename:
                    try:
                        file_metadata = data_manager.save_excel_file(promo_code, sku_file, 'sku_excel')
                        uploaded_files['sku_excel'] = file_metadata
                        flash('SKU Excel file uploaded successfully!', 'success')
                    except Exception as e:
                        flash(f'Error uploading SKU file: {str(e)}', 'error')
            
            # Handle Trade-In Excel file upload
            if 'tradein_excel' in request.files:
                tradein_file = request.files['tradein_excel']
                if tradein_file and tradein_file.filename:
                    try:
                        file_metadata = data_manager.save_excel_file(promo_code, tradein_file, 'tradein_excel')
                        uploaded_files['tradein_excel'] = file_metadata
                        flash('Trade-In Excel file uploaded successfully!', 'success')
                    except Exception as e:
                        flash(f'Error uploading Trade-In file: {str(e)}', 'error')
            
            promo_data['uploaded_files'] = uploaded_files
              # Handle SQL generation if requested
            if request.form.get('generate_sql'):
                try:
                    sql_statement = generate_promo_eligibility_sql(promo_data)
                    
                    # Save SQL to file for download
                    sql_filename = f"{promo_code}_promo_eligibility_rules.sql"
                    sql_file_path = data_manager.save_sql_file(promo_code, sql_statement, sql_filename)
                    
                    flash('SQL generated successfully! Click download to get the SQL file.', 'success')
                    # Store the generated SQL and file info for display and download
                    promo_data['generated_sql'] = sql_statement
                    promo_data['sql_file'] = {
                        'filename': sql_filename,
                        'path': sql_file_path,
                        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Redirect to the same page with SQL Generation tab active to show the result
                    data_manager.save_promo(promo_code, promo_data, user_name="Daniel Zhang")
                    return redirect(url_for('edit_promo', promo_code=promo_code, tab='SQL Generation'))
                    
                except Exception as e:
                    flash(f'Error generating SQL: {str(e)}', 'error')
        
        # Save updated promo data
        try:
            data_manager.save_promo(promo_code, promo_data, user_name="Daniel Zhang")
            flash(f'{active_tab} tab saved successfully!', 'success')
        except Exception as e:
            flash(f'Error saving {active_tab} tab: {str(e)}', 'error')
    
    if not active_tab:
        active_tab = 'Details'
    
    # Load SOC Grouping content from storage
    soc_groupings = data_manager.get_soc_groupings()
    account_types = data_manager.get_account_types()
    sales_applications = data_manager.get_sales_applications()

    return render_template(
        "edit_promo.html",
        promo=promo_data,
        user_name="Daniel Zhang",
        active_tab=active_tab,
        soc_groupings=soc_groupings,
        account_types=account_types,
        sales_applications=sales_applications
    )


@app.route("/promotions")
def promotions():
    # Load all promotions from data manager
    all_promotions = data_manager.get_all_promos()
    
    # Convert to the format expected by the template
    promotions_list = []
    for promo_code, promo_data in all_promotions.items():
        promotions_list.append({
            "code": promo_code,
            "orbit_id": promo_data.get('orbit_id', ''),
            "status": "In Progress",  # You can add logic to determine status
            "description": promo_data.get('bill_facing_name', ''),
            "start_date": promo_data.get('promo_start_date', ''),
            "end_date": promo_data.get('promo_end_date', ''),
            "owner": promo_data.get('owner', '')
        })
    
    # Get unique owners for filter dropdown
    owners = ["All"] + list(set([p.get('owner', '') for p in all_promotions.values() if p.get('owner')]))
    
    return render_template(
        "promotions.html",
        promotion_code="All Promotions",
        user_name="Daniel Zhang",
        owners=owners,
        selected_owner="All",
        search_query="",
        active_tab="RDC",
        promotions=promotions_list,
        current_datetime=datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")
    )


@app.route("/spe")
def spe():
    # SPE-specific promotions data
    spe_promotions = [
        {
            "code": "SP005",
            "orbit_id": "15600",
            "status": "Active",
            "description": "SPE Line On Us Promo",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "owner": "Hari Kariavula"
        },
        {
            "code": "SP122",
            "orbit_id": "23987",
            "status": "Launched",
            "description": "Internet ID250153",
            "start_date": "3/27/2025",
            "end_date": "4/2/2025",
            "owner": "Rich Brakenhoff"
        }
    ]
    
    return render_template(
        "spe.html",
        promotion_code="SPE Promotions",
        user_name="Daniel Zhang",
        owners=["All", "Hari Kariavula", "Rich Brakenhoff", "Cade Holtzen"],
        selected_owner="All",
        search_query="",
        active_tab="SPE",
        promotions=spe_promotions,
        current_datetime=datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")
    )


@app.route("/edit_spe", methods=["GET", "POST"])
def edit_spe():
    # Get promo_code from URL parameters
    promo_code = request.args.get('promo_code', 'SP005')
    
    # Load existing SPE promo data or create default
    try:
        spe_data = data_manager.get_spe_promo(promo_code)
    except:
        # Default SPE promo structure if not found
        spe_data = {
            "code": promo_code,
            "owner": "",
            "bill_facing_name": "",
            "orbit_id": "",
            "pj_code": "",
            "description": "",
            "promo_notes": "",
            "promo_identifier": "",
            "pt_priority_indicator": "",
            "account_type": "",
            "sales_application": "",
            "dcd_web_cart": "",
            "on_menu": "",
            "service_priority": "",
            "max_discount": "",
            "market_group": "",
            "store_group": "",
            "c2_content": "",
            "promo_start_date": "",
            "promo_end_date": "",
            "pr_date": "",
            "ban_tenure_start": "",
            "ban_tenure_end": "",
            "channel_grace_period": "",
            "maintain_line_count_days": "",
            "re_enroll_period": "",
            "promo_duration": "",
            "port_duration": "",
            "tfb_channel_group_id": "",
            "dealer_group_id": "",
            "updated_mrc_ranking": "",
            "suppress_discount_reorder": "",
            "retro_ban_evaluation": "",
            "port_in_group_id": "",
            "adjustment_code": "",
            "discount_codes": "",
            "total_indicator": "",
            "gsm_indicator": "",
            "mi_indicator": "",
            "pure_mi_indicator": "",
            "virtual_mi_indicator": "",
            "duplicate_indicator": "",
            "auto_att_indicator": "",
            "fax_line_indicator": "",
            "conference_indicator": "",
            "iot_indicator": "",
            "go_soc_group_id": "",
            "bo_soc_group_id": "",
            "paid_soc_group_id": "",
            "min_paid_line_mi_count": "",
            "go_line_maintenance": "",
            "bo_line_maintenance": "",
            "paid_line_maintenance": "",
            "min_paid_line_gsm_count": "",
            "go_line_count": "",
            "bo_line_count": "",
            "borrow_bo_lines": "",
            "lend_bo_lines": "",
            "soc_discount_mapping": "",
            "version_history": []
        }

    # Determine active tab from GET or POST
    active_tab = request.args.get('tab')
    if request.method == 'POST':
        active_tab = request.form.get('active_tab', active_tab)
        
        # Handle form submission for each tab
        if active_tab == 'Details':
            # Update Details tab fields
            spe_data.update({
                'promo_identifier': request.form.get('promo_identifier') if request.form.get('promo_identifier') else None,
                'pt_priority_indicator': request.form.get('pt_priority_indicator') if request.form.get('pt_priority_indicator') else None,
                'account_type': request.form.get('account_type') if request.form.get('account_type') else None,
                'sales_application': request.form.get('sales_application') if request.form.get('sales_application') else None,
                'dcd_web_cart': request.form.get('dcd_web_cart') if request.form.get('dcd_web_cart') else None,
                'on_menu': request.form.get('on_menu') if request.form.get('on_menu') else None,
                'service_priority': request.form.get('service_priority') if request.form.get('service_priority') else None,
                'max_discount': request.form.get('max_discount') if request.form.get('max_discount') else None,
                'market_group': request.form.get('market_group') if request.form.get('market_group') else None,
                'store_group': request.form.get('store_group') if request.form.get('store_group') else None,
                'c2_content': request.form.get('c2_content') if request.form.get('c2_content') else None
            })
        
        elif active_tab == 'Dates & Times':
            # Update Dates & Times tab fields
            spe_data.update({
                'promo_start_date': request.form.get('promo_start_date') if request.form.get('promo_start_date') else None,
                'promo_end_date': request.form.get('promo_end_date') if request.form.get('promo_end_date') else None,
                'pr_date': request.form.get('pr_date') if request.form.get('pr_date') else None,
                'ban_tenure_start': request.form.get('ban_tenure_start') if request.form.get('ban_tenure_start') else None,
                'ban_tenure_end': request.form.get('ban_tenure_end') if request.form.get('ban_tenure_end') else None,
                'channel_grace_period': request.form.get('channel_grace_period') if request.form.get('channel_grace_period') else None,
                'maintain_line_count_days': request.form.get('maintain_line_count_days') if request.form.get('maintain_line_count_days') else None,
                're_enroll_period': request.form.get('re_enroll_period') if request.form.get('re_enroll_period') else None,
                'promo_duration': request.form.get('promo_duration') if request.form.get('promo_duration') else None,
                'port_duration': request.form.get('port_duration') if request.form.get('port_duration') else None
            })
        
        elif active_tab == 'Requirements':
            # Update Requirements tab fields
            spe_data.update({
                'tfb_channel_group_id': request.form.get('tfb_channel_group_id') if request.form.get('tfb_channel_group_id') else None,
                'dealer_group_id': request.form.get('dealer_group_id') if request.form.get('dealer_group_id') else None,
                'updated_mrc_ranking': request.form.get('updated_mrc_ranking') if request.form.get('updated_mrc_ranking') else None,
                'suppress_discount_reorder': request.form.get('suppress_discount_reorder') if request.form.get('suppress_discount_reorder') else None,
                'retro_ban_evaluation': request.form.get('retro_ban_evaluation') if request.form.get('retro_ban_evaluation') else None,
                'port_in_group_id': request.form.get('port_in_group_id') if request.form.get('port_in_group_id') else None,
                'adjustment_code': request.form.get('adjustment_code') if request.form.get('adjustment_code') else None,
                'discount_codes': request.form.get('discount_codes') if request.form.get('discount_codes') else None
            })
        
        elif active_tab == 'Line Indicators':
            # Update Line Indicators tab fields
            spe_data.update({
                'total_indicator': request.form.get('total_indicator') if request.form.get('total_indicator') else None,
                'gsm_indicator': request.form.get('gsm_indicator') if request.form.get('gsm_indicator') else None,
                'mi_indicator': request.form.get('mi_indicator') if request.form.get('mi_indicator') else None,
                'pure_mi_indicator': request.form.get('pure_mi_indicator') if request.form.get('pure_mi_indicator') else None,
                'virtual_mi_indicator': request.form.get('virtual_mi_indicator') if request.form.get('virtual_mi_indicator') else None,
                'duplicate_indicator': request.form.get('duplicate_indicator') if request.form.get('duplicate_indicator') else None,
                'auto_att_indicator': request.form.get('auto_att_indicator') if request.form.get('auto_att_indicator') else None,
                'fax_line_indicator': request.form.get('fax_line_indicator') if request.form.get('fax_line_indicator') else None,
                'conference_indicator': request.form.get('conference_indicator') if request.form.get('conference_indicator') else None,
                'iot_indicator': request.form.get('iot_indicator') if request.form.get('iot_indicator') else None
            })
        
        elif active_tab == 'SOC Groupings':
            # Update SOC Groupings tab fields
            spe_data.update({
                'go_soc_group_id': request.form.get('go_soc_group_id') if request.form.get('go_soc_group_id') else None,
                'bo_soc_group_id': request.form.get('bo_soc_group_id') if request.form.get('bo_soc_group_id') else None,
                'paid_soc_group_id': request.form.get('paid_soc_group_id') if request.form.get('paid_soc_group_id') else None,
                'min_paid_line_mi_count': request.form.get('min_paid_line_mi_count') if request.form.get('min_paid_line_mi_count') else None,
                'go_line_maintenance': request.form.get('go_line_maintenance') if request.form.get('go_line_maintenance') else None,
                'bo_line_maintenance': request.form.get('bo_line_maintenance') if request.form.get('bo_line_maintenance') else None,
                'paid_line_maintenance': request.form.get('paid_line_maintenance') if request.form.get('paid_line_maintenance') else None,
                'min_paid_line_gsm_count': request.form.get('min_paid_line_gsm_count') if request.form.get('min_paid_line_gsm_count') else None,
                'go_line_count': request.form.get('go_line_count') if request.form.get('go_line_count') else None,
                'bo_line_count': request.form.get('bo_line_count') if request.form.get('bo_line_count') else None,
                'borrow_bo_lines': request.form.get('borrow_bo_lines') if request.form.get('borrow_bo_lines') else None,
                'lend_bo_lines': request.form.get('lend_bo_lines') if request.form.get('lend_bo_lines') else None,
                'soc_discount_mapping': request.form.get('soc_discount_mapping') if request.form.get('soc_discount_mapping') else None
            })
        
        # Save updated SPE promo data
        try:
            data_manager.save_spe_promo(promo_code, spe_data, user_name="Daniel Zhang")
            flash(f'{active_tab} tab saved successfully!', 'success')
        except Exception as e:
            flash(f'Error saving {active_tab} tab: {str(e)}', 'error')
    
    if not active_tab:
        active_tab = 'Details'

    return render_template(
        "edit_spe.html",
        promo=spe_data,
        user_name="Daniel Zhang",
        active_tab=active_tab
    )


@app.route("/date_mismatch")
def date_mismatch():
    return render_template(
        "date_mismatch.html",
        user_name="Daniel Zhang",
        current_datetime=datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")
    )


@app.route("/download_file/<promo_code>/<file_type>")
def download_file(promo_code, file_type):
    """Download uploaded Excel files"""
    from flask import send_file, abort
    
    try:
        file_path = data_manager.get_file_path(promo_code, file_type)
        if file_path and os.path.exists(file_path):
            file_info = data_manager.get_uploaded_file_info(promo_code, file_type)
            original_name = file_info.get('original_name', 'download.xlsx') if file_info else 'download.xlsx'
            return send_file(file_path, as_attachment=True, download_name=original_name)
        else:
            abort(404)
    except Exception:
        abort(404)


@app.route("/download_sql/<promo_code>")
def download_sql(promo_code):
    """Download generated SQL file"""
    from flask import send_file, abort
    
    try:
        # Get promo data to find SQL file info
        promo_data = data_manager.get_promo(promo_code)
        if promo_data and 'sql_file' in promo_data:
            sql_file_info = promo_data['sql_file']
            file_path = sql_file_info.get('path')
            filename = sql_file_info.get('filename', f'{promo_code}_sql.sql')
            
            if file_path and os.path.exists(file_path):
                return send_file(file_path, as_attachment=True, download_name=filename, mimetype='text/plain')
            else:
                abort(404)
        else:
            abort(404)
    except Exception:
        abort(404)


def format_adf_description(text):
    """Format text into Atlassian Document Format (ADF) for JIRA description"""
    lines = str(text).strip().splitlines()
    adf_blocks = []

    for line in lines:
        line = line.strip()
        if not line:
            adf_blocks.append({"type": "paragraph", "content": []})
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            adf_blocks.append({
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": key.strip() + ":",
                        "marks": [{"type": "strong"}]
                    },
                    {
                        "type": "text",
                        "text": " " + value.strip()
                    }
                ]
            })
        else:
            adf_blocks.append({
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": line}
                ]
            })

    return {"type": "doc", "version": 1, "content": adf_blocks}


@app.route("/create_jira_ticket", methods=["POST"])
def create_jira_ticket():
    """Create a JIRA ticket and update the operator_id with the ticket number"""
    try:
        data = request.get_json()
        
        # JIRA configuration
        JIRA_URL = "https://t-mobile-stage.atlassian.net"
        PROJECT_KEY = "CPO"
        CUSTOM_FIELD_TEAM_ID = "customfield_10048"
        TEAM_VALUE = "Promo Ops T1"
        # R2D2_TEAM_ID_FIELD = "customfield_10059"  # R2D2 Team ID field - disabled, field not available in CPO project
        # R2D2_TEAM_VALUE = "2730"
        
        # Extract form data
        summary = data.get('summary', '')[:2000]  # Limit to 2000 chars
        description_text = data.get('description', '')
        priority = data.get('priority', 'High')
        issue_type = data.get('issue_type', 'Task')
        parent_key = data.get('parent', '')
        user_email = data.get('email', '')
        api_token = data.get('token', '')
        promo_code = data.get('promo_code', '')
        
        if not all([summary, description_text, user_email, api_token, promo_code]):
            return jsonify({"success": False, "error": "Missing required fields"})
        
        # Prepare JIRA ticket fields (with assignee matching reporter)
        fields = {
            "project": {"key": PROJECT_KEY},
            "summary": summary,
            "description": format_adf_description(description_text),
            "priority": {"name": priority},
            "issuetype": {"name": issue_type},
            "labels": ["New_Promo"],
            "assignee": {"emailAddress": user_email},  # Set assignee same as reporter
            CUSTOM_FIELD_TEAM_ID: {"value": TEAM_VALUE}
            # R2D2_TEAM_ID_FIELD: R2D2_TEAM_VALUE  # Disabled - field not available in CPO project
        }
        
        # Add parent if specified
        if parent_key:
            fields["parent"] = {"key": parent_key}
        
        # Prepare request
        payload = {"fields": fields}
        url = f"{JIRA_URL}/rest/api/3/issue"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        auth = (user_email, api_token)
        
        # Make JIRA API request
        response = requests.post(url, json=payload, headers=headers, auth=auth, verify=False)
        
        if response.status_code == 201:
            # Extract ticket key from response
            ticket_data = response.json()
            ticket_key = ticket_data["key"]
            
            # Update the promo with the JIRA ticket information
            promo_data = data_manager.get_promo(promo_code)
            if promo_data:
                # Store the JIRA ticket key
                promo_data['jira_ticket'] = ticket_key
                
                # Extract just the number from the ticket key (e.g., "CPO-123" -> "123")
                ticket_number = ticket_key.split('-')[-1]
                
                # Update the operator_id with the ticket number
                promo_data['operator_id'] = ticket_number
                
                # Save the updated promo data
                data_manager.save_promo(promo_code, promo_data, user_name=user_email.split('@')[0])
                
                return jsonify({
                    "success": True, 
                    "ticket_key": ticket_key,
                    "ticket_url": f"{JIRA_URL}/browse/{ticket_key}",
                    "operator_id": ticket_number
                })
            else:
                return jsonify({"success": False, "error": "Promo not found"})
        else:
            error_msg = f"JIRA API Error: {response.status_code} - {response.text}"
            return jsonify({"success": False, "error": error_msg})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(debug=True)
