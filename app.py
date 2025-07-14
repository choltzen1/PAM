from flask import Flask, render_template
from datetime import datetime


app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")
from flask import request, redirect, url_for

@app.route("/edit_promo", methods=["GET", "POST"])
def edit_promo():
    # Simulate a promo object with all needed fields for both tabs
    fake_promo = {
        "code": "P0472022",
        "owner": "Alejandro Ferrer",
        "bill_facing_name": "2022 Samsung Trade P30",
        "orbit_id": "15233",
        "pj_code": "P047",
        "description": "Magenta Only: Customers can get up to $600 off GS22 Series when they trade in an eligible device (new and existing customers qualify) on a qualifying rate plan - TFB Retail Only.",
        "promo_notes": "Two-tiered discount structure.\n1. $700: All iPhones EXCEPT the iPhone 14 and 15\n2. $730: iPhone 14 and 15 (including all memory variants) to have $730\nTier 1 $730: iPhone 15, iPhone 15 Plus, iPhone 15 Pro, iPhone 15 Pro Max, iPhone 14, iPhone 14 Plus, iPhone 14 Pro, iPhone 14 Pro Max\nTier 2 $700: iPhone 15 Plus, iPhone 15 Pro, iPhone 15 Pro Max, iPhone 14 Plus, iPhone 14 Pro, iPhone 14 Pro Max, iPhone 13 Mini, iPhone 13 Pro, iPhone 13 Pro Max",
        "discount": 10,
        "amount": 600,
        "nseip_drop": "N",
        "dcd_web_cart": "Y",
        "product_type": "G",
        "bogo": "N",
        "trade_in_group_id": "TRD2025-001",
        "fpd_display_promo": "N",
        "on_menu": "Y",
        "market_group": "*",
        "store_group": "*",
        "sku_link": "https://web.powerapps.com/webplayer/iframe...",
        "tradein_link": "https://web.powerapps.com/webplayer/iframe...",
        "promo_start_date": "2025-07-01",
        "promo_end_date": "2025-08-01",
        "comm_end_date": "2025-08-15",
        "promo_duration": 24,
        "delay_time": 0,
        "application_grace_period": "G11",
        "promo_grace": "",
        "trade_in_grace": "",
        "mpss_lookback": "",
        # Requirements tab fields
        "device_sales_type": "S01",
        "activation_type": "*",
        "maintain_soc": "Y",
        "limit_per_ban": 4,
        "min_gsm_count": "",
        "max_gsm_count": 12,
        "port_in_group_id": "G02",
        "version_history": [
            "11/6/2023 1:18 PM - Michael Pugh - Approval requested for Care-Medjo, Sue, Commissions - Sandbo, Stephany and Device Finance - Kanzler, Justin.",
            "11/1/2023 10:00 AM - Daniel Zhang - Created promo."
        ]
    }

    # Load SOC Grouping content from text file
    soc_grouping_content = []
    try:
        with open("static/soc_grouping.txt", "r") as file:
            soc_grouping_content = file.readlines()
    except FileNotFoundError:
        soc_grouping_content = ["Error: SOC Grouping file not found."]

    # Determine active tab from GET or POST
    active_tab = request.args.get('tab')
    if request.method == 'POST':
        active_tab = request.form.get('active_tab', active_tab)
        # Here you would update fake_promo with form data and save to DB
        # For now, just simulate a save and stay on the same tab
    if not active_tab:
        active_tab = 'Details'

    return render_template(
        "edit_promo.html",
        promo=fake_promo,
        user_name="Daniel Zhang",
        active_tab=active_tab,
        soc_grouping_content=soc_grouping_content
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



if __name__ == "__main__":
    app.run(debug=True)
