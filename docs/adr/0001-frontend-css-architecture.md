# ADR 0001: Frontend CSS Architecture

Date: 2026-03-03

## Status
Accepted

## Context
The codebase has duplicated base templates, inline CSS in templates, and JS that applies visual styling via `style.cssText`. This creates drift, makes refactors risky, and complicates future maintenance.

## Decision
- Adopt a two-file global CSS split:
  - `static/css/styles.css`: tokens, base/reset, layout primitives, utilities.
  - `static/css/global.css`: reusable components.
- Add CSS cascade layers (`reset`, `base`, `components`, `utilities`, `pages`).
- Enforce no inline CSS in templates and no visual inline styling in JS (state toggles only).
- Use a hybrid naming convention: keep existing semantic classes; apply BEM-style naming for new/refactored components.

## Consequences
- Lower risk of UI drift; overrides become predictable.
- Short-term work to migrate existing inline styles and JS styling.
- Guardrail tests will prevent regressions and support incremental cleanup.
