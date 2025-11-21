from flask import Blueprint, render_template, redirect, url_for

core_bp = Blueprint('core', __name__)

@core_bp.route('/', endpoint='home')
def home_page():
    return redirect(url_for('core.landing'))

@core_bp.route('/PAM_homepage', endpoint='PAM_homepage')
def pam_homepage():
    """Primary navigation landing page (formerly index)."""
    return render_template('pam/PAM_homepage.html')

@core_bp.route('/landing', endpoint='landing')
def landing_page():
    """Primary entry landing page (workspace hub) with three selectable workspaces."""
    hub_name = "Workspace Hub"
    tiles = [
        {
            'key': 'pam',
            'label': 'PAM',
            'icon': 'bi-grid-3x3-gap-fill',
            'url': url_for('core.PAM_homepage'),
            'ribbon': 'Live',
            'sub': 'Promo & Workflow'
        },
        {
            'key': 'offers',
            'label': 'Offers',
            'icon': 'bi-gift-fill',
            'url': url_for('core.offers_workspace'),
            'ribbon': 'Preview',
            'sub': 'Placeholder'
        },
        {
            'key': 'research',
            'label': 'Research',
            'icon': 'bi-search-heart',
            'url': url_for('research.index'),
            'ribbon': 'Alpha',
            'sub': 'Data & Eligibility'
        }
    ]
    objective = (
        "Choose a workspace. Pam and Research are in an Alpha and active development stage. Offers is a current placeholder." )
    return render_template('landing.html', tiles=tiles, objective=objective, hub_name=hub_name)

@core_bp.route('/theme', methods=['GET','POST'], endpoint='set_theme')
def set_theme():
    """Persist user theme choice (light/dark/auto) in a cookie.
    Returns JSON describing the saved mode. LocalStorage will also be used client-side for first-paint override.
    """
    from flask import request, make_response, jsonify
    mode = request.values.get('mode','auto')
    if mode not in ('light','dark','auto'):
        mode = 'auto'
    resp = make_response(jsonify(success=True, mode=mode))
    # 1 year persistence
    resp.set_cookie('theme', mode, max_age=60*60*24*365, samesite='Lax')
    return resp

@core_bp.route('/offers', endpoint='offers_workspace')
def offers_workspace():
    # Updated to new offers workspace hub layout (similar to research workspace)
    return render_template('offers/placeholder.html')

# Research workspace handled by research blueprint (/research)

__all__ = ['core_bp']
