import sys
import os
import json
from flask import url_for

"""Blueprint-only endpoint validator.

This simplified validator enforces that:
 1. No legacy (pre-blueprint) endpoint names are present.
 2. Required blueprint endpoints exist and can build URLs.

Exit codes:
 0 = success
 1 = missing required blueprint endpoint
 2 = legacy endpoint unexpectedly present
"""

# Legacy endpoint names that must no longer resolve
LEGACY_ENDPOINTS = [
    'promotions','spe','rebates','date_mismatch','get_promo_codes','approvers','reviewers',
    'links','updates','capacity','test','admin','version_history','download_file','download_sql',
    'create_jira_ticket','clear_trade_data','clear_tiers_data','clear_segment_data'
]

# Required blueprint endpoints (add here if new critical pages introduced)
REQUIRED_BLUEPRINT_ENDPOINTS = [
    'promo.promotions_page',
    'promo.rebates_page',
    'promo.date_mismatch_page',
    'promo.get_promo_codes_page',
    'promo.approvers_page',
    'promo.reviewers_page',
    'promo.links_main_page',
    'admin_bp.dashboard',
    'admin_bp.version_history_page',
    'api.get_promo_details'
]

def run_validation(app):
    legacy_failures = []
    missing_blueprints = []
    ctx = app.test_request_context('/')
    ctx.push()
    try:
        for ep in LEGACY_ENDPOINTS:
            try:
                url_for(ep)
                legacy_failures.append(ep)
            except Exception:
                pass
        for ep in REQUIRED_BLUEPRINT_ENDPOINTS:
            try:
                url_for(ep)
            except Exception as e:
                missing_blueprints.append({'endpoint': ep, 'error': str(e)})
    finally:
        ctx.pop()

    status = 0
    if legacy_failures:
        status = 2
    if missing_blueprints:
        status = 1 if status == 0 else status

    report = {
        'legacy_unexpected': legacy_failures,
        'missing_blueprint': missing_blueprints,
        'status': status
    }
    print(json.dumps(report, indent=2))
    sys.exit(status)

def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault('PAM_VALIDATION_MODE', '1')
    from app import app  # type: ignore
    run_validation(app)

if __name__ == '__main__':
    main()
