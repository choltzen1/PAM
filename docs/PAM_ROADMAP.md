# PAM — Product Roadmap
### Promotions Automation Manager · T-Mobile Promotions Engineering
**Last Updated:** March 31, 2026  
**Maintainer:** Cade Holtzen (cade.holtzen1@t-mobile.com)

---

## Executive Summary

PAM automates the end-to-end lifecycle of T-Mobile promotional campaigns — from intake of ORBIT data, through SQL code generation for the EFPE eligibility system, to approval routing, versioning, and deployment tracking. The platform currently supports RDC (Regular Discount Credits) with SPE (Special Promotional Events) and Rebates as near-term expansions of the same engine.

---

## Timeline Overview

```
2025 Q3          Q4              2026 Q1              Q2              Q3
──┬──────────────┬───────────────┬───────────────┬─────────────────┬─────────
  │ FOUNDATION   │ BUILD-OUT     │ INTEGRATION   │ EXPAND          │ SCALE
  │              │               │ & STABILIZE   │                 │
  ▼              ▼               ▼               ▼                 ▼
Blueprint        PETE Research,  Fabric/ORBIT    SPE & Rebates     Production
Refactor &       PDT Parser,     Gateway +       SQL Generators    Hardening &
Core Build       UI Rebrand      Pipeline & Beta + PETE Expansion  Observability
                                                  / P.A.L.
```

---

## Phase 1 — Foundation (2025 Q3) ✅ COMPLETE

_Established the architectural backbone and core PAM capabilities._

| Deliverable | Status |
|---|---|
| Blueprint architecture migration (flat routes → `promo`, `admin`, `jira`, `api`, `research`) | ✅ Done |
| Application factory pattern (`factory.py` → `create_app()`) | ✅ Done |
| SQL Server primary data store (`PAM_Orbit_Data_Updated`) | ✅ Done |
| Legacy JSON storage retirement (`promotions.json` → `.bak`) | ✅ Done |
| Field mapping layer — 100+ canonical ↔ physical column mappings | ✅ Done |
| RDC listing page with search, pagination, owner filtering | ✅ Done |
| RDC multi-tab edit page (Details, SQL Generation, Links, etc.) | ✅ Done |
| Sequential promo code generation (R001→R999→S001…) with tombstoning | ✅ Done |
| Admin dashboard — data, users, groupings, performance, security, integrations | ✅ Done |
| Approval/review workflow with Database Mail email routing | ✅ Done |
| Capacity planning with weekly promotion calendar | ✅ Done |
| Version history tracking | ✅ Done |

---

## Phase 2 — Integration & Research (2025 Q4) 🔶 PARTIAL

_Built the integration layer and PETE research toolkit. Fabric connectivity code is complete but not yet connected to live ORBIT data._

| Deliverable | Status | Notes |
|---|---|---|
| Microsoft Fabric Data Warehouse integration code (OAuth Service Principal, 50-min token cache) | ✅ Code Complete | Connection code built, **awaiting gateway access** |
| `FabricDatabaseManager` — connection pooling, search by promo code / GTM ID | ✅ Code Complete | Not yet hitting live data |
| `OrbitDatabaseManager` — transparent Fabric toggle (`USE_FABRIC_ORBIT=true`) | ✅ Code Complete | Toggle ready, blocked on connectivity |
| ORBIT field mapping documented — 45+ mapped fields, 30 manual-entry fields identified | ✅ Done | |
| PETE research tool — EIP lookup, BAN discovery, 9 API endpoints | ✅ Done | |
| PETE promo eligibility context query (8-table CTE across EFPE) | ✅ Done | |
| PETE chat interface with keyword-driven response generation | ✅ Done | |
| Date/time normalization (epoch → human-readable) | ✅ Done | |
| PDT parser (tab-separated + trade-in Excel) | ✅ Done | |


---

## Phase 3 — RDC Pipeline Completion (2026 Early Q2) 🔶 IN PROGRESS ← **WE ARE HERE**

_Complete the data pipeline from ORBIT into RDC SQL generation and stabilize for beta._

### 🔴 Blocker
| Issue | Detail | Owner |
|---|---|---|
| Fabric Gateway / ORBIT Data Access | Fabric integration code is built but **cannot connect to live ORBIT data**. Working with IDS teams (Power BI team) to establish a gateway so PAM can query the Fabric Data Warehouse. Everything downstream (field population, SQL generation, beta testing) is gated on this. | IDS / Power BI team + PAM team |

### Current Sprint — Orbit-to-RDC Pipeline

