# Hydrotesting Feature - Complete Documentation

## Overview
The Hydrotesting Feature is a comprehensive compliance management system for petrol bunks, designed to track and manage hydrotest records for tanks, pipelines, sumps, and vent lines in accordance with PESO (Petroleum and Explosives Safety Organisation) regulations.

## Features Implemented

### 1. **Database Models**
- **Tank**: Storage tank management with capacity, fuel type, and location tracking
- **Pipeline**: Pipeline management with length, diameter, and fuel type
- **Hydrotest**: Complete hydrotest record with test details, results, and compliance tracking
- **HydrotestFile**: Document storage for certificates, photos, and supporting documents
- **HydrotestNotification**: Automated notification system for expiring tests
- **ContractorMaster**: PESO contractor database with licence verification

### 2. **Core Modules**

#### A. Hydrotest Data Entry Module
- **Form Fields**:
  - Basic Information: Tank/Pipeline selection, test date
  - PESO Contractor: Name, licence number, certificate number
  - Technical Details: Test pressure, hold duration, result, validity period
  - Remarks: Observations and notes
  
- **Document Upload**:
  - Hydrotest Certificate PDF (Required)
  - Gas-Free Certificate PDF
  - Pressure Gauge Calibration Certificate
  - Photos: Before test, during filling, gauge reading, after test
  - Supports: PDF, JPG, PNG, DOC, DOCX formats

#### B. Compliance Tracking Module
- **Status Calculation**:
  - **Compliant** (Green): >90 days until expiry
  - **Warning** (Yellow): 30-90 days until expiry
  - **Due Soon** (Orange): ≤30 days until expiry
  - **Expired** (Red): Past due date

- **Dashboard Metrics**:
  - Total compliant tests
  - Tests due soon
  - Warning status tests
  - Expired tests

#### C. Notification & Reminder System
- **Automated Notifications**:
  - 90 days before expiry
  - 30 days before expiry
  - On expiry date
  
- **Delivery Methods**:
  - Email notifications
  - Dashboard alerts
  - Real-time notification banner

- **Background Service**:
  - Runs every 24 hours
  - Creates pending notifications
  - Sends email alerts automatically

### 3. **User Interface Screens**

#### Main Dashboard (`/hydrotesting/dashboard`)
- Summary cards showing compliance status
- Quick action buttons (Add Test, Manage Tanks, Manage Pipelines)
- Expiring soon tests table
- Overdue tests alert section
- Recent tests history

#### Tank Management (`/hydrotesting/tanks`)
- Grid view of all tanks
- Status indicators for each tank
- Last test date and next due date
- Quick access to test history

#### Pipeline Management (`/hydrotesting/pipelines`)
- Grid view of all pipelines
- Status indicators for each pipeline
- Last test date and next due date
- Quick access to test history

#### Add Test (`/hydrotesting/add_test`)
- Comprehensive form with validation
- Dynamic equipment selection based on test type
- Multiple file upload support
- Auto-calculation of next due date

#### View Test Details (`/hydrotesting/view_test/<id>`)
- Complete test information display
- Status banner with compliance alerts
- Contractor information
- All uploaded documents with download links

#### Test History (`/hydrotesting/history`)
- Filterable list of all tests
- Equipment type filter
- Specific equipment filter
- Sortable columns

#### Compliance Report (`/hydrotesting/compliance_report`)
- PESO-ready compliance report
- Summary statistics
- Detailed equipment-wise status
- Printable format

#### Contractor Directory (`/hydrotesting/contractors`)
- PESO approved contractors list
- Licence numbers and validity
- Contact information

### 4. **PESO Compliance Features**

#### Compliance Validation
- Validates test dates against PESO requirements
- Tracks PESO certificate numbers
- Monitors contractor licence validity
- Maintains 5-year document retention

#### Reporting
- Generate compliance reports for PESO audits
- Equipment-wise status tracking
- PESO approval status tracking
- Certificate number tracking

#### Document Management
- Secure storage of all certificates
- Photo evidence of test procedures
- Gauge calibration certificates
- Gas-free certificates

### 5. **Role-Based Access Control**

