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
- **File Upload Support**: SKU lists, trade-in files, and promotional documents
- **Data Validation**: Comprehensive error checking and data consistency validation
- **Date Mismatch Detection**: Identify and resolve promotional date conflicts
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
- **Flask Framework**: Python web framework with modular blueprint architecture
- **JSON Data Storage**: Flexible data management with JSON file persistence
- **File Handling**: Secure file upload and management system
- **Date Processing**: Advanced date calculations for promotion scheduling

### Data Structure
```
data/
├── promotions.json      # RDC promotion data
├── spe_promotions.json  # SPE promotion data
├── rebates.json         # Rebate program data
└── uploads/             # File upload storage
    └── promotions/      # Promotion-specific files
```

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

1. **Environment Variables** (optional):
   Create a `.env` file for environment-specific settings:
   ```env
   FLASK_DEBUG=True
   FLASK_ENV=development
   ```

2. **Data Initialization**:
   The application will automatically create initial data files on first run.

### Running the Application

1. **Start the Development Server**:
   ```bash
   python app.py
   ```

2. **Access the Application**:
   Open your browser and navigate to `http://127.0.0.1:5000`

## Application Structure

### Main Pages
- **Dashboard** (`/`): Home page with navigation and system overview
- **Promotions** (`/promotions`): RDC promotion management interface
- **SPE** (`/spe`): Special promotional events management
- **Rebates** (`/rebates`): Rebate program administration
- **Capacity** (`/capacity`): Capacity planning and workload management
- **Approvers** (`/approvers`): Approval workflow management

### Key Components

#### Promotion Editing
- Multi-tab interface for complex promotion data
- Real-time validation and error highlighting
- Auto-save functionality with session persistence

#### Capacity Planning
- Current active promotions dashboard
- Weekly launch calendar view
- Owner workload distribution charts
- Resource allocation tracking

#### Approval Management
- Promotion-specific approver assignment
- Direct navigation from promotion lists
- Approval status tracking and notifications

### File Structure
```
PAM/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── LICENSE               # License information
├── data/                 # Data storage
│   ├── __init__.py
│   ├── storage.py        # Data management layer
│   ├── promotions.json   # RDC promotions
│   ├── spe_promotions.json # SPE promotions
│   ├── rebates.json      # Rebate data
│   └── uploads/          # File uploads
├── promo/                # Promotion business logic
│   ├── builders.py       # SQL generation
│   ├── parsers.py        # Data parsing utilities
│   └── routes.py         # Promotion-specific routes
├── services/             # External service integrations
│   └── orbit.py          # Orbit system integration
├── static/               # Static assets
│   ├── css/             # Stylesheets
│   └── js/              # JavaScript files
└── templates/            # HTML templates
    ├── base.html         # Base template
    ├── promotions.html   # Promotion management
    ├── capacity.html     # Capacity planning
    ├── approvers.html    # Approval workflows
    └── [other pages]
```

## Development

### Adding New Features
1. Create feature branch from main
2. Implement changes following existing patterns
3. Test thoroughly across all browsers
4. Submit pull request for review

### Data Model Extensions
- Extend JSON schemas in `data/storage.py`
- Update validation rules as needed
- Maintain backward compatibility

### API Endpoints
The application provides RESTful endpoints for:
- Promotion CRUD operations
- File upload and download
- Approval workflow management
- Capacity planning data

## Deployment

### Production Considerations
- Use a production WSGI server (e.g., Gunicorn)
- Configure proper environment variables
- Set up SSL/TLS certificates
- Implement proper backup strategies for data files
- Configure log rotation and monitoring

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

**PAM System Version**: 2.0.0  
**Last Updated**: August 2025  
**Maintained by**: T-Mobile Promotions Team