| Task | Status | Notes |
|---|---|---|
| `orbit_search()` returns normalized promo data | ✅ Code Complete | Via `promo_codes_service.py` — ready once gateway works |
| **Fabric gateway established (live ORBIT access)** | 🔴 Blocked | Working with IDS / Power BI team — **this unblocks everything below** |
| **Auto-populate RDC edit fields from ORBIT data** | ⬜ Blocked | ~45 mapped fields need to flow into edit form; code paths exist, need live data to test & tune |
| **Map ORBIT fields into SQL generator inputs** | ⬜ Blocked | `builders.py` needs real ORBIT-sourced values (SOC grouping, trade tiers, segment data, etc.) |
| End-to-end SQL generation testing | ⬜ Blocked | Requires real ORBIT data flowing through the full pipeline |
| Rejection workflow testing (email threading) | ⬜ Not Started | Route built, needs integration testing |

### RDC Beta Milestone (Target: Early Q2 2026)

| Criteria | Status |
|---|---|
| ORBIT data auto-populates RDC forms | 🔶 |
| SQL generation produces valid EFPE INSERT blocks from real data | 🔶 |
| Uploaded Excel files (SKU/Trade-In) parse and generate correct device group INSERTs | ✅ Mostly done (trade-in works, SKU stub) |
| Approval email flow works end-to-end (send → approve/reject → track) | ✅ Built |
| Version history captures all changes | ✅ Built |
| Links management per-promo | ✅ Built |
| Dark mode branding consistent across all pages | ✅ Done |
| Manual QA pass by promotions team | ⬜ Not Started |

---

## Phase 4 — SPE & Rebates (2026 Q2) ⬜ PLANNED

_Extend the engine to handle SPE and Rebate constructs using the same RDC foundation._

### SPE (Special Promotional Events)

| Task | Status | Notes |
|---|---|---|
| SPE listing page with search/filter/pagination | ✅ Done | `/spe` route working |
| SPE edit page (multi-tab, details tab) | ✅ Done | `/edit-spe/<code>` working |
| SPE data storage & retrieval | ✅ Done | Uses same DB table, filtered by `Desired_Execution` |
| **SPE SQL generator** | ⬜ Not Started | Needs SPE-specific INSERT templates (different column set & rules than RDC) |
| SPE-specific field mapping/presets | ⬜ Not Started | May need new config presets beyond RDC ones |
| SPE approval workflow | 🔶 Partial | Can reuse RDC approval infra, may need SPE-specific email templates |
| SPE end-to-end testing | ⬜ Not Started | |

### Rebates

| Task | Status | Notes |
|---|---|---|
| Rebates listing page | ✅ Done | `/rebates` route exists |
| **Rebates edit page** | ⬜ Not Started | Needs rebate-specific form fields |
| **Rebates SQL generator** | ⬜ Not Started | Different construct from RDC/SPE |
| Rebates field mapping | ⬜ Not Started | |
| Rebates approval workflow | ⬜ Not Started | Reuse core infra |

### Key Insight
> Most of the bones are already laid. SPE and Rebates share the same data pipeline (ORBIT → PAM), the same approval infrastructure, the same code generation framework, and the same UI patterns. The work is primarily in **fine-tuning SQL output templates** for each construct type and adding any construct-specific fields.

---

## Phase 5 — PETE Expansion + SPETE / Re-PETE (2026 Q2) ⬜ PLANNED

_Expand PETE with richer troubleshooting data pulls, add P.A.L. (PETE 2.0) eligibility guidance, and extend the research model to SPE and cross-construct workflows._

| Task | Status | Notes |
|---|---|---|
| PETE enhanced data pulls (Port, AAL, manual bulk status) | ⬜ Not Started | Q2 2026 focus for RDC troubleshooting |
| Automated Port and AAL utilization pull | ⬜ Not Started | Surface BAN/EIP usage already satisfying Port or AAL promo requirements |
| Trade mis-shipment identification | ⬜ Not Started | Connect UPS and trade warehouse data needed to trace where a trade was lost |
| P.A.L. (PETE 2.0) automated eligibility determination | ⬜ Not Started | Late Q2 2026 target |
| P.A.L. reason-for-ineligibility output | ⬜ Not Started | Surface clear failure reasons alongside the automated decision |
| **SPETE workflow** | ⬜ Not Started | SPE-specific research queries and chat based on PETE patterns |
| Re-PETE cross-construct expansion | ⬜ Not Started | Extend research workflows across RDC, SPE, and Rebates |

### Planning Note
> PETE's Q2 enhancement roadmap is now defined. SPETE and Re-PETE still depend on the SPE construct becoming operational and on confirming the highest-value research patterns with the team.

---

## Phase 6 — Production Hardening & Scale (2026 Q3+) ⬜ FUTURE

_Harden the platform for full production use across the promotions team._