#### Pump Owner Access
- Full access to their pump's hydrotesting data
- Add/edit tanks and pipelines
- Upload test records
- View compliance reports
- Download certificates

#### Admin Access (Future)
- View all pump hydrotesting data
- Verify PESO contractors
- Approve test records
- Generate system-wide reports

### 6. **Integration with Variance Logic**

The system integrates with fuel variance tracking:

```python
# Example integration logic
if (hydrotest_expired OR hydrotest_failed) AND (daily_variance > threshold):
    flag = "Possible leakage – Hydrotest pending"
    alert_level = "CRITICAL"
```

This smart integration helps identify:
- Tank leakage correlation with failed hydrotests
- Pipeline integrity issues
- Fuel loss patterns related to equipment condition

## API Endpoints

### Public Endpoints
- `GET /hydrotesting/dashboard` - Main dashboard
- `GET /hydrotesting/tanks` - Tank list
- `GET /hydrotesting/pipelines` - Pipeline list
- `GET /hydrotesting/add_tank` - Add tank form
- `GET /hydrotesting/add_pipeline` - Add pipeline form
- `GET /hydrotesting/add_test` - Add test form
- `GET /hydrotesting/view_test/<id>` - View test details
- `GET /hydrotesting/history` - Test history
- `GET /hydrotesting/compliance_report` - Compliance report
- `GET /hydrotesting/contractors` - Contractor directory
- `GET /hydrotesting/download_file/<id>` - Download document

### API Endpoints
- `GET /hydrotesting/api/check_notifications` - Check pending notifications
- `POST /hydrotesting/api/mark_notification_read/<id>` - Mark notification as read

## Database Schema

