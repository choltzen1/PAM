import os, re

ROOT = os.path.dirname(os.path.dirname(__file__))
APP_ROUTE_PATTERN = re.compile(r"@app\.route\(")
ALLOWED_FILES = {os.path.join(ROOT, 'app.py')}  # entrypoint allowed for zero or minimal usage


def test_no_direct_app_route_decorators():
    violations = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # prune external / environment dirs
        dirnames[:] = [d for d in dirnames if d not in {'venv','env','__pycache__','.git'}]
        for fname in filenames:
            if not fname.endswith('.py'): continue
            path = os.path.join(dirpath, fname)
            if path in ALLOWED_FILES:
                # We optionally allow zero @app.route occurrences in app.py now; flag if any found.
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    if APP_ROUTE_PATTERN.search(f.read()):
                        violations.append(path.replace(ROOT+os.sep,''))
                continue
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                if APP_ROUTE_PATTERN.search(f.read()):
                    violations.append(path.replace(ROOT+os.sep,''))
    if violations:
        raise AssertionError('Direct @app.route usage detected; use blueprints instead:\n' + '\n'.join(violations))
