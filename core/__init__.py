from flask import Blueprint, render_template, redirect, url_for

core_bp = Blueprint('core', __name__)

@core_bp.route('/', endpoint='home')
def home_page():  # legacy root path retained; redirect to new named homepage
    return redirect(url_for('core.PAM_homepage'))

@core_bp.route('/PAM_homepage', endpoint='PAM_homepage')
def pam_homepage():
    """Primary navigation landing page (formerly index)."""
    return render_template('PAM_homepage.html')

__all__ = ['core_bp']