| Deliverable | Status |
|---|---|
| Azure production environment fully provisioned | ⬜ Blocked |
| Automated regression test suite (SQL output validation) | ⬜ Not Started |
| Email template regression tests | ⬜ Not Started |
| Observability — structured logging, diagnostics dashboard | ⬜ Not Started |
| Performance monitoring (metrics already scaffold in `perf/metrics.py`) | 🔶 Partial |
| Service layer build-out (`services/admin/`, `services/core/`, `services/jobs/`, `services/promo/`, `services/workflows/`) | ⬜ Scaffolded, no code |
| Offers module | ⬜ Placeholder templates only |
| JIRA integration expansion | 🔶 Partial |
| Multi-user concurrent editing safeguards | ⬜ Not Started |
| Role-based access control refinement | ⬜ Not Started |

---

## Technical Debt & Cleanup

| Item | Priority | Notes |
|---|---|---|
| ~~Remove `services/orbit.py` mock stub~~ | ~~Low~~ | ✅ Deleted Feb 11, 2026 |
| Move `templates/research/pete.py` out of templates dir | Low | Python file misplaced in Jinja2 template folder |
| ~~Implement `parse_sku_excel()` in `parsers.py`~~ | ~~Medium~~ | ✅ Removed stub — `builders.py` handles SKU parsing inline |
| Populate empty service packages | Low | `services/admin/`, `core/`, `jobs/`, `promo/`, `workflows/` |
| Fix unreachable returns in `PromoCodeWorkflow.orbit_lookup()` | Low | Two dead-code returns |

---

## Architecture Reference

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                           │
├─────────────────────────────────────────────────────────────────┤
│                     Flask / Jinja2 Templates                    │
│  ┌──────┐ ┌───────┐ ┌──────┐ ┌──────┐  ┌──────────┐             │
│  │ RDC  │ │  SPE  │ │Rebate│ │Admin │  │ Research │             │
│  │routes│ │routes │ │routes│ │routes│  │  /PETE   │             │
│  └──┬───┘ └──┬────┘ └──┬───┘ └──┬───┘  └────┬─────┘             │
│     │        │         │        │           │                   │
│  ┌──▼────────▼─────────▼────────▼───────────▼──────┐            │
│  │              Services Layer                     │            │
│  │  promo_codes_service │ mail_service │ cache     │            │
│  │  promo_code_workflow │ jira_utils               │            │
│  └──────────────┬──────────────────────────────────┘            │
│                 │                                               │
│  ┌──────────────▼───────────────────────────────────┐           │
│  │              Data Layer                          │           │
│  │  ┌────────────┐  ┌──────────────┐  ┌───────────┐ │           │
│  │  │ storage.py │  │orbit_database│  │ field_map │ │           │
│  │  │ (DB CRUD)  │  │   .py        │  │   .py     │ │           │
│  │  └─────┬──────┘  └──────┬───────┘  └───────────┘ │           │
│  │        │                │                        │           │
│  │  ┌─────▼──────┐   ┌─────▼─────────┐              │           │
│  │  │ SQL Server │   │ MS Fabric     │              │           │
│  │  │ PAM DB     │   │ ORBIT Data    │              │           │
│  │  │            │   │ Warehouse     │              │           │
│  │  └────────────┘   └───────────────┘              │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                 │
│  ┌──────────────────────────────────────────────────┐           │
│  │           SQL Generation (builders.py)           │           │
│  │  PROMO_ELIGIBILITY_RULES │ PROMO_DEVICE_GROUPS   │           │
│  │  PROMO_TRADEIN_GROUPS    │ PROMO_TIERED_GROUPS   │           │
│  │  PROMO_MK_MDL_GROUPS     │ PROMO_SEGMENT_GROUPS  │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Milestones Summary

| Milestone | Target | Status |
|---|---|---|
| Blueprint architecture & core CRUD | 2025 Q3 | ✅ Complete |
| Fabric/ORBIT integration code complete | 2025 Q4 | ✅ Code Complete |
| PETE research tool | 2025 Q4 | ✅ Complete |
| Fabric gateway / live ORBIT data access | 2026 Q1 | 🔴 Blocked (IDS/Power BI) |
| ORBIT → RDC pipeline complete | 2026 Q1 | 🔶 Blocked on gateway |
| RDC Beta (internal testing) | Late Q1 2026 | 🔶 Approaching |
| RDC Production | Early Q2 2026 | ⬜ Pending beta results |
| SPE SQL generation | Q2 2026 | ⬜ Planned |
| Rebates SQL generation | Q2 2026 | ⬜ Planned |
| PETE enhanced data pulls | Q2 2026 | ⬜ Planned |
| P.A.L. (PETE 2.0) | Late Q2 2026 | ⬜ Planned |
| SPETE / Re-PETE follow-on | Q2–Q3 2026 | ⬜ Planned |
| Full production hardening | Q3 2026 | ⬜ Future |

---

*This roadmap is a living document. Update as milestones are reached or priorities shift.*
