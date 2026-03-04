# UI/CSS Refactor Tracking (Source of Truth)

This file tracks the ongoing HTML/CSS refactor work.

Goals:
- Zero functional changes.
- Zero unintentional UI drift (visual snapshots must match baseline).
- No inline CSS in templates.
- No visual inline styling in JS (no `style.cssText` / no `.style.<prop>` for colors/spacing/typography).

## How to Update
- Every PR that touches templates/CSS/JS must update this tracker.
- Keep entries small and scoped; link to the PR.

## Status Legend
- Not Started
- In Progress
- Done
- Blocked

## Work Items

| ID | Area | Summary | Status | Risk | Owner | PR | Notes |
|---:|------|---------|--------|------|-------|----|------|
| 1 | Offers | Remove offers workspace route/templates/role/docs | Done | Low |  |  | Completed in `cssrefactor` branch |
| 2 | Guardrails | Add inline CSS/JS regression tests (baseline-based) | Done | Medium |  |  | Baseline generated in `tests/baselines/frontend_guardrails.json` |
| 3 | Docs | Add frontend standards + how-to + checklist + components | Done | Low |  |  | Added in `docs/` |
| 4 | Tracking UI | Add admin page rendering tracking JSON | Done | Low |  |  | Route: `/admin/ui-refactor` |
| 5 | Landing | Remove inline CSS from landing templates; scope styles in landing.css | Done | Medium |  |  | Scoped by body classes to avoid impacting `/research` |
| 6 | Research | Remove inline CSS from research templates; migrate to research.css/pete.css | Done | Medium |  |  | Scoped by body classes (`research--home`, `research--pete`) |
| 7 | Base templates | Create shared base + partials; dedupe header/footer/theme | Done | High |  |  | Shared partials in `templates/partials/`; base templates updated |
| 8 | Footer | Make footer icons visible in light mode | Done | Low |  |  | Footer link color now magenta in light mode |
| 9 | PAM placeholders | Remove inline CSS from PAM placeholder templates; migrate to pam_placeholders.css | Done | Low |  |  | Linked `static/css/pam_placeholders.css` via `extra_css` |
| 10 | Reviewers | Remove inline CSS from reviewers.html; migrate into reviewers.css | Done | Medium |  |  | Removed inline `<style>` block + style attributes |
| 11 | Edit RDC | Remove inline CSS from edit_rdc.html; migrate into edit_rdc.css/jira_modal.css | Done | Medium |  |  | Replaced inline styles with classes + CSS rules |
| 12 | Edit SPE | Remove inline CSS from edit_spe.html; migrate into edit_spe.css | Done | Low |  |  | SMS fields now use class-based `display: contents` and class toggling |
| 13 | Admin dashboard | Remove redundant inline style from admin.html | Done | Low |  |  | `.small-hint` now purely class-based (admin.css) |
| 14 | Admin groupings | Remove inline CSS from admin_groupings.html; migrate into admin_groupings.css | Done | Medium |  |  | Inline styles and `.style.display` toggles replaced with classes |
| 15 | Admin PAM promotions | Remove inline CSS from admin_pam_promotions.html; migrate into admin.css | Done | Medium |  |  | Inline styles removed; status/empty-row styling now class-based |
| 16 | Get Promo Codes | Remove inline CSS from get_promo_codes.html; migrate into get_promo_codes.css | Done | Low |  |  | Control layout + Orbit input width now class-based |
| 17 | Date mismatch | Remove inline CSS from date_mismatch.html; migrate into date_mismatch.css | Done | Medium |  |  | SQL preview container/textarea styling now class-based |
| 18 | Version history | Remove inline CSS from version_history.html; migrate into version_history.css | Done | Low |  |  | Per-page pagination form now styled via CSS |
| 19 | Capacity | Remove inline CSS from capacity.html dynamic row-count; keep layout | Done | Low |  |  | `--row-count` now set via `data-row-count` + script |
| 20 | Research JS | Remove inline styles from research.js; use hidden + CSS classes | Done | Low |  |  | Query console toggle now uses `hidden`; clickable rows now use `.research-clickable-row` in research.css |
| 21 | JIRA modal JS | Remove inline styles from jira_modal.js; migrate to jira_modal.css | Done | Medium |  |  | Modal show/hide uses `is-hidden`; toast/preview overlay styles moved from JS to CSS |
| 22 | PAM base | Remove runtime <style> injection from pam_base.html | Done | Low |  |  | Removed redundant caret-color style injection (covered by global.css) |
| 23 | Legacy cleanup | Remove misplaced Streamlit PETE script under templates | Done | Low |  |  | Deleted `templates/research/pete.py`; Flask PETE is `templates/research/pete.html` |
| 24 | Approval email | Remove inline style from rejection email body | Done | Low |  |  | Removed inline color styling from `rejection_body` HTML in promo/routes.py |

## Baseline Files
- Machine-readable tracker: `docs/ui_refactor_tracking.json`
- Standards: `docs/FRONTEND_STANDARDS.md`
