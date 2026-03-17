# PAM Architecture Diagram

> PAM (Promotion Automation Manager) — Flask web app for T-Mobile's promotions team.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        External Layer                               │
│                                                                     │
│  Browser  ──►  Azure App Service Easy Auth  ──►  Flask (PAM)        │
│                 (X-MS-CLIENT-PRINCIPAL headers)                     │
│                                                                     │
│  JIRA API  ◄──►  PAM  ◄──►  SQL Server (PromoQuality DB)            │
│                        ◄──►  Fabric / ORBIT DB                      │
│                        ◄──►  Oracle                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Application Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ENTRY POINT                                  │
│  app.py  ──►  factory.create_app()                                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    APPLICATION FACTORY  (factory.py)                │
│                                                                     │
│  ┌──────────────────┐   ┌───────────────────┐  ┌─────────────────┐  │
│  │  Flask App Init  │   │  Shared Services  │  │  Middleware     │  │
│  │  - secret key    │   │  PromoDataManager │  │  - CSRF         │  │
│  │  - config class  │   │  (single instance)│  │  - Rate limit   │  │
│  │  - session cache │   │  - injected into  │  │  - Sec headers  │  │
│  │  - logging       │   │    all blueprints │  │  - CSP          │  │
│  └──────────────────┘   └───────────────────┘  └─────────────────┘  │
│                                                                     │
│  Background Thread: _warm_app_cache()  (DB pool + homepage preload) │
└────────────────────────────┬────────────────────────────────────────┘
                             │  registers
          ┌──────────────────┼───────────────────────┐
          ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BLUEPRINTS (Route Layer)                    │
│                                                                     │
│  ┌───────────┐  ┌───────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │  core_bp  │  │  promo_bp │  │  admin_bp   │  │    api_bp      │  │
│  │  (root/)  │  │  (root/)  │  │  /admin     │  │    /api        │  │
│  │           │  │           │  │             │  │                │  │
│  │ - Home    │  │ - RDC     │  │ - Dashboard │  │ - JSON REST    │  │
│  │ - Landing │  │ - SPE     │  │ - Pagination│  │ - Orbit search │  │
│  │ - Theme   │  │ - Rebates │  │ - Version   │  │ - Promo lookup │  │
│  │ - Debug   │  │ - SQL gen │  │   history   │  │                │  │
│  └───────────┘  └───────────┘  └─────────────┘  └────────────────┘  │
│                                                                     │
│  ┌───────────┐  ┌───────────┐  ┌───────────────────────────────┐    │
│  │  jira_bp  │  │research_bp│  │           lists_bp            │    │
│  │  /jira    │  │ /research │  │           /lists              │    │
│  │           │  │           │  │                               │    │
│  │ - Tickets │  │ - PETE    │  │ - SKU lists                   │    │
│  │ - Lookup  │  │   workflow│  │ - Trade-in lists              │    │
│  │ - Create  │  │ - Research│  │ - List automation             │    │
│  └───────────┘  └───────────┘  └───────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────────┘
                             │  all call
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER  (data/)                         │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    PromoDataManager  (storage.py)           │    │
│  │                                                             │    │
│  │  Primary facade for all promotion data operations           │    │
│  │  - get_promo(), save_promo(), list_promos()                 │    │
│  │  - Phase computation & lifecycle transitions                │    │
│  │  - Manages uploads (data/uploads/promotions/)               │    │
│  │  - Delegates DB queries → DatabaseManager                   │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │                                       │
│    ┌────────────────────────┼─────────────────────────┐             │
│    ▼                        ▼                         ▼             │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐     │
│  │ DatabaseMgr  │  │  field_map.py    │  │  Supporting Modules│     │
│  │ (database.py)│  │                  │  │                    │     │
│  │              │  │ Canonical ↔      │  │ version_history.py │     │
│  │ SQL Server   │  │ Physical column  │  │  -Field audit trail│     │
│  │ + SQLAlchemy │  │ name mapping     │  │                    │     │
│  │ connection   │  │ (single source   │  │ sql_store.py       │     │
│  │ pool + retry │  │  of truth)       │  │  - SQL metadata    │     │
│  └──────┬───────┘  └──────────────────┘  │                    │     │
│         │                                │ approval_email_    │     │
│    ┌────┴──────────────────────┐         │  tracking.py       │     │
│    ▼                          ▼          │ code_tracking.py   │     │
│  ┌────────────┐  ┌────────────────────┐  │ sku_group_tracking │     │
│  │fabric_db   │  │ orbit_database.py  │  └────────────────────┘     │
│  │.py         │  │ oracle_client.py   │                             │
│  │            │  │                    │                             │
│  │ Fabric /   │  │ ORBIT analytics    │                             │
│  │ ORBIT conn │  │ Oracle integration │                             │
│  └────────────┘  └────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Authentication & Authorization Flow

