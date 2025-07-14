from flask import Blueprint, request, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os

from promo.builders import generate_promo_insert, generate_device_inserts
from services.orbit import fetch_promo_line
from services.devices import load_devices_from_excel, filter_eligible
from db import engine

promo_bp = Blueprint(
    'promo',
    __name__,
    template_folder='templates/promo',
    url_prefix='/promo'
)

@promo_bp.route('/new', methods=['GET', 'POST'])
def new_promo():
    if request.method == 'POST':
        # 1. Fetch promo data from Orbit
        promo_id = request.form['promo_id']
        promo_data = fetch_promo_line(promo_id)

        # 2. Apply any user overrides from the form
        for field in ('loan_sku_grp', 'mk_mdl_grp_id', 'tradein_amount', 'description'):
            if request.form.get(field):
                promo_data[field] = request.form[field]

        # 3. Handle SKU Excel upload
        sku_file = request.files.get('sku_file')
        if not sku_file:
            flash("Please upload a SKU file.", "error")
            return redirect(url_for('promo.new_promo'))

        filename = secure_filename(sku_file.filename)
        temp_path = os.path.join('/tmp', filename)
        sku_file.save(temp_path)

        # 4. Load & filter devices
        df = load_devices_from_excel(temp_path)
        df_eligible = filter_eligible(df)

        # 5. Generate SQL statements
        promo_sql = generate_promo_insert(promo_data)
        device_sqls = generate_device_inserts(
            promo_data['trade_in_grp_id'],
            df_eligible.to_dict(orient='records')
        )

        # 6a. Preview mode
        if request.form.get('preview'):
            return render_template(
                'promo/promo_preview.html',
                promo_sql=promo_sql,
                device_sqls=device_sqls
            )

        # 6b. Commit mode
        elif request.form.get('commit'):
            try:
                with engine.begin() as conn:
                    conn.execute(promo_sql)
                    for stmt in device_sqls:
                        conn.execute(stmt)
                flash(f"Promo {promo_id} committed successfully!", "success")
            except Exception as e:
                flash(f"Error committing promo: {e}", "error")
            return redirect(url_for('promo.new_promo'))

    # GET request: render the blank form
    return render_template('promo/promo_form.html')