# Fuel Flux - Petrol Pump Management System

A comprehensive Flask-based web application for managing petrol pumps with advanced features including OCR receipt processing, subscription management, vehicle verification, hydrotesting compliance, and ANPR gate control.

## Features

### Core Features
- 🔐 **Dual Authentication**: Separate portals for Users and Pump Owners
- 🏪 **Pump Management**: Register and manage multiple pump stations
- 📊 **Dashboard Analytics**: Real-time data visualization with dark theme UI
- 💳 **Subscription System**: Tiered plans (Silver/Gold/Diamond) with Razorpay payment
- 🧾 **OCR Receipt Processing**: Advanced receipt data extraction using EasyOCR
- 📈 **Daily Comparison**: Compare sales data between receipts
- 🧪 **Density Calculator**: Fuel density calculations at standard temperature

### Advanced Features

#### 🧪 Hydrotesting Management
- **Tank & Pipeline Tracking**: Manage storage tanks and pipeline hydrotesting schedules
- **Compliance Monitoring**: Track test dates, expiry, and compliance status
- **Automated Alerts**: Email notifications for expiring tests (30/90 days)
- **Contractor Management**: Maintain records of testing contractors
- **Compliance Reports**: Generate detailed compliance reports
- **Document Management**: Upload and store test certificates

#### 🚗 ANPR (Automatic Number Plate Recognition)
- **Real-time Detection**: OpenCV + EasyOCR powered license plate recognition
- **Vehicle Compliance**: Automated hydrotest compliance checking
- **Gate Control**: Automatic gate opening/closing based on compliance
- **RTSP Camera Integration**: Support for multiple RTSP camera streams
- **Entry Logging**: Complete detection history with images
- **Alert System**: Email alerts for expired/blacklisted vehicles
- **Vehicle Database**: Comprehensive vehicle registration and tracking

#### 👥 Employee Management
- **Face Recognition**: AI-powered attendance tracking
- **Live Monitoring**: Real-time employee presence detection
- **Attendance Reports**: Detailed attendance analytics
- **Multiple Camera Support**: Monitor multiple locations simultaneously

## Tech Stack

- **Backend**: Flask, SQLAlchemy, Flask-Login, Flask-Migrate
- **Database**: PostgreSQL (production) / SQLite (development)
- **Computer Vision**: OpenCV, EasyOCR, dlib, face_recognition
- **AI/ML**: PyTorch (for ANPR), NumPy
- **Payment**: Razorpay
- **Auth**: Google OAuth 2.0
- **Email**: Flask-Mail with SMTP
- **Video Streaming**: RTSP protocol support
- **Deployment**: Render.com
- **UI**: TailwindCSS, Font Awesome

## Environment Variables

Required environment variables for deployment:

```
DATABASE_URL=postgresql://...
SECRET_KEY=your_secret_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
RAZORPAY_KEY_ID=your_razorpay_key
RAZORPAY_KEY_SECRET=your_razorpay_secret
MAIL_USERNAME=your_email
MAIL_PASSWORD=your_email_password
FLASK_ENV=production
```

## Local Development

### Standard Setup

1. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env` file

4. Initialize database:
```bash
flask db upgrade
```

5. Run the application:
```bash
python app.py
```

6. Access at `http://localhost:5001`

### Conda Setup (Recommended for ANPR/Face Recognition)

For features requiring face recognition and ANPR:

1. Install Conda/Miniconda
2. Run setup script:
```bash
# Windows
.\start_conda.bat

# Or manually
conda create -n fuelflux python=3.9
conda activate fuelflux
pip install -r requirements_conda.txt
```

3. See `ANPR_FEATURE_GUIDE.md` and `HYDROTESTING_SETUP_GUIDE.md` for detailed setup

## Key Features in Detail

### ANPR Gate Control System
- Supports HTTP and GPIO relay gate control
- Configurable confidence thresholds
- Adjustable detection intervals
- Real-time compliance checking
- Automatic email alerts for violations
- Complete audit trail with images

### Hydrotesting Compliance
- Track tanks and pipelines separately
- Multiple test types (pressure, leak, visual)
- Automated expiry calculations
- Color-coded compliance status
- Contractor database integration
- PDF certificate storage

### Employee Attendance
- Face recognition using dlib
- Live camera monitoring
- Attendance reports by date range
- Multiple employee support
- Real-time presence detection

## Deployment

### Render.com Deployment
See `PETROL_BUNK_DEPLOYMENT_GUIDE.md` for complete deployment instructions.

### Requirements
- Python 3.9+
- PostgreSQL database
- SMTP email server (for notifications)
- RTSP cameras (for ANPR/attendance features)
- Adequate storage for images and documents

## Project Structure

```
Flue_flex_pvt_ltd_/
├── app.py                          # Main application file
├── config.py                       # Configuration settings
├── models.py                       # Database models
├── hydrotesting.py                 # Hydrotesting blueprint
├── employee.py                     # Employee management
├── anpr_processor.py               # ANPR detection engine
├── anpr_compliance_checker.py      # Vehicle compliance logic
├── requirements.txt                # Python dependencies
├── requirements_conda.txt          # Conda environment dependencies
├── Procfile                        # Render deployment config
├── migrations/                     # Database migrations
├── templates/
│   ├── Pump-Owner/
│   │   ├── hydrotesting/          # Hydrotesting templates
│   │   ├── employee_management.html
│   │   └── attendance_monitor.html
│   └── ...
├── static/                         # CSS, JS, images
├── lib/
│   └── face_recognition_service.py # Face recognition module
└── uploads/
    ├── hydrotest_documents/        # Test certificates
    └── anpr_detections/            # ANPR captured images
```

## Documentation

- `ANPR_FEATURE_GUIDE.md` - Complete ANPR setup and usage guide
- `HYDROTESTING_SETUP_GUIDE.md` - Hydrotesting feature documentation
- `HYDROTESTING_FEATURE_DOCUMENTATION.md` - Detailed hydrotesting specs
- `INSTALL_FACE_RECOGNITION.md` - Face recognition setup guide
- `RTSP_TROUBLESHOOTING.md` - Camera connectivity troubleshooting
- `PETROL_BUNK_DEPLOYMENT_GUIDE.md` - Production deployment guide

## License

Proprietary - All Rights Reserved

## Configuration

### ANPR Configuration
```python
# Camera settings
RTSP_URL = "rtsp://username:password@camera_ip:554/stream"
CONFIDENCE_THRESHOLD = 0.7  # 70% confidence
DETECTION_INTERVAL = 2  # seconds

# Gate control
GATE_CONTROL_TYPE = "http"  # or "relay"
GATE_IP_ADDRESS = "192.168.1.200"
```

### Email Notifications
```python
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = "your_email@gmail.com"
MAIL_PASSWORD = "your_app_password"
```

## Subscription Plans

| Feature | Silver | Gold | Diamond |
|---------|--------|------|---------|
| Basic Dashboard | ✅ | ✅ | ✅ |
| OCR Processing | ✅ | ✅ | ✅ |
| Vehicle Counting | ❌ | ✅ | ✅ |
| Hydrotesting | ❌ | ✅ | ✅ |
| ANPR Gate Control | ❌ | ❌ | ✅ |
| Employee Attendance | ❌ | ❌ | ✅ |
| Price/Month | ₹999 | ₹1999 | ₹2999 |

## Support

For issues or questions, contact the development team.

## Contributing

This is a proprietary project. For contribution guidelines, contact the project maintainers.






