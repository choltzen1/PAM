import os, re, sys

ROOT = os.path.dirname(os.path.dirname(__file__))
PATTERN = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
ALLOWED = {'static'}  # Flask implicit static endpoint

IGNORED_DIRS = {'venv', 'env', '__pycache__', '.git'}


def test_no_unnamespaced_url_for_in_python():
    violations = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for fname in filenames:
            if not fname.endswith('.py'): continue
            # Skip tools validator itself (explicitly working with legacy names historically)
            if fname == 'validate_endpoints.py':
                continue
            path = os.path.join(dirpath, fname)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for m in PATTERN.finditer(content):
                ep = m.group(1)
                if '.' not in ep and ep not in ALLOWED:
                    violations.append(f"{path.replace(ROOT+os.sep,'')}: {ep}")
    if violations:
        raise AssertionError("Un-namespaced url_for endpoints in Python files:\n" + '\n'.join(violations))
