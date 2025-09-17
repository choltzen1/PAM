import os, re

ALLOWED_SINGLE = {'static'}  # implicit blueprint provided by Flask
# core.home is allowed but already namespaced; this test flags only bare names without a dot
PATTERN = re.compile(r"url_for\('([^']+)'")

IGNORED_FILES = {
}

ROOT = os.path.dirname(os.path.dirname(__file__))


def test_no_unnamespaced_url_for_calls():
    violations = []
    templates_dir = os.path.join(ROOT, 'templates')
    for dirpath, _, filenames in os.walk(templates_dir):
        for fname in filenames:
            if not fname.endswith('.html'): continue
            path = os.path.join(dirpath, fname)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for match in PATTERN.finditer(content):
                endpoint = match.group(1)
                if '.' not in endpoint and endpoint not in ALLOWED_SINGLE:
                    violations.append((path.replace(ROOT+os.sep, ''), endpoint))
    if violations:
        details = '\n'.join(f"{p}: {ep}" for p, ep in violations)
        raise AssertionError(f"Found un-namespaced endpoint usages in templates:\n{details}")
