from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for
from .services import (
    get_main_data,
    get_promo_error_reasons,
    get_rate_plan_data,
    get_active_aal_lines,
    get_trade_data_qr,
    get_eip_ids_by_ban,
    get_eip_ids_by_msisdn,
    get_promo_eligibility_context,
    deduplicate_columns,
    extract_promo_code,
    generate_pete_response,
)

research_bp = Blueprint('research', __name__, url_prefix='/research')

@research_bp.route('/')
def index():
    return render_template('research/research_home.html')

from .pete_workflow import (
    ensure_session_defaults,
    run_eip_lookup,
    run_ban_to_eip_list,
    run_selected_eip,
    process_chat,
    gather_template_context,
)

@research_bp.route('/pete', methods=['GET', 'POST'])
def pete():
    ensure_session_defaults()
    # If this is a plain GET (no POST redirect) we clear prior query state so page loads blank
    if request.method == 'GET':
        # Skip clearing if this GET is the redirect after a POST (PRG pattern)
        if not session.pop('pete_just_posted', False):
            for k in ["df_main","promo_errors","rate_plans","aal_lines","trade_data","eip_list","used_ban","eip_id","order_ids"]:
                session.pop(k, None)
            session["trade_query_attempted"] = False
    if request.method == 'POST':
        form_name = request.form.get('form_name','')
        if form_name == 'chat_form':
            prompt = request.form.get('prompt','')
            process_chat(prompt)
            session['pete_just_posted'] = True
            return redirect(url_for('research.pete'))
        if form_name == 'data_form':
            mode = request.form.get('has_eip','Yes')
            if request.form.get('action') == 'run_lookup_from_select':
                selected = request.form.get('selected_eip','').strip()
                if selected:
                    run_selected_eip(selected)
                session['pete_just_posted'] = True
                return redirect(url_for('research.pete'))
            if mode == 'Yes':
                eip_id = request.form.get('eip_id','').strip()
                if eip_id:
                    run_eip_lookup(eip_id)
            else:
                ban = request.form.get('ban','').strip()
                if ban:
                    run_ban_to_eip_list(ban)
            session['pete_just_posted'] = True
            return redirect(url_for('research.pete'))
    ctx = gather_template_context()
    return render_template('research/pete.html', **ctx)

@research_bp.route('/api/main-data')
def api_main_data():
    eip_id = request.args.get('eip_id','').strip()
    if not eip_id:
        return jsonify({'error':'eip_id required'}), 400
    df = get_main_data(eip_id)
    return jsonify({'rows': df.to_dict(orient='records'), 'count': len(df)})

@research_bp.route('/api/promo-error-reasons')
def api_promo_error_reasons():
    eip_id = request.args.get('eip_id','').strip()
    if not eip_id:
        return jsonify({'error':'eip_id required'}), 400
    df = get_promo_error_reasons(eip_id)
    return jsonify({'rows': df.to_dict(orient='records'), 'count': len(df)})

@research_bp.route('/api/rate-plans')
def api_rate_plans():
    ban = request.args.get('ban','').strip()
    if not ban:
        return jsonify({'error':'ban required'}), 400
    df = get_rate_plan_data(ban)
    return jsonify({'rows': df.to_dict(orient='records'), 'count': len(df)})

@research_bp.route('/api/aal-lines')
def api_aal_lines():
    ban = request.args.get('ban','').strip()
    if not ban:
        return jsonify({'error':'ban required'}), 400
    df = get_active_aal_lines(ban)
    return jsonify({'rows': df.to_dict(orient='records'), 'count': len(df)})

@research_bp.route('/api/trade-data-qr')
def api_trade_data_qr():
    raw = request.args.get('order_ids','').strip()
    if not raw:
        return jsonify({'rows': [], 'count': 0})
    order_ids = [x for x in raw.split(',') if x.strip()]
    df = get_trade_data_qr(order_ids)
    return jsonify({'rows': df.to_dict(orient='records'), 'count': len(df)})

