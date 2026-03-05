# PAM - Promotion Automation Manager System

## Overview
PAM (Promotion Automation Manager) is a comprehensive web-based application designed for T-Mobile's promotions team to streamline the management, validation, and approval process of promotional campaigns. The system provides advanced tools for promotion lifecycle management, capacity planning, and approval workflows.

### Key Features

#### 🎯 **Promotion Management**
- **RDC Promotions**: Manage retail distribution center promotions with comprehensive data fields
- **SPE Promotions**: Handle special promotional events with custom configurations
- **Rebate Programs**: Track and manage customer rebate promotions
- **SQL Generation**: Automatic generation of promo eligibility rules SQL for database integration

#### 📊 **Capacity Management** 
- **Active Promotion Tracking**: Real-time view of currently active promotions by type (RDC/SPE/REBATE)
- **Weekly Launch Schedule**: Visual calendar showing promotion launch dates across 4-week periods
- **Owner Workload Distribution**: Track promotion workload across team members with status indicators
- **Resource Planning**: Capacity metrics to prevent overallocation and ensure smooth launches

#### ✅ **Approval Workflows**
- **Approver Assignment**: Assign device finance and revenue accounting approvers to promotions
- **Approval Tracking**: Monitor approval status and send approval requests
- **Department Integration**: Seamless integration with different approval departments

#### 📈 **Data Management & Validation**
- **File Upload Support**: SKU lists, trade-in files, and promotional documents (checksums logged)
- **Structured Version History**: Field‑level diffs and metadata are persisted in SQL Server with user + change type
- **Date Mismatch Detection**: Identify and resolve promotional date conflicts with diagnostics history
- **Export Capabilities**: Generate reports and export promotional data

#### 🎨 **User Experience**
- **Responsive Design**: Optimized for desktop, tablet, and mobile devices
- **Intuitive Navigation**: Tab-based interfaces for complex data entry
- **Real-time Filtering**: Advanced search and filter capabilities
- **Visual Status Indicators**: Clear status badges and progress indicators

## Technical Architecture

### Frontend
- **HTML5/CSS3**: Modern responsive design with Bootstrap components
- **JavaScript**: Interactive features, dynamic filtering, and real-time updates
- **Jinja2 Templates**: Server-side rendering with Flask template engine

### Backend
- **Flask Framework**: Modular blueprint architecture
- **Primary Data Store (SQL Server)**: `[PAM].[PAM_Orbit_Data_Updated]` is the single source of truth for ALL promotions (RDC/SPE/Rebate distinguished by `Desired_Execution`)
-- **Metadata Store**: metadata are persisted in SQL Server (`PAM.generated_sql_store`).
- **File Handling**: Secure file upload (saved under `data/uploads/promotions/<code>/`) with checksum + metadata persisted
- **Date Processing**: Advanced date calculations + invalid date diagnostics history

### Data Architecture
```
SQL Server (authoritative)
└── [PAM].[PAM_Orbit_Data_Updated]  (all core promo columns, incl. Desired_Execution)

Filesystem
└── data/uploads/promotions/<PROMO_CODE>/  (uploaded artifacts)

All metadata are now persisted in SQL Server (`PAM.generated_sql_store`).
```

Legacy JSON files (`promotions.json`, `spe_promotions.json`, `rebates.json`) were retired September 2025. On startup any remnants are auto‑archived to `.bak` and never read.

## Getting Started

### Prerequisites
- **Python 3.10 or higher**
- **pip** (Python package manager)
- **Virtual Environment** (recommended)

### Installation

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd PAM
   ```

2. **Set Up Virtual Environment**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   source venv/bin/activate  # macOS/Linux
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

1. **Environment Variables**:
   Copy `.env.example` to `.env` and set local secrets/connection values.
   ```bash
   copy .env.example .env   # Windows
   cp .env.example .env     # macOS/Linux
   ```
   Notes:
   - Never commit real credentials; `.env` is ignored by git.
   - Set `FLASK_SECRET_KEY` in `.env` for shared/non-local environments.
   - `DEV_MODE=true` is for local only and is blocked in Azure-hosted environments.

2. **Data Initialization**:
   Ensure SQL Server connectivity. Core promotion data is fetched live from SQL Server; ensure connectivity/env credentials.

### Running the Application

1. **Start the Development Server**:
   ```bash
   python app.py
   ```

2. **Access the Application**:
   Open your browser and navigate to `http://127.0.0.1:5000`

### Application Factory (Refactor 2025)
The app now uses an application factory pattern for better testability and modularity.

```
from factory import create_app
app = create_app()
```

Legacy scripts and the dev server still work via `python app.py`, which simply initializes the factory-built instance.

Benefits:
- Enables isolated app instances in tests (`create_app({'TESTING': True})`).
- Centralizes blueprint registration and data manager setup in `factory.py`.
- Simplifies future configuration injection (DB URIs, feature flags).

### Endpoint Validator & Migration Guardrails
`tools/validate_endpoints.py` enforces a blueprint‑only contract (legacy flat routes removed). Migration scripts under `tools/` (`migrate_json_history.py`, `migrate_extras_from_json.py`) remain for historical one‑time conversions; they are no longer required for new deployments.

### Routing & Refactor (2025 Migration)

The 2025 refactor decomposed a monolithic `app.py` into focused blueprints:

