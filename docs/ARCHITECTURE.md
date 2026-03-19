# PAM — Architecture Document

> PAM (Promotion Automation Manager) — Flask web application for T-Mobile's promotions team.
> Manages the lifecycle of RDC, SPE, and Rebate promotions including creation, SQL generation, approvals, capacity planning, and JIRA integration.

---

## 1. Project Structure

```
PAM/
├── Root Configuration & Entrypoint
│   ├── app.py                          # Flask entrypoint, bootstrap factory
│   ├── factory.py                      # create_app() factory, blueprint wiring, init
│   ├── config.py                       # BaseConfig, DevelopmentConfig, TestingConfig, ProductionConfig
│   ├── auth.py                         # Azure AD Easy Auth + RBAC decorators
│   ├── requirements.txt                # Python dependencies
│   ├── pytest.ini                      # Test configuration
│   ├── CLAUDE.md                       # Claude Code project guidance
│   └── FABRIC_INTEGRATION_GUIDE.md     # Microsoft Fabric setup guide
│
├── Backend: Blueprints
│   ├── core/__init__.py                # Home, landing, theme, debug endpoints
│   ├── promo/
│   │   ├── routes.py                   # RDC/SPE/Rebate CRUD, SQL generation, approvals
│   │   ├── builders.py                 # SQL generation + promo eligibility rule builders
│   │   ├── parsers.py                  # PDT parsing + Oracle date conversions
│   │   └── config_presets.py           # Promo configuration templates
│   ├── admin/routes.py                 # Dashboard, pagination, version history, user mgmt
│   ├── api/routes.py                   # JSON/RESTful endpoints, Orbit search
│   ├── jira/routes.py                  # JIRA ticket creation + epic link integration
│   ├── research/
│   │   ├── routes.py                   # PETE workflow (eligibility research)
│   │   ├── services.py                 # BAN, EIP, trade-in, promo rules data fetching
│   │   ├── db.py                       # Research DB queries
│   │   └── pete_workflow.py            # PETE session management
│   └── lists/routes.py                 # SKU lists & trade-in list automation
│
├── Data Layer
│   ├── data/
│   │   ├── storage.py                  # PromoDataManager: primary facade for all promo ops
│   │   ├── database.py                 # DatabaseManager: SQL Server + SQLAlchemy connections
│   │   ├── field_map.py                # Canonical ↔ physical column name mapping
│   │   ├── version_history.py          # Field-level audit trail (PAM.Version_History)
│   │   ├── sql_store.py               # Generated SQL metadata (PAM.generated_sql_store)
│   │   ├── orbit_database.py           # OrbitDatabaseManager: staging table lookups
│   │   ├── fabric_database.py          # FabricDatabaseManager: Microsoft Fabric access
│   │   ├── oracle_client.py            # Oracle linked server integration
│   │   ├── code_tracking.py            # Promo code generation helpers
│   │   ├── approval_email_tracking.py  # Approval workflow metadata
│   │   └── sku_group_tracking.py       # SKU grouping audit
│   └── data/uploads/promotions/        # Per-promo file storage (SKU lists, SQL, metadata)
│
├── Services & Integrations
│   ├── mail_service.py                 # SQL Server Database Mail integration
│   ├── jira_utils.py                   # JIRA summary builder + ticket creation helpers
│   ├── cache.py                        # TTLCache: in-memory caching with expiry
│   ├── promo_codes_service.py          # Promo code workflow + issuance
│   └── promo_code_workflow.py          # Advanced promo code state management
│
├── Frontend
│   ├── static/css/                     # 25+ CSS files (styles.css → global.css → page-specific)
│   ├── static/js/                      # device_formatter, jira_modal, research, tradein_lists
│   └── templates/
│       ├── pam/                        # PAM section templates (edit_rdc, edit_spe, admin, etc.)
│       ├── research/                   # PETE workspace templates
│       └── lists/                      # SKU/trade-in list templates
│
├── Tests
│   ├── tests/conftest.py               # Fixtures + test safety guards (DB write blocking)
│   ├── tests/test_*.py                 # 40+ test files
│   └── perf/metrics.py                 # Request latency collector
│
├── Tools
│   ├── tools/validate_endpoints.py     # Blueprint endpoint validator (CI enforced)
│   ├── tools/refresh_staging_schema.py # Orbit staging schema refresh
│   ├── build_catalog_hierarchy.py      # Device catalog builder
│   ├── query_fabric.py                 # Fabric data warehouse query tool
│   └── ssms_job.py                     # Dataverse extraction + SQL Server merge job
│
├── CI/CD & Config
│   ├── .github/workflows/ci.yml        # GitHub Actions: pytest + endpoint validation
│   ├── .github/workflows/cade_pam-npe.yml  # Deploy to Azure App Service
│   ├── .pre-commit-config.yaml         # Pre-commit hooks
│   └── mypy.ini                        # Type checking config
│
└── Documentation
    └── docs/                           # ARCHITECTURE.md, FRONTEND_STANDARDS.md, RBAC, roadmap, ADRs
```

