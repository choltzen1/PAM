# PAM Internal Team Roadmap
### Promotions Automation Manager — Detailed Plan for the Team
**Last Updated:** March 31, 2026
**Maintainer:** Cade Holtzen (cade.holtzen1@t-mobile.com)

> **Audience:** PAM team members, promotions engineering leads, P3 stakeholders.
> For the executive-level timeline, see the PAM Roadmap slide deck.

---

## Where We Are Today (March 31, 2026)

**Big news:** The ORBIT data connection is **LIVE**. PAM is now pulling real promotion data directly from the ORBIT Data Warehouse. This was the major blocker holding up the RDC pipeline — it's now cleared.

We're wrapping up RDC and starting work on SPE & Rebates. The approvals code has been tested and approved in the current environment; the remaining step is switching approval routing over to production email recipients.

### Progress at a Glance

| Phase | What It Means | Status |
|-------|---------------|--------|
| Platform Foundation | PAM exists, has pages, stores data, has user roles | Done |
| Data & Research Tools | PETE works, ORBIT connection built, field mapping done | Done |
| RDC Fully Operational | Create an RDC promo start-to-finish using real ORBIT data | Almost done (~85%) |
| SPE & Rebates | Same workflow, but for SPE and Rebate promo types | Getting started (~30%) |
| PETE / SPETE / Re-PETE | PETE expansion plus research tools for SPE and cross-construct troubleshooting | Q2 kickoff planned |
| Stability & Monitoring | Make everything rock-solid for daily production use | Early stages |

---

## Phase 3 — RDC Promo Automation Fully Operational (Finishing Up)

**What this means for the team:** You'll be able to pull a promo from ORBIT, have PAM auto-fill the details, generate the SQL, send it for approval, and track the whole thing — all from one place.

### 3A. Connecting ORBIT Data to RDC Forms (April 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 3A-1 | Verify that promo details auto-fill correctly from live ORBIT data (45+ fields) | Dev | In Progress | 1 week |
| 3A-2 | Make sure auto-filled data flows correctly into SQL generation | Dev | Next Up | 1 week |
| 3A-3 | Test the full flow: pull from ORBIT, generate SQL, verify output is correct | Dev | Waiting on 3A-2 | 2-3 days |
| 3A-4 | **P3 team validates:** Does the generated SQL match what you'd write by hand? | Dev + P3 Team | Waiting on 3A-3 | 2-3 days |
| 3A-5 | Fix any data gaps or mapping issues found during testing | Dev | As needed | 1-3 days |

### 3B. Approval Workflow Production Cutover (April 2026)

Approval workflow code has already been tested and approved. The remaining work in this phase is cutting over from test recipients to production emails and confirming the live approval path behaves correctly.

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 3B-1 | Update approval email routing from test recipients to production emails | Dev | Next Up | 1 day |
| 3B-2 | Verify production approval emails thread correctly (replies stay in the same email chain) | Dev | Waiting on 3B-1 | 1 day |
| 3B-3 | Run a final live approval/rejection pass after the production email cutover | Dev | Waiting on 3B-1 | 2 days |
| 3B-4 | SOX compliance check — confirm the audit trail meets requirements | Dev + Compliance | Waiting on 3B-3 | 2 days |
| 3B-5 | Write up the approval process for team training | Dev | Waiting on 3B-3 | 1 day |

### 3C. RDC Beta Checklist (Target: Mid-April 2026)

Before we call RDC "ready," all of these need a checkmark:

| # | Criteria | Status |
|---|----------|--------|
| 3C-1 | Pulling a promo from ORBIT auto-fills the RDC form correctly | In Progress |
| 3C-2 | SQL generation produces correct output using real ORBIT data | Not yet tested |
| 3C-3 | Uploading Excel files (SKU lists, trade-in devices) works correctly | Done |
| 3C-4 | Approval emails send, get approved or rejected, and the status updates | Code tested and approved; production email cutover remaining |
| 3C-5 | Every field change is tracked in version history | Done |
| 3C-6 | UI looks clean in both light and dark mode | In Progress |
| 3C-7 | **P3 team hands-on test:** Create 3+ real RDC promos end-to-end | Scheduled for April 2026 |

**What "beta complete" looks like:** The P3 team can create RDC promos from start to finish without workarounds, and the generated SQL is validated by engineering.

---

## Phase 4 — SPE & Rebate Support (Q2 2026: Late April - June)

**What this means for the team:** Everything that works for RDC promos will also work for SPE and Rebate promos — same workflow, same approval process, same tracking. Each type just generates different SQL based on its own business rules.

### 4A. SPE Promos (Late April - May 2026)

