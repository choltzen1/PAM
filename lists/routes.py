from flask import Blueprint, render_template
from auth import role_required

lists_bp = Blueprint('lists', __name__, url_prefix='/lists')


@lists_bp.route('/')
@role_required('pam_users')
def index():
    return render_template('lists/lists_home.html')


@lists_bp.route('/sku')
@role_required('pam_users')
def sku_lists():
    return render_template('lists/sku_lists.html')


@lists_bp.route('/tradein')
@role_required('pam_users')
def tradein_lists():
    return render_template('lists/tradein_lists.html')
