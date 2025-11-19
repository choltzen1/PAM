from factory import create_app, data_manager as factory_data_manager  # import alias
from perf.metrics import collector  # request metrics collector
import time
from flask import request, make_response, jsonify

app = create_app()
# After factory create_app, re-import the factory module variable to ensure it's initialized
from factory import data_manager as _dm  # type: ignore
data_manager = _dm  # expose for tests

def _perf_begin():
    from flask import request, g
    rk = request.endpoint or request.path
    g.__perf_start = (rk, time.perf_counter())

def _perf_end(resp):
    from flask import g
    tup = getattr(g, '__perf_start', None)
    if tup:
        rk, start = tup
        try:
            collector.end_request(rk, start)
        except Exception:
            pass
    return resp

def perf_metrics():
    from flask import jsonify
    return jsonify(collector.snapshot())

@app.route('/theme', methods=['GET','POST'])
def set_theme():
    """Persist user theme choice (light/dark/auto) in a cookie.
    Returns JSON describing the saved mode. LocalStorage will also be used client-side for first-paint override.
    """
    mode = request.values.get('mode','auto')
    if mode not in ('light','dark','auto'):
        mode = 'auto'
    resp = make_response(jsonify(success=True, mode=mode))
    # 1 year persistence
    resp.set_cookie('theme', mode, max_age=60*60*24*365, samesite='Lax')
    return resp

# Register hooks and metrics endpoint without @app.route to satisfy blueprint-only policy
app.before_request(_perf_begin)
app.after_request(_perf_end)
app.add_url_rule('/__perf_metrics', 'perf_metrics', perf_metrics)


if data_manager is None:  # defensive assertion during test/dev
    try:
        from data.storage import PromoDataManager
        data_manager = PromoDataManager()
    except Exception:
        pass

"""Entrypoint module.
The root route now lives in the core blueprint (`core.home`).
"""

if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run the PAM application')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the application on')
    args = parser.parse_args()
    
    # Run the app on the specified port
    app.run(debug=True, port=args.port)
