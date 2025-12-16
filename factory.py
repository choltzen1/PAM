import os
from flask import Flask, request
import base64, json
from dotenv import load_dotenv
from datetime import datetime
import urllib3

from promo.routes import promo_bp, init_data_manager as init_promo_data_manager
from admin.routes import admin_bp, init_data_manager as init_admin_data_manager
from core import core_bp
from api.routes import api_bp, init_data_manager as init_api_data_manager
from jira.routes import jira_bp
from data.storage import PromoDataManager
from research import research_bp
import threading
import time

_loaded_env = load_dotenv()
print(f"[startup] .env loaded={_loaded_env} ORBIT_DB_SERVER={os.getenv('ORBIT_DB_SERVER')} ORBIT_DB_DATABASE={os.getenv('ORBIT_DB_DATABASE')} PAM_DB_SERVER={os.getenv('PAM_DB_SERVER')} PAM_DB_DATABASE={os.getenv('PAM_DB_DATABASE')}")
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
    # Avoid using Unicode symbols that can break in certain Windows code pages.
    print("DB-only promo data manager initialized (JSON disabled for RDC)")

    # Register blueprints
    app.register_blueprint(core_bp)
    app.register_blueprint(promo_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(jira_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(research_bp)

    # Initialize data manager in blueprints
    init_promo_data_manager(data_manager)
    init_admin_data_manager(data_manager)
    init_api_data_manager(data_manager)

    # Legacy alias tracking removed after full blueprint migration.

    # Kick off background warm-up to reduce first-request latency
    try:
        t = threading.Thread(target=_warm_app_cache, args=(data_manager,), daemon=True)
        t.start()
    except Exception:
        pass

    @app.context_processor
    def inject_current_datetime():  # type: ignore
        return {'current_datetime': datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")}

    @app.context_processor
    def inject_theme():  # type: ignore
        cookie_mode = request.cookies.get('theme')
        # Only allow light/dark/auto, default auto
        raw = cookie_mode if cookie_mode in ('light','dark','auto') else 'auto'
        resolved = raw if raw in ('light','dark') else 'auto'
        return {
            'server_theme': raw,
            'server_theme_resolved': resolved
        }

    def _extract_user_name(req: request) -> str | None:
        """Extract display name from Azure App Service Easy Auth headers.
        Preference order: givenname+surname -> name -> preferred_username/email -> header fallback.
        """
        try:
            b64 = req.headers.get('X-MS-CLIENT-PRINCIPAL')
            if b64:
                try:
                    decoded = base64.b64decode(b64)
                    payload = json.loads(decoded.decode('utf-8'))
                    claims = payload.get('claims', [])
                    def claim(key: str):
                        for c in claims:
                            if c.get('typ') == key:
                                return c.get('val')
                        return None
                    given = claim('givenname') or claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname')
                    surname = claim('surname') or claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname')
                    full = None
                    if (given or surname):
                        gn = (given or '').strip()
                        sn = (surname or '').strip()
                        full = f"{gn} {sn}".strip()
                    name = claim('name') or claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name')
                    if not full:
                        full = name
                    if not full:
                        preferred = claim('preferred_username') or claim('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress') or claim('emailaddress')
                        full = preferred
                    if full:
                        return full
                except Exception:
                    pass
            # Fallback simple header
            simple = req.headers.get('X-MS-CLIENT-PRINCIPAL-NAME')
            if simple:
                # Try to convert email to First Last if we also have given/surname in individual headers
                return simple
        except Exception:
            pass
        return None

    @app.context_processor
    def inject_user():  # type: ignore
        try:
            uname = _extract_user_name(request)
            return {'user_name': uname}
        except Exception:
            return {'user_name': None}

    return app

def _warm_app_cache(dm: PromoDataManager):
    """Background warm-up: establish DB connection and prefetch homepage payload."""
    try:
        # Ensure connection is established early (reduces first-request latency)
        dm.db_manager.test_connection()
        # Preload base homepage data (page 1, no filters) into admin cache
        try:
            from admin import routes as admin_routes
            payload = dm.get_paginated_execution_type(
                execution_type='RDC', page=1, per_page=25, search='', owner_filter='all'
            )
            admin_routes._PAM_PROMO_CACHE = {'ts': time.time(), 'data': payload}
            # Warm owners cache from payload if available
            if payload and payload.get('owners'):
                admin_routes._OWNERS_CACHE = {'ts': time.time(), 'data': payload.get('owners')}
        except Exception:
            pass
        # Periodic refresher loop (every 5 minutes)
        while True:
            try:
                from admin import routes as admin_routes
                payload = dm.get_paginated_execution_type(
                    execution_type='RDC', page=1, per_page=25, search='', owner_filter='all'
                )
                admin_routes._PAM_PROMO_CACHE = {'ts': time.time(), 'data': payload}
                if payload and payload.get('owners'):
                    admin_routes._OWNERS_CACHE = {'ts': time.time(), 'data': payload.get('owners')}
            except Exception:
                pass
            time.sleep(300)
    except Exception:
        # Non-fatal warm-up failures shouldn't block app startup
        pass

__all__ = ['create_app','data_manager']