---

## 2. High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USERS                                     │
│         (T-Mobile Promotions Team — Browsers)                       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AZURE APP SERVICE                                 │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Azure AD Easy Auth (X-MS-CLIENT-PRINCIPAL JWT)               │  │
│  └───────────────────────────┬───────────────────────────────────┘  │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Flask Application (Gunicorn WSGI)                            │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐ ┌──────────┐  │  │
│  │  │ core_bp │ │promo_bp │ │admin_bp │ │api_bp│ │research_bp│  │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └──────┘ └──────────┘  │  │
│  │  ┌─────────┐ ┌─────────┐                                     │  │
│  │  │ jira_bp │ │lists_bp │                                     │  │
│  │  └─────────┘ └─────────┘                                     │  │
│  │                    │                                          │  │
│  │         PromoDataManager (facade)                             │  │
│  │         DatabaseManager (SQL Server)                          │  │
│  └───────────────────────┬───────────────────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  SQL Server  │  │   JIRA API   │  │  MS Fabric   │
│ (PromoQuality│  │ (Atlassian)  │  │ (Dataverse)  │
│  Database)   │  │              │  │              │
├──────────────┤  └──────────────┘  └──────────────┘
│ PAM schema   │
│ RDC schema   │         ┌──────────────┐
│ Oracle links │────────▶│ Oracle DB    │
│ (OPENQUERY)  │         │ (OFS/PEFPEP) │
└──────────────┘         └──────────────┘
```

---

## 3. Core Components

### Frontend
- **Purpose:** Jinja2 server-rendered HTML with page-specific CSS
- **Technologies:** HTML5, CSS3 (cascade layers), vanilla JavaScript (minimal)
- **CSS Architecture:** `styles.css` (tokens/reset) → `global.css` (shared components) → page CSS. BEM naming (`c-block__element--modifier`). Dark mode via `[data-theme='dark']`.
- **JS Philosophy:** State toggles only (`hidden`, `is-*` classes). No visual styling via JS.
- **Deployment:** Static files served by Flask / Azure App Service

### Backend (Flask Blueprints)
- **Purpose:** Route handling, business logic, data orchestration
- **Technologies:** Flask 3.1, SQLAlchemy 2.0, pyodbc, Jinja2
- **Pattern:** Application factory (`factory.py::create_app()`). Single shared `PromoDataManager` injected into all blueprints via `init_data_manager()`.
- **Deployment:** Gunicorn WSGI on Azure App Service

### Data Layer
- **Purpose:** All database operations, field mapping, version tracking
- **Technologies:** SQL Server (pyodbc + SQLAlchemy), Oracle (oracledb), Microsoft Fabric (ODBC + OAuth)
- **Pattern:** `PromoDataManager` facade wraps `DatabaseManager` for all CRUD. `field_map.py` translates between canonical Python names and physical SQL column names.
- **Deployment:** Connects to remote SQL Server instances via environment variables

---

## 4. Data Stores

### SQL Server — PromoQuality Database (Primary)
| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `[PAM].[PAM_Orbit_Data_Updated]` | Single source of truth for all promotions (RDC, SPE, Rebate) | `code` (PK), `Owner`, `bill facing name`, `orbit_id`, `Desired_Execution`, `Status`, pricing, dates, eligibility, trade tiers |
| `[PAM].[Version_History]` | Field-level audit trail | `promo_code`, `event_type`, `changed_fields` (JSON), `actor`, `event_ts` |
| `[PAM].[generated_sql_store]` | Generated SQL metadata | `promo_code`, `sql_text`, `sql_hash`, `generated_at`, `generated_by` |
| `[PAM].[OrbitPromoExtract_STG]` | Staging table (Dataverse imports) | Merged into main table via `dbo.usp_Merge_OrbitPromoExtract` |
| `[PAM].[Trade_Catalog_Assurant]` | Trade-in device catalog hierarchy | `MAXVALUE_MFG`, `MARKETING_NAME` |
| `[PAM].[date_diagnostics_history]` | Date validation snapshots | `total_with_value`, `valid_dates`, `invalid_dates` |

### RDC Database (Same Server — Read-Only Reference)
| Table | Purpose |
|-------|---------|
| `RDC.Daily_EFPE_ELIGIBILITY_RULES` | Promo eligibility rules by code |
| `RDC.Daily_EFPE_DEVICE_GROUPS` | SKU group definitions |
| `RDC.Daily_EFPE_SOC_GROUPS` | SOC group definitions |
| `RDC.Daily_EFPE_TRADEIN_GROUPS` | Trade-in group definitions |
| `RDC.Daily_EFPE_MK_MDL_GROUPS` | Make/model device tier groups |
| `RDC.Daily_EFPE_PORT_GROUPS` | Port-in eligibility groups |
| `RDC.Daily_EFPE_SEGMENT_GROUPS` | Customer segment groups |

### Oracle Databases (Linked Server — OPENQUERY)
| Linked Server | Purpose |
|---------------|---------|
| `OFSLL` | OFS Loan data (`EDS_ACCOUNTS_TMO`, `EDS_AGREEMENTS_TMO`) |
| `PEFPEP_RO` | Promo execution errors (`PROMO_ERROR_REASONS`) |
| `RSCUSP` | Subscriber records (`VSTAPPO.SUBSCRIBER`) |

### In-Memory Cache
- **TTLCache** (`cache.py`): configurable TTL, used for Fabric query results (30 min), Orbit lookups
- **Flask-Session**: filesystem-backed server-side sessions

### File Storage
- `data/uploads/promotions/<PROMO_CODE>/` — SKU Excel files, trade-in Excel files, generated SQL, metadata JSON sidecars

---

## 5. External Integrations

| Service | Purpose | Auth Method | Files |
|---------|---------|-------------|-------|
| **Atlassian JIRA** | Create promo tickets, epic links | Basic auth (email + API token) | `jira/routes.py`, `jira_utils.py` |
| **Microsoft Fabric** | Orbit reporting data (optional) | OAuth Service Principal (MSAL) | `data/fabric_database.py`, `query_fabric.py` |
| **Dataverse (Dynamics 365)** | Promo source data extraction | TDS SQL via service principal token | `ssms_job.py` |
| **Azure AD / Entra ID** | User authentication | Easy Auth JWT (`X-MS-CLIENT-PRINCIPAL`) | `auth.py` |
| **SQL Server Database Mail** | Approval email notifications | T-SQL `sp_send_dbmail` | `mail_service.py` |
| **Oracle Database** | Execute promo eligibility SQL | Username/password (oracledb) | `data/oracle_client.py` |

---

## 6. Deployment & Infrastructure

| Component | Detail |
|-----------|--------|
| **Cloud Provider** | Microsoft Azure |
| **Compute** | Azure App Service (Linux, Python 3.11+) |
| **WSGI Server** | Gunicorn |
| **Authentication** | Azure AD Easy Auth (built-in to App Service) |
| **Database** | Azure SQL Server (PromoQuality database) |
| **CI/CD** | GitHub Actions (`ci.yml` — test, `cade_pam-npe.yml` — deploy) |
| **Build** | Oryx build system (`SCM_DO_BUILD_DURING_DEPLOYMENT=true`) |
| **Monitoring** | Performance metrics via `perf/metrics.py` (request latency) |
| **Dependency Management** | Dependabot (`dependabot.yml`) for security updates |
| **Pre-Commit** | `.pre-commit-config.yaml` for linting hooks |

---

## 7. Security Considerations

| Area | Implementation |
|------|----------------|
| **Authentication** | Azure AD Easy Auth (production). Base64 JWT in `X-MS-CLIENT-PRINCIPAL` header. Dev fallback via `DEV_MODE=true`. |
| **Authorization** | RBAC with 5 roles: `pam_admin`, `pam_approvers`, `pam_users`, `pam_viewonly`, `pam_research`. Enforced via `@role_required()` decorator. |
| **CSRF Protection** | Flask-WTF enabled globally. Exempt: `api_bp` (JSON), `core_bp` (stateless). |
| **Rate Limiting** | Flask-Limiter: 300 req/min per IP (in-memory storage). |
| **SQL Injection** | Parameterized queries via SQLAlchemy. No raw string interpolation. |
| **File Uploads** | `secure_filename()` validation. Checksum metadata logged. |
| **Session** | Filesystem-backed (cachelib). SameSite=Lax cookies. Non-permanent sessions. |
| **Security Headers** | X-Content-Type-Options: nosniff, X-Frame-Options: SAMEORIGIN, Referrer-Policy: strict-origin, CSP: self + CDN whitelist. |
| **Secrets** | Environment variables only. No inline secrets. `.env` checked at startup. |

---

## 8. Development & Testing

### Local Setup
```bash
# Clone & install
git clone <repo-url> && cd PAM
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Edit with local DB credentials
export DEV_MODE=true   # Enables dev auth fallback

