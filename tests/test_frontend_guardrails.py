from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tests" / "baselines" / "frontend_guardrails.json"


RE_STYLE_ATTR = re.compile(r"\bstyle\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
RE_STYLE_TAG = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
RE_JS_STYLE = re.compile(r"\.style\b")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _compute_current_counts() -> dict[str, dict[str, int]]:
    templates_root = REPO_ROOT / "templates"
    static_root = REPO_ROOT / "static"

    # Template rules
    template_style_attr: dict[str, int] = {}
    template_style_tag: dict[str, int] = {}

    for path in templates_root.rglob("*.html"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = _read_text(path)
        template_style_attr[rel] = len(RE_STYLE_ATTR.findall(text))
        template_style_tag[rel] = len(RE_STYLE_TAG.findall(text))

    # JS rule
    js_style_api: dict[str, int] = {}
    for pattern in ("*.js", "*.mjs"):
        for path in static_root.rglob(pattern):
            rel = path.relative_to(REPO_ROOT).as_posix()
            text = _read_text(path)
            js_style_api[rel] = len(RE_JS_STYLE.findall(text))

    # Keep output small.
    template_style_attr = {k: v for k, v in template_style_attr.items() if v > 0}
    template_style_tag = {k: v for k, v in template_style_tag.items() if v > 0}
    js_style_api = {k: v for k, v in js_style_api.items() if v > 0}

    return {
        "template_style_attr": template_style_attr,
        "template_style_tag": template_style_tag,
        "js_style_api": js_style_api,
    }


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        raise AssertionError(
            "Missing guardrail baseline. Generate it with: "
            "python scripts/generate_frontend_guardrails_baseline.py"
        )
    return json.loads(_read_text(BASELINE_PATH))


@pytest.mark.parametrize(
    "rule_key, human_name",
    [
        ("template_style_attr", "inline style= attributes"),
        ("template_style_tag", "<style> blocks"),
        ("js_style_api", "JS .style usage"),
    ],
)
def test_frontend_guardrails_no_increase(rule_key: str, human_name: str) -> None:
    """Prevent adding *new* inline CSS / JS styling during the refactor.

    This is a baseline-based check: it allows existing violations but fails if
    any file's count increases compared to the committed baseline.
    """

    baseline = _load_baseline()
    baseline_counts: dict[str, int] = baseline.get("counts", {}).get(rule_key, {})

    current_counts = _compute_current_counts()[rule_key]

    regressions: list[tuple[str, int, int]] = []
    for path, current in current_counts.items():
        allowed = int(baseline_counts.get(path, 0))
        if current > allowed:
            regressions.append((path, allowed, current))

    # Ignore baseline entries for deleted files.

    if regressions:
        details = "\n".join(
            f"- {p}: baseline={a}, current={c}" for p, a, c in sorted(regressions)
        )
        raise AssertionError(
            f"Frontend guardrail regression: added {human_name}.\n{details}\n\n"
            "If this increase is intentional (it usually shouldn't be), "
            "regenerate the baseline with: python scripts/generate_frontend_guardrails_baseline.py"
        )
