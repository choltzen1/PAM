from flask import Flask, render_template, request, redirect, url_for, flash
import os
from datetime import datetime
from data.storage import PromoDataManager

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
            # Update BPTCR tab field
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
            "owner": "Hari Kariavula",
            "bill_facing_name": "2022 Line On Us P2",
            "orbit_id": "15600",
            "pj_code": "SPE",
            "description": "SPE Line On Us Promo",
            "promo_notes": "",
            "promo_identifier": "B",
            "pt_priority_indicator": "G",
            "account_type": "*",
            "sales_application": "*",
            "dcd_web_cart": "Y",
            "on_menu": "N",
            "service_priority": "2880",
            "max_discount": "1",
            "market_group": "*",
            "store_group": "*",
            "c2_content": "",
            "promo_start_date": "2025-01-01",
            "promo_end_date": "2025-12-31",
            "pr_date": "",
            "ban_tenure_start": "",
            "ban_tenure_end": "",
            "channel_grace_period": "NULL",
            "maintain_line_count_days": "365",
            "re_enroll_period": "",
            "promo_duration": "",
            "port_duration": "",
            "tfb_channel_group_id": "NULL",
            "dealer_group_id": "NULL",
            "updated_mrc_ranking": "NULL",
            "suppress_discount_reorder": "No",
            "retro_ban_evaluation": "No",
            "port_in_group_id": "NULL",
            "adjustment_code": "EEDG74",
            "discount_codes": "22Q12F, 22Q12P, 22Q12S",
            "total_indicator": "N",
            "gsm_indicator": "Y",
            "mi_indicator": "N",
            "pure_mi_indicator": "N",
            "virtual_mi_indicator": "N",
            "duplicate_indicator": "N",
            "auto_att_indicator": "N",
            "fax_line_indicator": "N",
            "conference_indicator": "N",
            "iot_indicator": "N",
            "go_soc_group_id": "A56",
            "bo_soc_group_id": "A55",
            "paid_soc_group_id": "A55",
            "min_paid_line_mi_count": "",
            "go_line_maintenance": "A57",
            "bo_line_maintenance": "A57",
            "paid_line_maintenance": "A57",
            "min_paid_line_gsm_count": "1",
            "go_line_count": "1",
            "bo_line_count": "1",
            "borrow_bo_lines": "N",
            "lend_bo_lines": "Y",
            "soc_discount_mapping": "https://web.powerapps.com/webplayer/iframe...",
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
                'promo_identifier': request.form.get('promo_identifier', 'B'),
                'pt_priority_indicator': request.form.get('pt_priority_indicator', 'G'),
                'account_type': request.form.get('account_type', '*'),
                'sales_application': request.form.get('sales_application', '*'),
                'dcd_web_cart': request.form.get('dcd_web_cart', 'N'),
                'on_menu': request.form.get('on_menu', 'N'),
                'service_priority': request.form.get('service_priority', '2880'),
                'max_discount': request.form.get('max_discount', '1'),
                'market_group': request.form.get('market_group', '*'),
                'store_group': request.form.get('store_group', '*'),
                'c2_content': request.form.get('c2_content', '')
            })
        
        elif active_tab == 'Dates & Times':
            # Update Dates & Times tab fields
            spe_data.update({
                'promo_start_date': request.form.get('promo_start_date', ''),
                'promo_end_date': request.form.get('promo_end_date', ''),
                'pr_date': request.form.get('pr_date', ''),
                'ban_tenure_start': request.form.get('ban_tenure_start', ''),
                'ban_tenure_end': request.form.get('ban_tenure_end', ''),
                'channel_grace_period': request.form.get('channel_grace_period', 'NULL'),
                'maintain_line_count_days': request.form.get('maintain_line_count_days', '365'),
                're_enroll_period': request.form.get('re_enroll_period', ''),
                'promo_duration': request.form.get('promo_duration', ''),
                'port_duration': request.form.get('port_duration', '')
            })
        
        elif active_tab == 'Requirements':
            # Update Requirements tab fields
            spe_data.update({
                'tfb_channel_group_id': request.form.get('tfb_channel_group_id', 'NULL'),
                'dealer_group_id': request.form.get('dealer_group_id', 'NULL'),
                'updated_mrc_ranking': request.form.get('updated_mrc_ranking', 'NULL'),
                'suppress_discount_reorder': request.form.get('suppress_discount_reorder', 'No'),
                'retro_ban_evaluation': request.form.get('retro_ban_evaluation', 'No'),
                'port_in_group_id': request.form.get('port_in_group_id', 'NULL'),
                'adjustment_code': request.form.get('adjustment_code', 'EEDG74'),
                'discount_codes': request.form.get('discount_codes', '')
            })
        
        elif active_tab == 'Line Indicators':
            # Update Line Indicators tab fields
            spe_data.update({
                'total_indicator': request.form.get('total_indicator', 'N'),
                'gsm_indicator': request.form.get('gsm_indicator', 'N'),
                'mi_indicator': request.form.get('mi_indicator', 'N'),
                'pure_mi_indicator': request.form.get('pure_mi_indicator', 'N'),
                'virtual_mi_indicator': request.form.get('virtual_mi_indicator', 'N'),
                'duplicate_indicator': request.form.get('duplicate_indicator', 'N'),
                'auto_att_indicator': request.form.get('auto_att_indicator', 'N'),
                'fax_line_indicator': request.form.get('fax_line_indicator', 'N'),
                'conference_indicator': request.form.get('conference_indicator', 'N'),
                'iot_indicator': request.form.get('iot_indicator', 'N')
            })
        
        elif active_tab == 'SOC Groupings':
            # Update SOC Groupings tab fields
            spe_data.update({
                'go_soc_group_id': request.form.get('go_soc_group_id', ''),
                'bo_soc_group_id': request.form.get('bo_soc_group_id', ''),
                'paid_soc_group_id': request.form.get('paid_soc_group_id', ''),
                'min_paid_line_mi_count': request.form.get('min_paid_line_mi_count', ''),
                'go_line_maintenance': request.form.get('go_line_maintenance', ''),
                'bo_line_maintenance': request.form.get('bo_line_maintenance', ''),
                'paid_line_maintenance': request.form.get('paid_line_maintenance', ''),
                'min_paid_line_gsm_count': request.form.get('min_paid_line_gsm_count', '1'),
                'go_line_count': request.form.get('go_line_count', '1'),
                'bo_line_count': request.form.get('bo_line_count', '1'),
                'borrow_bo_lines': request.form.get('borrow_bo_lines', 'N'),
                'lend_bo_lines': request.form.get('lend_bo_lines', 'N'),
                'soc_discount_mapping': request.form.get('soc_discount_mapping', '')
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


if __name__ == "__main__":
    app.run(debug=True)