```
HTTP Request
     │
     ▼
Azure App Service Easy Auth
     │ injects headers:
     │  X-MS-CLIENT-PRINCIPAL       (base64 JWT — groups, roles)
     │  X-MS-CLIENT-PRINCIPAL-NAME  (email / UPN)
     │  X-MS-CLIENT-PRINCIPAL-ID    (Azure AD object ID)
     │
     ▼
auth.py  get_user_from_headers()
     │
     ├── DEV_MODE=true (local) → synthetic dev user (role from DEV_USER_ROLE)
     │
     └── Production → parse JWT → extract groups → map to internal roles
              │
              ▼
         AZURE_ROLE_MAPPING
         ┌───────────────┬─────────────────┐
         │ Azure Role    │ Internal Role   │
         ├───────────────┼─────────────────┤
         │ Admin         │ pam_admin       │  ← superuser, all permissions
         │ Approver      │ pam_approvers   │  ← approval buttons + viewonly
         │ User          │ pam_users       │  ← full edit + viewonly + research
         │ ViewOnly      │ pam_viewonly    │  ← read-only audit
         │ Research      │ pam_research    │  ← research tools only
         └───────────────┴─────────────────┘
              │
              ▼
         @role_required('pam_users')  decorators on routes
         (role hierarchy enforced — pam_admin inherits all)
```

---

## Frontend Architecture

```
Browser
  │
  ├── templates/
  │     ├── landing.html          ← workspace hub (3 tiles)
  │     │
  │     ├── pam/
  │     │     ├── base_pam.html   ← PAM base layout (nav + sidebar)
  │     │     ├── rdc.html        ← RDC promotion list
  │     │     ├── spe.html        ← SPE promotion list
  │     │     ├── rebates.html    ← Rebate promotion list
  │     │     ├── edit_rdc.html   ← RDC editor
  │     │     ├── edit_spe.html   ← SPE editor
  │     │     ├── admin.html      ← admin dashboard
  │     │     ├── approvers.html  ← approval workflow
  │     │     └── capacity.html   ← capacity planning
  │     │
  │     ├── research/
  │     │     ├── research_base.html
  │     │     └── pete.html       ← PETE workflow UI
  │     │
  │     ├── lists/
  │     │     ├── lists_base.html
  │     │     ├── sku_lists.html
  │     │     └── tradein_lists.html
  │     │
  │     └── partials/
  │           ├── _theme_init.html
  │           ├── _theme_toggle.html
  │           └── _footer_time_script.html
  │
  └── static/
        ├── css/
        │     ├── styles.css    ← 1st: tokens, reset, layout  [reset + base layers]
        │     ├── global.css    ← 2nd: reusable components    [components layer]
        │     └── <page>.css    ← 3rd: page-specific          [pages layer]
        │
        ├── js/
        │     ├── jira_modal.js
        │     ├── device_formatter.js
        │     ├── research.js
        │     └── tradein_lists.js
        │
        └── img/  (logos, icons)
```

---

## Data Flow: Promotion Lifecycle

```
User Action (browser form)
        │
        ▼
promo_bp route  (promo/routes.py)
        │
        ├── auth check via @role_required
        │
        ▼
PromoDataManager.save_promo()
        │
        ├── field_map.py  (canonical → physical column names)
        │
        ├── DatabaseManager.execute_query()
        │         │
        │         └── SQL Server  [PAM].[PAM_Orbit_Data_Updated]
        │
        └── version_history.py  (field-level audit trail → SQL Server)
                  │
                  └── PAM.date_diagnostics_history  (in SQL Server)


SQL Generation Flow:
        │
        ▼
promo_bp  /generate_sql  route
        │
        ▼
promo/builders.py  (SQL builder — ~43 KB)
        │
        ▼
sql_store.py  (persist generated SQL metadata)
        │
        ▼
api_bp  /api/get_sql  (JSON response to browser)
```

---

## External Integrations

```
PAM
 │
 ├──► SQL Server (PromoQuality)
 │      Table: [PAM].[PAM_Orbit_Data_Updated]
 │      Table: [PAM].[date_diagnostics_history]
 │      Auth:  ODBC Driver 17 / integrated or SQL auth
 │
 ├──► Fabric / ORBIT DB  (fabric_database.py / orbit_database.py)
 │      Analytics and reporting data source
 │      Auth:  DefaultAzureCredential / ManagedIdentity / ClientSecret
 │
 ├──► Oracle  (oracle_client.py)
 │      Oracle data integration
 │
 └──► JIRA  (jira/routes.py)
        Ticket creation and lookup via JIRA REST API
```

---

## Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| Single data source | SQL Server is authoritative; JSON storage deprecated |
| Shared data manager | One `PromoDataManager` instance, injected into all blueprints |
| Field name mapping | `field_map.py` as single source of truth for column names |
| Audit trail | Field-level version history in SQL Server |
| Auth via headers | Azure Easy Auth; no passwords in Flask session |
| Safe test defaults | DB writes + outbound HTTP blocked unless `--run-integration` |
| Frontend constraints | No inline CSS; JS toggling via classes only; BEM naming |
