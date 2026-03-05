import os
import re
import sys
from typing import List

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def validate_blueprint_only() -> int:
    route_pattern = re.compile(r"@\s*app\s*\.\s*route\s*\(")
    legacy_files = []
    failures: List[str] = []

    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", "venv", "__pycache__", ".pytest_cache"}]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, filename)
            relative_path = os.path.relpath(filepath, REPO_ROOT)
            if relative_path.startswith("tests"):
                continue

            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except OSError as exc:
                failures.append(f"Unable to read {relative_path}: {exc}")
                continue

            if route_pattern.search(content):
                legacy_files.append(relative_path)

    if legacy_files:
        for relative_path in sorted(legacy_files):
            failures.append(f"Legacy @app.route decorator found in {relative_path}")

    if failures:
        print("Endpoint validator failed:\n")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Endpoint validator passed: no legacy @app.route decorators found.")
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "blueprint"

    if mode != "blueprint":
        print("Usage: python tools/validate_endpoints.py blueprint")
        return 2

    return validate_blueprint_only()


if __name__ == "__main__":
    raise SystemExit(main())
