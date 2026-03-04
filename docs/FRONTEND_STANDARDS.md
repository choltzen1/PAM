# Frontend Standards (HTML/CSS/JS)

Audience: internal dev team.

## Non-Negotiables
- No functional changes in refactor PRs unless explicitly stated.
- Zero unintentional UI drift: Playwright snapshots must match baseline.
- No inline CSS in templates (`<style>` blocks or `style="..."`).
- JS must not apply visual styling via DOM style APIs (`style.cssText`, or `.style.<prop>` for colors/spacing/typography).
  - JS may toggle state only via `hidden` and/or `is-*` classes.

## CSS Architecture
- Load order (canonical): `styles.css` → `global.css` → page CSS.
- `static/css/styles.css`: tokens, base/reset, layout primitives, utilities.
- `static/css/global.css`: reusable components (buttons/forms/tables/alerts/modals).
- Page CSS: only page-specific layout that cannot be generalized.

## Cascade Layers
Use CSS cascade layers to keep overrides predictable:
- `reset`, `base`, `components`, `utilities`, `pages`

## Naming
Hybrid approach:
- Keep existing semantic classes already in use (e.g., `btn`, `alert`, `container-fluid`).
- New/refactored components use BEM-style naming:
  - Block: `c-thing`
  - Element: `c-thing__part`
  - Modifier: `c-thing--variant`
- States: `is-open`, `is-disabled`, `is-loading`, etc.
- Utilities: `u-hidden`, `u-flex`, etc. (keep small and stable)

## JS Interaction
- Prefer `element.hidden = true/false` or `classList.add/remove('is-*')`.
- Avoid inline event handlers (`onclick="..."`) for new code; bind in JS.

## Accessibility
Minimum expectations:
- Keyboard operable controls
- Visible focus states (`:focus-visible`)
- Respect `prefers-reduced-motion`
- Dark mode contrast for text/buttons/tables

## Where to Put Changes
- Shared style rules → `global.css` or `styles.css` depending on category.
- If a rule will be used by 2+ pages, it probably belongs in `global.css`.

## Review Checklist (quick)
- No inline CSS/JS styling introduced
- Snapshots unchanged (or intentionally updated with explanation)
- Tracker updated
