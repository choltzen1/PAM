# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Is

PAM (Promotion Automation Manager) is a Flask web application for T-Mobile's promotions team. It manages the lifecycle of RDC, SPE, and Rebate promotions — including creation, SQL generation, approvals, capacity planning, and JIRA integration. SQL Server is the single authoritative data source; JSON-based storage was fully deprecated.

## Common Commands

```bash
# Run the development server
python app.py

# Run all safe (non-integration) tests
python -m pytest

# Run a single test file
python -m pytest tests/test_database_connectivity.py

# Run a single test by name
python -m pytest tests/test_field_roundtrip.py::test_roundtrip_rdc_fields

# Run integration tests (requires real DB + HTTP access)
python -m pytest --run-integration -m integration

# Validate blueprint endpoints
python tools/validate_endpoints.py
```

## Architecture

**Application factory:** `factory.py::create_app()` wires together all blueprints and a single shared `PromoDataManager` instance. Each blueprint receives the data manager via its own `init_data_manager()` function.

**Blueprints:**
| Blueprint | Module | URL Prefix | Purpose |
|-----------|--------|------------|---------|
| `core_bp` | `core/__init__.py` | (root) | Home, landing, theme |
| `promo_bp` | `promo/routes.py` | (root) | RDC/SPE/Rebate CRUD, SQL generation |
| `admin_bp` | `admin/routes.py` | `/admin` | Dashboard, pagination, version history |
| `api_bp` | `api/routes.py` | `/api` | JSON/RESTful endpoints, Orbit search |
| `jira_bp` | `jira/routes.py` | `/jira` | JIRA ticket creation/lookup |
| `research_bp` | `research/routes.py` | `/research` | PETE workflow, research tools |

**Data layer (`data/`):**
- `storage.py` — `PromoDataManager`: the primary facade for all promotion data operations
- `database.py` — `DatabaseManager`: raw SQL Server + SQLAlchemy connection management
- `field_map.py` — canonical ↔ physical column name mapping (important for any DB queries)
- `version_history.py` — field-level audit trail stored in SQL Server
- `sql_store.py` — persistence for generated SQL metadata

**Authentication:** Azure AD Easy Auth. User info is extracted from `X-MS-CLIENT-PRINCIPAL` (base64 JWT) and `X-MS-CLIENT-PRINCIPAL-NAME` headers. Role decorators live in `auth.py`. Roles: `pam_admin`, `pam_approvers`, `pam_users`, `pam_viewonly`, `pam_research`.

## Testing Safety Model

`tests/conftest.py` enforces safe defaults:
- **By default:** integration tests are skipped (`-m "not integration"` in `pytest.ini`), DB writes (INSERT/UPDATE/DELETE/ALTER/DROP) are blocked, and outbound HTTP is blocked except to localhost.
- **`--run-integration` flag:** required to run tests that touch the real database or external services.
- Tests that guarantee no external writes can be marked `@pytest.mark.no_external_writes`.

When writing new tests, use the `integration` mark for anything that requires a real DB connection.

## Frontend Standards

Defined in `docs/FRONTEND_STANDARDS.md`. Key rules:
- **No inline CSS** in templates (`<style>` blocks or `style="..."` attributes).
- **JS may only toggle state** via `hidden` or `is-*` classes — never apply visual styles via `style.*` APIs.
- **CSS load order:** `styles.css` (tokens/reset/layout) → `global.css` (reusable components) → page-specific CSS.
- **CSS cascade layers:** `reset`, `base`, `components`, `utilities`, `pages`.
- **Naming:** BEM-style for new components (`c-block__element--modifier`); state classes `is-*`; utilities `u-*`.
- Shared rules used by 2+ pages belong in `global.css`, not page CSS.

## Key Environment Variables

```
FLASK_SECRET_KEY        # Required in non-dev environments
DEV_MODE=true           # Enables dev fallback secret key
PAM_DB_SERVER           # SQL Server hostname
PAM_DB_DATABASE         # Database name
PAM_DB_USERNAME/PASSWORD  # Optional (integrated auth used if omitted)
ORBIT_DB_SERVER/DATABASE  # Orbit analytics data source
PAM_VALIDATION_MODE=1   # Lightweight init for test/validation runs
```

## Branch Conventions

- Main branch: `cade`
- Current feature branch: `cssrefactor`