@research_bp.route('/api/eip-by-ban')
def api_eip_by_ban():
    ban = request.args.get('ban','').strip()
    if not ban:
        return jsonify({'error':'ban required'}), 400
    df = get_eip_ids_by_ban(ban)
    return jsonify({'rows': df.to_dict(orient='records'), 'count': len(df)})

@research_bp.route('/api/eip-identify')
def api_eip_identify():
    """Unified identification endpoint. Provide either ban=<ban> or msisdn=<msisdn>.
    Returns list of EIP accounts with BAN + MSISDN for selection. Prioritizes BAN if both given.
    """
    ban = request.args.get('ban','').strip()
    msisdn = request.args.get('msisdn','').strip()
    if not ban and not msisdn:
        return jsonify({'error': 'ban or msisdn required'}), 400
    if ban:
        df = get_eip_ids_by_ban(ban)
    else:
        df = get_eip_ids_by_msisdn(msisdn)
    return jsonify({'rows': df.to_dict(orient='records'), 'count': len(df), 'ban': ban, 'msisdn': msisdn})

@research_bp.route('/api/promo-eligibility')
def api_promo_eligibility():
    promo_code = request.args.get('promo_code','').strip().upper()
    if not promo_code:
        return jsonify({'error':'promo_code required'}), 400
    df = get_promo_eligibility_context(promo_code)
    df = deduplicate_columns(df)
    return jsonify({'rows': df.to_dict(orient='records'), 'count': len(df)})

@research_bp.route('/api/extract-promo-code', methods=['POST'])
def api_extract_promo_code():
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get('prompt','')
    code = extract_promo_code(prompt)
    return jsonify({'promo_code': code})

@research_bp.route('/api/pete/chat', methods=['POST'])
def api_pete_chat():
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get('prompt','')
    promo_code = extract_promo_code(prompt or '')
    eligibility_df = get_promo_eligibility_context(promo_code) if promo_code else None
    if eligibility_df is not None:
        eligibility_df = deduplicate_columns(eligibility_df)
    reply = generate_pete_response(prompt, eligibility_df)
    return jsonify({'prompt': prompt, 'promo_code': promo_code, 'reply': reply})

@research_bp.route('/api/pete/aggregate')
def api_pete_aggregate():
    """Aggregate data pull similar to original PETE flow: eip -> promo errors, trade, rate plans, lines."""
    eip_id = request.args.get('eip_id','').strip()
    ban = request.args.get('ban','').strip()
    promo_code = request.args.get('promo_code','').strip().upper()
    payload = {}
    if eip_id:
        main_df = get_main_data(eip_id)
        payload['main'] = main_df.to_dict(orient='records')
        payload['main_count'] = len(main_df)
        errors_df = get_promo_error_reasons(eip_id)
        payload['errors'] = errors_df.to_dict(orient='records')
        payload['errors_count'] = len(errors_df)
        order_ids = []
        if 'ORDER_DETAIL_ID' in main_df.columns:
            order_ids = [str(x) for x in main_df['ORDER_DETAIL_ID'].dropna().unique()]
        if order_ids:
            trade_df = get_trade_data_qr(order_ids)
            payload['trade'] = trade_df.to_dict(orient='records')
            payload['trade_count'] = len(trade_df)
        # derive BAN if not provided
        if not ban and 'BAN' in main_df.columns and not main_df['BAN'].dropna().empty:
            ban = str(main_df['BAN'].dropna().iloc[0])
    if ban:
        rate_df = get_rate_plan_data(ban)
        payload['rate_plans'] = rate_df.to_dict(orient='records')
        payload['rate_plans_count'] = len(rate_df)
        aal_df = get_active_aal_lines(ban)
        payload['aal_lines'] = aal_df.to_dict(orient='records')
        payload['aal_lines_count'] = len(aal_df)
    if promo_code:
        elig_df = get_promo_eligibility_context(promo_code)
        elig_df = deduplicate_columns(elig_df)
        payload['eligibility'] = elig_df.to_dict(orient='records')
        payload['eligibility_count'] = len(elig_df)
    payload['ban'] = ban
    payload['eip_id'] = eip_id
    payload['promo_code'] = promo_code
    return jsonify(payload)
