from flask import Blueprint, render_template

core_bp = Blueprint('core', __name__)

@core_bp.route('/', endpoint='home')
def home_page():  # provides namespaced home
    return render_template('index.html')

__all__ = ['core_bp']