SPE already has a listing page and edit page in PAM. The main work is enabling SQL generation and making sure the business rules are captured correctly.

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 4A-1 | **Gather SPE business rules** — What makes SPE SQL different from RDC? What fields change? What are the defaults? | Dev + P3 SMEs | Not Started | 2-3 days |
| 4A-2 | Build the SPE SQL generator based on those rules | Dev | Waiting on 4A-1 | 1-1.5 weeks |
| 4A-3 | Set up SPE-specific default values and field presets | Dev | Waiting on 4A-1 | 2-3 days |
| 4A-4 | Connect the SPE edit page to SQL generation (click "Generate SQL" and it works) | Dev | Waiting on 4A-2 | 1-2 days |
| 4A-5 | **P3 team validates:** Does the SPE SQL match what you'd expect? | Dev + P3 Team | Waiting on 4A-4 | 3-5 days |
| 4A-6 | Set up SPE-specific approval email templates (if needed) | Dev | Waiting on 4A-1 | 1-2 days |
| 4A-7 | Full end-to-end test: ORBIT to SPE SQL to approval | Dev | Waiting on all above | 2-3 days |

**What P3 team needs to provide:** SME time to walk through SPE-specific rules, sample SPE SQL for comparison, and validation of generated output.

### 4B. Rebate Promos (May - June 2026)

Rebates currently only have a read-only listing. This phase adds full editing and SQL generation.

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 4B-1 | **Gather Rebate business rules** — What makes Rebates different? What fields are unique? | Dev + P3 SMEs | Not Started | 2-3 days |
| 4B-2 | Build the Rebate editing page (like the RDC edit page, but for Rebates) | Dev | Waiting on 4B-1 | 1-1.5 weeks |
| 4B-3 | Build the Rebate SQL generator | Dev | Waiting on 4B-1 | 1-1.5 weeks |
| 4B-4 | Set up Rebate-specific default values and field presets | Dev | Waiting on 4B-1 | 2-3 days |
| 4B-5 | Connect the Rebate edit page to SQL generation | Dev | Waiting on 4B-2, 4B-3 | 1-2 days |
| 4B-6 | **P3 team validates:** Does the Rebate SQL match what you'd expect? | Dev + P3 Team | Waiting on 4B-5 | 3-5 days |
| 4B-7 | Set up Rebate-specific approval routing (reuses existing approval system) | Dev | Waiting on 4B-1 | 1-2 days |
| 4B-8 | Full end-to-end test: ORBIT to Rebate SQL to approval | Dev | Waiting on all above | 2-3 days |

### 4C. All Three Promo Types Working Together (June 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 4C-1 | Create one RDC, one SPE, and one Rebate promo end-to-end as a team exercise | Dev + P3 Team | Not Started | 3-5 days |
| 4C-2 | Verify all three types produce correct, distinct SQL output | Dev | Not Started | 2-3 days |
| 4C-3 | Confirm promo code numbering stays consistent across all types | Dev | Not Started | 1 day |
| 4C-4 | SOX compliance sign-off for SPE & Rebate approval audit trails | Dev + Compliance | Not Started | 2 days |
| 4C-5 | **Team training:** Walk through SPE & Rebate workflows in PAM | Dev + P3 Team | Not Started | 2 days |

### 4D. SKU & Trade-In List Management (Parallel Track, Q2 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 4D-1 | Build SKU list upload (drag-and-drop Excel/CSV into PAM) | Dev | Not Started | 1 week |
| 4D-2 | Auto-generate SKU SQL from uploaded lists | Dev | Not Started | 1 week |
| 4D-3 | Build trade-in list management screen | Dev | Not Started | 1 week |
| 4D-4 | Link SKU and trade-in lists to specific promos from the edit page | Dev | Waiting on 4D-1, 4D-3 | 2-3 days |

---

## Phase 5 — PETE, SPETE & Re-PETE Research Tools (Q2 2026 Kickoff)

**What this means for the team:** PETE already helps research RDC promos (EIP lookups, eligibility checks, error reasons). In Q2, PETE expands with richer Port, AAL, bulk-status, and trade troubleshooting data. SPETE extends the same model to SPE, and P.A.L. / Re-PETE push the research experience toward smarter automated eligibility guidance across promo types.

### 5A. PETE Enhancements (April - June 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 5A-1 | Add PETE data pull for Port-in activity tied to the BAN associated to the EIP | Dev | Not Started | 3-5 days |
| 5A-2 | Add PETE data pull for AAL utilization so the team can see which BAN lines already satisfy AAL requirements | Dev | Not Started | 3-5 days |
| 5A-3 | Add PETE data pull for Port utilization so the team can see which BAN Port activity already satisfies Port requirements | Dev | Not Started | 3-5 days |
| 5A-4 | Add manual bulk enrollment status and summary review capability | Dev | Not Started | 2-3 days |
| 5A-5 | Connect data sources needed for trade mis-shipment identification (UPS and trade warehouse visibility) | Dev | Not Started | 1 week |
| 5A-6 | Team validation: run PETE enhancements against real troubleshooting scenarios | Dev + P3 Team | Waiting on 5A-1 to 5A-5 | 2-3 days |