# Run
python app.py          # Starts Flask dev server on port 5000
```

### Testing
```bash
python -m pytest                           # Safe mode (no DB, no HTTP)
python -m pytest --run-integration         # With real DB + services
python -m pytest tests/test_specific.py    # Single file
python tools/validate_endpoints.py         # Blueprint endpoint check (CI enforced)
```

### Test Safety Model
- **Default:** Integration tests skipped, DB writes blocked (INSERT/UPDATE/DELETE/DROP caught), outbound HTTP blocked (except localhost)
- **`--run-integration`:** Required for real DB/service tests
- **Prod guard:** Refuses prod-like servers unless `PYTEST_ALLOW_PROD_DB=1`

### Code Quality
| Tool | Config | Purpose |
|------|--------|---------|
| pytest | `pytest.ini` | Testing framework with strict markers |
| mypy | `mypy.ini` | Static type checking |
| pre-commit | `.pre-commit-config.yaml` | Linting hooks |
| validate_endpoints.py | CI workflow | Blueprint-only route enforcement |

---

## 9. Future Considerations

### Known Technical Debt
- **JSON storage fully deprecated** (Sept 2025) — legacy `.json` files auto-archived to `.bak`, all data in SQL Server
- **SQLite diagnostics deprecated** — moved to SQL Server `PAM.date_diagnostics_history`
- **Migration tools disabled** — `migrate_json_history.py`, `migrate_extras_from_json.py` kept for reference only
- **CSS duplication** — `.c-field-card` component defined in both `edit_rdc.css` and `edit_spe.css`; should be consolidated into `global.css`

### Planned Enhancements
- Fabric integration expansion (currently optional fallback for Orbit data)
- Async promo code issuance (currently synchronous)
- Performance metrics dashboard (framework in place via `perf/metrics.py`)
- Research module full rollout (currently Alpha status)
- Rebate edit page alignment with RDC/SPE card-based design system
- UI refactor tracking (see `docs/UI_REFACTOR_TRACKING.md`)

---

## 10. Glossary

| Term | Meaning |
|------|---------|
| **RDC** | Retail Distribution Center — primary promotion type for device sales, pricing, and eligibility rules |
| **SPE** | Special Promotional Event — secondary promotion type for special one-time campaigns |
| **Rebate** | Customer rebate programs — third promotion type for refund/rebate eligibility |
| **Orbit** | External marketing initiative system — data source for promo enrichment (names, dates, descriptions) |
| **Orbit ID** | Marketing initiative identifier linking PAM promos to Orbit records |
| **PETE** | Promo Eligibility Testing Engine — research tool for testing customer qualification |
| **BPTCR** | Bill-to-Point-of-Transaction-Card-Reader — T-Mobile internal promo classification field |
| **DCD** | Device Care Discount — JIRA project for DCD-related promotion tickets |
| **EFPE** | Primary JIRA project key for promo eligibility tickets |
| **SOC** | Service of Charge — T-Mobile plan/service classification used in eligibility rules |
| **BAN** | Billing Account Number — customer account identifier used in PETE lookups |
| **EIP** | Equipment Installment Plan — device financing; tracked in promo research |
| **FMV** | Fair Market Value — device trade-in valuation used in trade tier configs |
| **Desired_Execution** | Database column determining promo type (RDC, SPE, or Rebate) |
| **NSEIP** | No-cost Service Equipment Installment Plan drop indicator |
| **MPSS** | Mobile Protection Service Solutions — lookback period field |
| **ATST** | Account Type / Sub-Type grouping |

---

## 11. Project Identification

| Field | Value |
|-------|-------|
| **Project Name** | PAM — Promotion Automation Manager |
| **Team** | T-Mobile Promotions Operations |
| **Primary Contact** | Cade Holtzen |
| **Repository** | GitHub (private) |
| **Main Branch** | `cade` |
| **Deployment** | Azure App Service (`PAM-npe`) |
| **Last Updated** | 2026-03-18 |
