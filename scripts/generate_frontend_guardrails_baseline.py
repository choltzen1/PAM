"""Generate baseline counts for frontend guardrail tests.

This is intentionally a *counts-based* baseline so that:
- existing legacy inline styles don't fail CI immediately
- CI fails only when a change increases inline styles / JS style usage

Run:
  python scripts/generate_frontend_guardrails_baseline.py

It writes:
  tests/baselines/frontend_guardrails.json
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


RE_STYLE_ATTR = re.compile(r"\bstyle\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
RE_STYLE_TAG = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
RE_JS_STYLE = re.compile(r"\.style\b")


def _iter_files(root: Path, patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(root.glob(pattern))
    out: list[Path] = []
    for f in files:
        if not f.is_file():
            continue
        parts = {p.lower() for p in f.parts}
        if "__pycache__" in parts:
            continue
        out.append(f)
    return sorted(set(out))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def compute_baseline(repo_root: Path) -> dict:
    templates_root = repo_root / "templates"
    static_root = repo_root / "static"

    template_files = _iter_files(templates_root, ["**/*.html", "**/*.htm"])
    js_files = _iter_files(static_root, ["**/*.js", "**/*.mjs"])

    style_attr_counts: dict[str, int] = {}
    style_tag_counts: dict[str, int] = {}
    js_style_counts: dict[str, int] = {}

    for f in template_files:
        rel = f.relative_to(repo_root).as_posix()
        text = _read_text(f)
        style_attr_counts[rel] = len(RE_STYLE_ATTR.findall(text))
        style_tag_counts[rel] = len(RE_STYLE_TAG.findall(text))

    for f in js_files:
        rel = f.relative_to(repo_root).as_posix()
        text = _read_text(f)
        js_style_counts[rel] = len(RE_JS_STYLE.findall(text))

    # Keep baseline small by storing only files with any hits.
    style_attr_counts = {k: v for k, v in style_attr_counts.items() if v > 0}
    style_tag_counts = {k: v for k, v in style_tag_counts.items() if v > 0}
    js_style_counts = {k: v for k, v in js_style_counts.items() if v > 0}

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rules": {
            "template_style_attr": {
                "description": "Count of style= attributes in templates",
            },
            "template_style_tag": {
                "description": "Count of <style>...</style> blocks in templates",
            },
            "js_style_api": {
                "description": "Count of '.style' usages in static JS files",
            },
        },
        "counts": {
            "template_style_attr": dict(sorted(style_attr_counts.items())),
            "template_style_tag": dict(sorted(style_tag_counts.items())),
            "js_style_api": dict(sorted(js_style_counts.items())),
        },
        "totals": {
            "template_style_attr": sum(style_attr_counts.values()),
            "template_style_tag": sum(style_tag_counts.values()),
            "js_style_api": sum(js_style_counts.values()),
        },
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    baseline_path = repo_root / "tests" / "baselines" / "frontend_guardrails.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)

    baseline = compute_baseline(repo_root)
    baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    print(f"Wrote baseline: {baseline_path}")
    print("Totals:")
    for k, v in baseline.get("totals", {}).items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