### 5B. SPETE — SPE Research Tool (May - June 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 5B-1 | Identify what data the team needs to look up for SPE troubleshooting | Dev + P3 SMEs | Not Started | 3-5 days |
| 5B-2 | Build SPE-specific data queries (eligibility, error reasons, account data) | Dev | Waiting on 5B-1 | 1-1.5 weeks |
| 5B-3 | Build the SPETE lookup screens (EIP search, eligibility check, etc.) | Dev | Waiting on 5B-2 | 1 week |
| 5B-4 | Build the SPETE chat interface (like PETE, but for SPE questions) | Dev | Waiting on 5B-3 | 1 week |
| 5B-5 | Teach the AI assistant about SPE-specific terms and logic | Dev | Waiting on 5B-3 | 2-3 days |
| 5B-6 | Team testing: use SPETE on real SPE scenarios | Dev + P3 Team | Waiting on all above | 2-3 days |

### 5C. P.A.L. (PETE 2.0) (Late Q2 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 5C-1 | Add smart automated capability to determine current promo eligibility | Dev | Not Started | 1-1.5 weeks |
| 5C-2 | Display the reason for ineligibility directly in the PETE response flow | Dev | Waiting on 5C-1 | 2-3 days |
| 5C-3 | Validate P.A.L. decisions against real promo scenarios before rollout | Dev + P3 Team | Waiting on 5C-1, 5C-2 | 2-3 days |

### 5D. Re-PETE — Next-Gen Research Tool (Late Q2 2026 kickoff, continuing as needed)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 5D-1 | **Scope session:** What do you wish PETE could do that it can't today across RDC, SPE, and Rebates? | Dev + P3 Team | Not Started | 3-5 days |
| 5D-2 | Build expanded lookups that work across RDC, SPE, and Rebates | Dev | Waiting on 5D-1 | 1-1.5 weeks |
| 5D-3 | Smarter AI chat — better understanding of promo context, fewer dead ends | Dev | Waiting on 5D-1 | 1-1.5 weeks |
| 5D-4 | Batch lookup — check multiple EIPs or BANs at once | Dev | Waiting on 5D-1 | 1 week |
| 5D-5 | Session history, saved searches, and export to Excel | Dev | Waiting on 5D-3 | 1 week |
| 5D-6 | Team testing: use Re-PETE on real scenarios | Dev + P3 Team | Waiting on all above | 2-3 days |

---

## Phase 6 — Production Hardening & Long-Term Stability (Q3 2026+)

**What this means for the team:** PAM becomes a fully supported production tool — reliable, monitored, and ready for the whole promotions org to use daily.

### 6A. Reliability & Quality (July - August 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 6A-1 | Automated checks that SQL output hasn't broken after updates | Dev | Not Started | 1-1.5 weeks |
| 6A-2 | Automated checks that approval emails still look correct after updates | Dev | Not Started | 2-3 days |
| 6A-3 | Prevent two people from editing the same promo at the same time (conflict protection) | Dev | Not Started | 1-1.5 weeks |
| 6A-4 | Expanded automated testing across all features | Dev | Not Started | 1 week |
| 6A-5 | Stress testing — make sure PAM handles busy days without slowing down | Dev | Not Started | 1 week |

### 6B. Monitoring & Visibility (August - September 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 6B-1 | Better logging so issues can be diagnosed quickly | Dev | Not Started | 1 week |
| 6B-2 | Admin health dashboard — see system status at a glance | Dev | Started | 1 week |
| 6B-3 | Track page load times and slow queries | Dev | Started | 1 week |
| 6B-4 | Azure monitoring integration (alerts if something goes wrong) | Dev | Not Started | 1 week |
| 6B-5 | Automatic alerts if the ORBIT data connection drops | Dev | Not Started | 2-3 days |

### 6C. Infrastructure & Security (September 2026)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 6C-1 | Full production Azure environment (beyond the test environment) | Dev + Infra | Blocked (needs provisioning request) | 1 week |
| 6C-2 | More granular user permissions (beyond the current 5 roles) | Dev | Not Started | 1 week |
| 6C-3 | Automated credential rotation (security best practice) | Dev + Infra | Not Started | 2-3 days |
| 6C-4 | Disaster recovery plan and documentation | Dev | Not Started | 2-3 days |
| 6C-5 | Automated deployments to staging and production | Dev | Partially Built | 1 week |

### 6D. Feature Expansion (Ongoing)

