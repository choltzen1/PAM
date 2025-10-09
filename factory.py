import os
from flask import Flask
from dotenv import load_dotenv
from datetime import datetime
import urllib3

from promo.routes import promo_bp, init_data_manager as init_promo_data_manager
from admin.routes import admin_bp, init_data_manager as init_admin_data_manager
from core import core_bp
from api.routes import api_bp, init_data_manager as init_api_data_manager
from jira.routes import jira_bp
from data.storage import PromoDataManager

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

data_manager = None  # will be initialized in create_app

def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = 'your-secret-key-here'

    if config:
        app.config.update(config)

    global data_manager
    # Single initialization path (DB-only model); validation mode no longer diverges
    data_manager = PromoDataManager()
    print("✅ DB-only promo data manager initialized (JSON disabled for RDC)")

    # Register blueprints
    app.register_blueprint(core_bp)
    app.register_blueprint(promo_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(jira_bp)
    app.register_blueprint(api_bp)

    # Initialize data manager in blueprints
    init_promo_data_manager(data_manager)
    init_admin_data_manager(data_manager)
    init_api_data_manager(data_manager)

    # Legacy alias tracking removed after full blueprint migration.

    @app.context_processor
    def inject_current_datetime():  # type: ignore
        return {'current_datetime': datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")}

    return app

__all__ = ['create_app','data_manager']
