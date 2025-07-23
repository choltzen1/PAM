from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
from data.storage import PromoDataManager

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages

# Initialize data manager
data_manager = PromoDataManager()


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
            "max_gsm_count": "",
            "port_in_group_id": "",
            "segment_name": "",
            "sub_segment": "",
            "segment_group_id": "",
            "segment_level": "",
            "soc_grouping": "",
            "account_type": "",
            "sales_application": "",
            "bptcr_details": [],
            "version_history": []
        }

    # Determine active tab from GET or POST
    active_tab = request.args.get('tab')
    if request.method == 'POST':
        active_tab = request.form.get('active_tab', active_tab)
        
        # Handle form submission for each tab
        if active_tab == 'Details':
            # Update Details tab fields
            promo_data.update({
                'bill_facing_name': request.form.get('bill_facing_name', ''),
                'discount': float(request.form.get('discount', 0) or 0),
                'amount': float(request.form.get('amount', 0) or 0),
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
                'tradein_link': request.form.get('tradein_link', '')
            })
        
        elif active_tab == 'Dates & Times':
            # Update Dates & Times tab fields
            promo_data.update({
                'promo_start_date': request.form.get('promo_start_date', ''),
                'promo_end_date': request.form.get('promo_end_date', ''),
                'comm_end_date': request.form.get('comm_end_date', ''),
                'promo_duration': int(request.form.get('promo_duration', 0) or 0),
                'delay_time': int(request.form.get('delay_time', 0) or 0),
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
                'maintain_soc': request.form.get('maintain_soc', 'N'),
                'limit_per_ban': int(request.form.get('limit_per_ban', 0) or 0),
                'min_gsm_count': request.form.get('min_gsm_count', ''),
                'max_gsm_count': int(request.form.get('max_gsm_count', 0) or 0),
                'port_in_group_id': request.form.get('port_in_group_id', '')
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
            bptcr_details = []
            for key, value in request.form.items():
                if key.startswith('bptcr_detail_') and value.strip():
                    bptcr_details.append(value.strip())
            promo_data['bptcr_details'] = bptcr_details
        
        # Save updated promo data
        try:
            data_manager.save_promo(promo_code, promo_data, user_name="Daniel Zhang")
            flash(f'{active_tab} tab saved successfully!', 'success')
        except Exception as e:
            flash(f'Error saving {active_tab} tab: {str(e)}', 'error')
    
    if not active_tab:
        active_tab = 'Details'    # Load SOC Grouping content from storage
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
    return render_template(
        "promotions.html",
        promotion_code="P0472022",
        user_name="Daniel Zhang",
        owners=[...],
        selected_owner="All",
        search_query="",
        active_tab="RDC",
        promotions=[{
            "code": "P0472022",
            "orbit_id": "123456",
            "status": "Active",
            "description": "Promotion Description",
            "start_date": "2022-01-01",
            "end_date": "2022-12-31",
            "owner": "Daniel Zhang"
        }],
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


if __name__ == "__main__":
    app.run(debug=True)