| # | What's Happening | Who's Involved | Status | Timeline |
|---|-----------------|----------------|--------|----------|
| 6D-1 | JIRA integration improvements — auto-create tickets, sync status | Dev | Partially Built | 1-1.5 weeks |
| 6D-2 | Offers module (future capability, scope TBD) | Dev + Stakeholders | Not Started | TBD |

---

## UI Refresh (In Progress, Parallel to All Phases)

| # | What's Happening | Status | Timeline |
|---|-----------------|--------|----------|
| CC-1 | Cleaning up shared visual styles for consistency | In Progress | 1 week |
| CC-2 | Standardizing edit page layouts (RDC and SPE look and feel the same) | In Progress | 1 week |
| CC-3 | Dark mode working consistently on every page | Nearly Done | 1-2 days |
| CC-4 | Works well on both laptop screens and large monitors | Not Started | 1-2 days |

---

## What the Team Needs to Know

### Where We Need P3 SME Input

These are the key moments where we'll need promotions team expertise:

| When | What We Need | Why It Matters |
|------|-------------|----------------|
| **April** (Phase 3) | Validate RDC SQL output against hand-written SQL | Ensures PAM generates correct code before we rely on it |
| **Late April** (Phase 4A) | Walk through SPE business rules and provide sample SQL | Can't build the SPE generator without knowing the rules |
| **May** (Phase 4B) | Walk through Rebate business rules and provide sample SQL | Same — need the rules to build correctly |
| **June** (Phase 4C) | Hands-on testing: create promos of all three types | Final validation before we call multi-construct "done" |
| **May-June** (Phase 5A) | Validate PETE enhancement priorities against real troubleshooting cases | Ensures Port, AAL, bulk-status, and trade lookup work solve the right problems |
| **June** (Phase 5B) | What data do you need for SPE troubleshooting? | Drives what SPETE queries look like |
| **Late June** (Phase 5C) | Validate P.A.L. eligibility decisions and ineligibility explanations | Ensures PETE 2.0 matches team expectations |
| **Late June-July** (Phase 5D) | What do you wish PETE could do better across all promo types? | Shapes the Re-PETE upgrade |

### Key Risks & What We're Doing About Them

| Risk | What Could Happen | What We're Doing |
|------|-------------------|------------------|
| SPE/Rebate rules are unclear | Phase 4 gets delayed 2-4 weeks | Scheduling SME sessions in April before dev starts |
| ORBIT data connection goes down | Can't pull promo data into PAM | Built-in retry logic and caching; adding alerts in Phase 6 |
| Only one developer building PAM | Everything moves at one person's pace | Documenting thoroughly so others can help or take over |
| Azure production environment takes time to provision | Can't go fully live on schedule | Starting the request now, not waiting until Phase 6 |

---

## Quarterly Milestones

### Q2 2026 (April - June)
- [ ] **April:** P3 hands-on RDC testing completed end-to-end with real data
- [ ] **April:** Approval workflow moved from test inboxes to production emails
- [ ] **April-May:** SPE SQL generation working and validated
- [ ] **May-June:** Rebate editing and SQL generation working and validated
- [ ] **June:** All three promo types (RDC, SPE, Rebate) working in PAM
- [ ] **Q2:** PETE enhanced data pulls live for Port, AAL, bulk status, and trade troubleshooting
- [ ] **Late Q2:** P.A.L. (PETE 2.0) eligibility automation and ineligibility explanations in development
- [ ] **Q2:** SPETE and Re-PETE kickoff underway
- [ ] **Ongoing:** UI refresh complete, SKU/trade-in list management started

### Q3 2026 (July - September)
- [ ] **July:** SPETE research tool live for SPE troubleshooting
- [ ] **July-August:** Re-PETE upgrade scoped and development started
- [ ] **August:** Automated testing and monitoring in place
- [ ] **September:** Production environment provisioned and hardened

### Q4 2026+ (October onwards)
- [ ] Full monitoring and alerting live
- [ ] Automated deployments to staging and production
- [ ] AI-powered features expanded
- [ ] Ongoing improvements based on team feedback

---

## How This Roadmap Connects to the Executive View

| Executive Roadmap Phase | What It Maps To Here |
|------------------------|---------------------|
| Q3 2025: Platform Foundation Established | Phase 1 (Done) |
| Q4 2025: Data and Research Enablement | Phase 2 (Done) |
| Late Q2 2026: RDC Promo Automation Fully Operational | Phases 3 + early Phase 4 |
| Q3 2026: Multi-Construct Expansion (SPE & Rebates) | Phase 4 completion + Phase 5 |
| Q3-Q4 2026+: Ongoing Maintenance and Improvements | Phase 6 |

---

*This is a living document. It gets updated as work completes or priorities shift. Questions? Reach out to Cade.*
