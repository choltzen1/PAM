# Frontend How-To

## Add a New Page
1. Template: extend the appropriate base (`pam/base_pam.html` for PAM pages).
2. CSS:
   - Prefer existing shared components in `static/css/global.css`.
   - Add page-specific CSS only if necessary.
3. JS:
   - No inline scripts for new code.
   - No visual styling via `.style`/`cssText`; toggle state classes/`hidden` only.
4. Tests:
   - If the page is core, add it to the route smoke test list.
   - If it’s user-facing, add a Playwright snapshot.

## Update Shared Components
- Update `docs/FRONTEND_COMPONENTS.md` with what changed.
- Update `docs/UI_REFACTOR_TRACKING.md` and `docs/ui_refactor_tracking.json`.

## Update Guardrail Baseline
If you intentionally reduce inline styles (preferred) or need to make a rare exception:
- Run `python scripts/generate_frontend_guardrails_baseline.py`
- Commit the updated `tests/baselines/frontend_guardrails.json`