| Area | Blueprint | Module | Prefix |
|------|-----------|--------|--------|
| Promotions UI / SQL / Date Mismatch / Files | `promo` | `promo/routes.py` | (none) |
| Admin & Version History & User Mgmt | `admin_bp` | `admin/routes.py` | `/admin` |
| JIRA Integration | `jira_bp` | `jira/routes.py` | `/jira` |
| JSON/API Endpoints (lookup, orbit search, status update) | `api` | `api/routes.py` | `/api` |

All legacy flat routes and redirect shims were removed (September 2025). Only canonical blueprint endpoints remain.

#### Deprecation Controls

Environment flags control the lifecycle:

| Env Var | Effect |
|---------|--------|
| `PAM_VALIDATION_MODE=1` | Light-weight init for validator/tests (skips heavy external ops). |
| (REMOVED) `PAM_BLOCK_LEGACY_ROUTES=1` | Deprecated; shims removed so flag is ignored. |

Historical rollout (completed):
1. Introduced blueprints alongside shims.
2. Added validator + alias usage telemetry.
3. Converted templates/tests to blueprint endpoints.
4. Enabled blueprint-only validator in CI.
5. Removed shims & alias middleware (September 2025).

#### Adding New Routes
Always add routes in the appropriate blueprint; do not extend `app.py`. If you need a temporary alias, add the redirect in `app.py` plus a mapping entry in `tools/validate_endpoints.py`.

#### Why This Matters
Benefits realized:
- Clear separation of UI (promo/admin) vs integration (jira/api).
- Easier testing via `create_app()` with selective blueprint registration.
- Centralized data manager initialization & future feature toggles.
- Safe incremental migration with automated endpoint validation and alias usage telemetry.


## Application Structure

### Main Pages
- **Dashboard** (`/`): Home page with navigation and system overview
- **RDC** (`/rdc`): RDC promotion management interface
- **SPE** (`/spe`): Special promotional events management
- **Rebates** (`/rebates`): Rebate program administration
- **Capacity** (`/capacity`): Capacity planning and workload management
- **Approvers** (`/approvers`): Approval workflow management

### Key Components

#### Promotion Editing
- Multi-tab interface for complex promotion data
- Real-time validation and error highlighting
- Auto-save functionality with session persistence

#### Migration

Metadata migration helpers under `tools/` are deprecated and kept only for reference; they are disabled to avoid accidental local SQLite access.

#### Capacity Planning
- Current active promotions dashboard
- Weekly launch calendar view
- Owner workload distribution charts
- Resource allocation tracking

#### Approval Management
- Promotion-specific approver assignment
- Direct navigation from promotion lists
- Approval status tracking and notifications

### File Structure (Simplified)
```
PAM/
├── app.py                  # Entrypoint (factory bootstrap)
├── factory.py              # create_app()
├── data/
│   ├── storage.py          # PromoDataManager (DB-only)
│   ├── database.py         # SQL Server helpers (SQLite deprecated)
│   ├── version_history.py  # Version event semantics
│   └── uploads/  # uploaded files stored on disk; version history stored in SQL Server
├── promo/ (routes/builders/parsers)
├── admin/ (admin + stats + history)
├── api/   (lookup + integration endpoints)
├── services/orbit.py
├── static/ (css/js)
├── templates/ (Jinja2 views)
└── tools/ (migration + validation utilities)
```

## Development

### Continuous Integration
Automated tests & endpoint validation run on each push via GitHub Actions workflow `ci.yml`.

Badge (add once repo public / actions enabled):
```
![CI](https://github.com/choltzen1/PAM/actions/workflows/ci.yml/badge.svg)
```

Current enforced pipeline (legacy shims removed):
1. Install dependencies
2. Run pytest (with `PAM_VALIDATION_MODE=1`)
3. Run endpoint validator in blueprint mode (fails build if any legacy endpoints reappear)

Deprecation Status: Complete. Legacy shim routes removed; validator enforces blueprint-only mode. `PAM_BLOCK_LEGACY_ROUTES` flag retired.


### Adding New Features
1. Create feature branch from main
2. Implement changes following existing patterns
3. Test thoroughly across all browsers
4. Submit pull request for review

### Data Model Extensions
- Add core columns in SQL Server table (schema migration outside this repo scope)
- Add new extended (non-core) fields to `promo_extras` (SQLite) and wire into diff logic
- Record changes automatically via `record_version_entry` in `database.py`

### API Endpoints
The application provides RESTful endpoints for:
- Promotion CRUD operations
- File upload and download
- Approval workflow management
- Capacity planning data

## Deployment

### Production Considerations
- Run behind a production WSGI server (e.g., Gunicorn / IIS w/ wfastcgi)
- Provide SQL Server connectivity (ODBC driver / connection string env var)
-- Back up only: SQL Server data + uploaded files
- Monitor version history growth (diff JSON compact by design)
- Instrument logs / metrics (add structured logging if scaling)

### Example Production Setup
```bash
# Install production server
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Contributing
Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch
3. Follow existing code style and patterns
4. Include tests for new functionality
5. Submit a pull request with detailed description

## Support
For technical support or questions:
- **Primary Contact**: cade.holtzen1@t-mobile.com
- **Team**: T-Mobile Promotions Engineering
- **Internal Documentation**: [Link to internal docs]

## License
This project is proprietary to T-Mobile. See the LICENSE file for full details.

---

**PAM System Version**: 3.0.0  
**Last Updated**: September 2025  
**Maintained by**: T-Mobile Promotions Team