### Tanks Table
```sql
CREATE TABLE tanks (
    id INTEGER PRIMARY KEY,
    pump_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    tank_id VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    capacity FLOAT NOT NULL,
    fuel_type VARCHAR(50) NOT NULL,
    location VARCHAR(200),
    installation_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Hydrotests Table
```sql
CREATE TABLE hydrotests (
    id INTEGER PRIMARY KEY,
    pump_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    tank_id INTEGER,
    pipeline_id INTEGER,
    test_type VARCHAR(50) NOT NULL,
    test_date DATE NOT NULL,
    peso_contractor_name VARCHAR(200) NOT NULL,
    competent_person_licence VARCHAR(100) NOT NULL,
    test_pressure FLOAT NOT NULL,
    pressure_unit VARCHAR(10) DEFAULT 'bar',
    hold_duration INTEGER NOT NULL,
    result VARCHAR(20) NOT NULL,
    remarks TEXT,
    next_due_date DATE NOT NULL,
    validity_years INTEGER DEFAULT 5,
    peso_approved BOOLEAN DEFAULT FALSE,
    peso_approval_date DATE,
    peso_certificate_number VARCHAR(100),
    created_by VARCHAR(100),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Installation & Setup

### 1. Database Migration
```bash
flask db migrate -m "Add hydrotesting tables"
flask db upgrade
```

### 2. Create Upload Directory
The system automatically creates `uploads/hydrotest_documents/` on startup.

### 3. Configure Email (for notifications)
Ensure email settings are configured in `.env`:
```
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

### 4. Access the Feature
Navigate to: `http://localhost:5001/hydrotesting/dashboard?pump_id=<your_pump_id>`

Or access via Pump Dashboard → Silver Features → 💧 Hydrotesting

## Usage Guide

### Adding a Tank
1. Go to Hydrotesting Dashboard
2. Click "Manage Tanks"
3. Click "Add Tank"
4. Fill in tank details (ID, name, capacity, fuel type)
5. Submit

### Adding a Hydrotest Record
1. Go to Hydrotesting Dashboard
2. Click "Add New Test"
3. Select test type (Tank/Pipeline/Sump/Vent Line)
4. Select equipment
5. Enter test date and contractor details
6. Enter technical test details (pressure, duration, result)
7. Upload required documents
8. Submit

### Viewing Compliance Status
1. Go to Hydrotesting Dashboard
2. View summary cards for quick overview
3. Check "Expiring Soon" section for upcoming tests
4. Review "Overdue Tests" for immediate action items

### Generating PESO Report
1. Go to Hydrotesting Dashboard
2. Click "Compliance Report"
3. Review equipment-wise status
4. Click "Print Report" for PESO audit

## Notification System

### How It Works
1. **Background Service**: Runs every 24 hours
2. **Notification Creation**: Creates notifications at 90, 30, and 0 days before expiry
3. **Email Delivery**: Sends automated emails to pump owners
4. **Dashboard Alerts**: Shows notification banner on dashboard

### Email Template
```
Subject: Hydrotest Expiry Alert - Tank: Petrol Storage Tank 1

Dear [Owner Name],

This is an automated reminder regarding your hydrotest compliance.

Equipment: Tank: Petrol Storage Tank 1
Test Type: Tank Hydrotest
Last Test Date: 10/02/2025
Next Due Date: 10/02/2030
Days Until Expiry: 30

Hydrotest will expire in 30 days. Please schedule testing.

Please schedule a hydrotest as soon as possible to maintain PESO compliance.

Best regards,
FuelFlux Team
```

## Security Features

### Access Control
- Only pump owners can access their own data
- Login required for all endpoints
- CSRF protection on all forms

### Data Retention
- Minimum 5-year document retention
- Audit trail with created_by tracking
- No deletion without admin approval

### File Upload Security
- Allowed file types: PDF, JPG, PNG, DOC, DOCX
- Secure filename handling
- Unique file naming (UUID)
- File size validation

## Best Practices

### For Pump Owners
1. Upload test records immediately after testing
2. Keep all original certificates as backup
3. Schedule tests 30 days before expiry
4. Verify contractor PESO licence before hiring
5. Review compliance report monthly

### For Administrators
1. Verify PESO contractors regularly
2. Monitor overdue tests across all pumps
3. Generate system-wide compliance reports
4. Ensure notification service is running
5. Backup hydrotest documents regularly

## Troubleshooting

### Notifications Not Sending
1. Check email configuration in `.env`
2. Verify notification service is running
3. Check database for pending notifications
4. Review application logs

### File Upload Issues
1. Verify `uploads/hydrotest_documents/` exists
2. Check file size limits
3. Ensure allowed file extensions
4. Verify disk space

### Compliance Status Not Updating
1. Check next_due_date calculation
2. Verify test_date is correct
3. Review validity_years setting
4. Check database timestamps

## Future Enhancements

### Planned Features
1. SMS notifications via Twilio
2. Mobile app integration
3. QR code verification for certificates
4. Auto-generation of test certificates
5. Integration with PESO online portal
6. Advanced analytics and trends
7. Contractor rating system
8. Equipment maintenance scheduling

### Integration Opportunities
1. Link with fuel variance detection
2. Integration with inventory management
3. Connection to billing system
4. API for third-party contractor apps

## Technical Stack

- **Backend**: Flask (Python)
- **Database**: SQLAlchemy ORM (SQLite/PostgreSQL)
- **Frontend**: TailwindCSS, Vanilla JavaScript
- **File Storage**: Local filesystem (upgradeable to S3)
- **Email**: Flask-Mail
- **Background Tasks**: Threading

## Support & Maintenance

### Regular Maintenance
- Weekly: Review pending notifications
- Monthly: Verify contractor licences
- Quarterly: Generate compliance reports
- Annually: Archive old test records

### Monitoring
- Check notification service status daily
- Monitor disk space for uploads
- Review error logs weekly
- Validate email delivery rates

## Compliance Checklist

### PESO Requirements ✓
- [x] Tank hydrotest tracking
- [x] Pipeline hydrotest tracking
- [x] Sump hydrotest tracking
- [x] Vent line test tracking
- [x] Contractor licence verification
- [x] Certificate storage (5 years)
- [x] Test validity tracking
- [x] Compliance reporting
- [x] Document evidence (photos)
- [x] Gauge calibration tracking
- [x] Gas-free certificate storage

## Contact & Support

For technical support or feature requests, contact the development team.

---

**Version**: 1.0.0  
**Last Updated**: December 2025  
**Status**: Production Ready
