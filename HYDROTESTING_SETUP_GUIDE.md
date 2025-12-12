# Hydrotesting Feature - Quick Setup Guide

## 🚀 Quick Start (5 Minutes)

### Step 1: Run Database Migrations
```bash
# Navigate to project directory
cd e:\fuelflux\Flue_flex_pvt_ltd_

# Run migrations to create hydrotesting tables
flask db migrate -m "Add hydrotesting feature tables"
flask db upgrade
```

### Step 2: Start the Application
```bash
# Start the Flask application
python app.py
```

The application will automatically:
- ✅ Create upload directories
- ✅ Initialize database tables
- ✅ Start notification service
- ✅ Register hydrotesting blueprint

### Step 3: Access the Feature
1. Login as a Pump Owner
2. Navigate to Pump Dashboard
3. Look for **Silver Features** section
4. Click on **💧 Hydrotesting** (may be locked if no subscription)

**Direct URL**: `http://localhost:5001/hydrotesting/dashboard?pump_id=YOUR_PUMP_ID`

---

## 📋 Initial Setup Checklist

### Database Setup
- [x] Models created in `models.py`
- [x] Migration files generated
- [x] Tables created: `tanks`, `pipelines`, `hydrotests`, `hydrotest_files`, `hydrotest_notifications`, `contractor_master`

### Backend Setup
- [x] Blueprint registered in `app.py`
- [x] Routes created in `hydrotesting.py`
- [x] File upload directory created: `uploads/hydrotest_documents/`
- [x] Notification service started

### Frontend Setup
- [x] Dashboard template created
- [x] All UI screens created (8 templates)
- [x] Links added to pump dashboard
- [x] TailwindCSS styling applied

---

## 🎯 First-Time Usage

### 1. Add Your First Tank
```
Navigate to: Hydrotesting Dashboard → Manage Tanks → Add Tank

Fill in:
- Tank ID: TANK-001
- Tank Name: Petrol Storage Tank 1
- Capacity: 10000 (liters)
- Fuel Type: Petrol
- Location: Underground - North Side
- Installation Date: (optional)

Click: Add Tank
```

### 2. Add Your First Pipeline
```
Navigate to: Hydrotesting Dashboard → Manage Pipelines → Add Pipeline

Fill in:
- Line ID: LINE-A
- Pipeline Name: Main Petrol Supply Line
- Length: 50 (meters)
- Diameter: 100 (mm)
- Fuel Type: Petrol
- Location: Tank to Dispenser 1

Click: Add Pipeline
```

### 3. Record Your First Hydrotest
```
Navigate to: Hydrotesting Dashboard → Add New Test

Basic Information:
- Test Type: Tank Hydrotest
- Select Tank: Petrol Storage Tank 1
- Test Date: (today's date)

PESO Contractor:
- Contractor Name: ABC Testing Services
- Licence Number: PESO/2024/12345
- Certificate Number: CERT-2024-001

Technical Details:
- Test Pressure: 2.5 bar
- Hold Duration: 60 minutes
- Result: Pass
- Validity: 5 years
- Remarks: No pressure drop observed

Documents:
- Upload Hydrotest Certificate (PDF) - REQUIRED
- Upload Gas-Free Certificate (optional)
- Upload Photos (optional)

Click: Save Hydrotest Record
```

---

## 🔧 Configuration

### Email Notifications (Optional but Recommended)

Edit `.env` file:
```env
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER_NAME=FuelFlux Hydrotesting
```

**Gmail Setup**:
1. Enable 2-Factor Authentication
2. Generate App Password
3. Use App Password in `.env`

### File Upload Limits

Default settings in `hydrotesting.py`:
```python
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
UPLOAD_FOLDER = 'uploads/hydrotest_documents'
```

To change max file size, add to `config.py`:
```python
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
```

---

## 📊 Feature Access Control

### Current Implementation
The hydrotesting feature is listed under **Silver Features** in the pump dashboard.

### To Enable for All Users
Edit `templates/Pump-Owner/pump_dashboard.html`:

Find:
```html
<a href="{{ url_for('hydrotesting.dashboard', pump_id=pump.id) }}" 
   class="... locked opacity-50 pointer-events-none">💧 Hydrotesting 🔒</a>
```

Change to:
```html
<a href="{{ url_for('hydrotesting.dashboard', pump_id=pump.id) }}" 
   class="block py-2 px-3 rounded-lg border border-gray-600 hover:bg-fuel-black transition">
   💧 Hydrotesting
</a>
```

### To Enable Based on Subscription
Add subscription check in `hydrotesting.py`:
```python
@hydrotesting_bp.before_request
def check_subscription():
    if not isinstance(current_user, PumpOwner):
        return redirect(url_for('auth.login'))
    
    pump = get_current_pump()
    subscription = PumpSubscription.query.filter_by(
        pump_id=pump.id,
        subscription_status='active'
    ).first()
    
    if not subscription or subscription.subscription_type not in ['silver', 'gold', 'diamond']:
        flash('Hydrotesting feature requires Silver subscription or higher', 'error')
        return redirect(url_for('pump_dashboard.dashboard'))
```

---

## 🧪 Testing the Feature

### Test Scenario 1: Add Equipment and Test
```
1. Add a tank
2. Add a hydrotest for the tank
3. Upload certificate
4. View test details
5. Check dashboard shows correct status
```

### Test Scenario 2: Expiring Test Notification
```
1. Add a hydrotest with next_due_date = today + 30 days
2. Wait for notification service to run (or trigger manually)
3. Check email for notification
4. Verify notification banner on dashboard
```

### Test Scenario 3: Compliance Report
```
1. Add multiple tanks and pipelines
2. Add hydrotests with different statuses
3. Generate compliance report
4. Verify all equipment is listed
5. Print report to PDF
```

### Manual Notification Trigger (for testing)
```python
# In Python shell or temporary route
from hydrotest_notification_service import check_and_send_notifications, create_pending_notifications
from app import app

with app.app_context():
    create_pending_notifications(app)
    check_and_send_notifications(app)
```

---

## 🔍 Troubleshooting

### Issue: "No module named 'hydrotesting'"
**Solution**: Ensure `hydrotesting.py` is in the root directory and restart the app.

### Issue: "Table doesn't exist"
**Solution**: Run migrations:
```bash
flask db migrate
flask db upgrade
```

### Issue: "File upload fails"
**Solution**: 
1. Check `uploads/hydrotest_documents/` exists
2. Verify file permissions
3. Check file size limits

### Issue: "Notifications not sending"
**Solution**:
1. Verify email configuration in `.env`
2. Check notification service is running (look for startup message)
3. Check database for pending notifications:
```sql
SELECT * FROM hydrotest_notifications WHERE sent = 0;
```

### Issue: "Dashboard shows 404"
**Solution**: Ensure you're passing `pump_id` parameter:
```
http://localhost:5001/hydrotesting/dashboard?pump_id=1
```

---

## 📈 Advanced Features

### Variance Integration

To use variance analysis with hydrotesting:

```python
from hydrotest_variance_integration import analyze_variance_with_hydrotest

# Analyze variance for a tank
analysis = analyze_variance_with_hydrotest(
    tank_id=1,
    daily_variance=1.5,  # 1.5% variance
    variance_threshold=0.5
)

print(analysis['alert_level'])  # critical, high, medium, low, normal
print(analysis['message'])
print(analysis['recommendations'])
```

### PESO Compliance Validation

To validate a hydrotest record:

```python
from peso_compliance_validator import PESOComplianceValidator

# Validate hydrotest
validation = PESOComplianceValidator.validate_hydrotest_record(
    hydrotest=hydrotest_obj,
    files_by_type=files_dict
)

print(f"Valid: {validation['is_valid']}")
print(f"Score: {validation['compliance_score']}/100")
print(f"Errors: {validation['errors']}")
print(f"Warnings: {validation['warnings']}")
```

### Check Pump Compliance

```python
from peso_compliance_validator import PESOComplianceValidator

# Check overall compliance
compliance = PESOComplianceValidator.check_pump_compliance(pump_id=1)

print(f"Status: {compliance['peso_status']}")
print(f"Compliance: {compliance['compliance_percentage']}%")
print(f"Issues: {compliance['issues']}")
```

---

## 🎨 Customization

### Change Notification Thresholds

Edit `hydrotesting.py` in `create_notifications_for_hydrotest()`:
```python
notification_days = [90, 30, 0]  # Change to [120, 60, 30, 0] for more reminders
```

### Change Validity Periods

Edit `peso_compliance_validator.py`:
```python
TANK_HYDROTEST_VALIDITY_YEARS = 5  # Change as needed
PIPELINE_HYDROTEST_VALIDITY_YEARS = 5
```

### Customize Email Template

Edit `hydrotest_notification_service.py` in `check_and_send_notifications()`:
```python
body = f"""
Your custom email template here...
"""
```

---

## 📱 Mobile Responsiveness

All templates are mobile-responsive using TailwindCSS:
- Dashboard: Grid layout adapts to screen size
- Forms: Stack vertically on mobile
- Tables: Horizontal scroll on small screens
- Cards: Single column on mobile

---

## 🔐 Security Best Practices

1. **File Upload Security**
   - Only allowed file types accepted
   - Unique filenames (UUID)
   - Stored outside web root

2. **Access Control**
   - Login required for all routes
   - Pump owners can only access their own data
   - CSRF protection on all forms

3. **Data Retention**
   - 5-year minimum retention
   - Audit trail with created_by
   - No deletion without admin approval

---

## 📞 Support

### Common Questions

**Q: Can I delete a hydrotest record?**
A: Currently, deletion is not implemented for compliance reasons. Contact admin if needed.

**Q: How do I add PESO contractors?**
A: Contractors must be added by admin to the `contractor_master` table.

**Q: Can I export data?**
A: Yes, use the Compliance Report and print to PDF.

**Q: What happens if I miss a test deadline?**
A: The system marks it as expired and sends alerts. Schedule testing immediately.

---

## 🎯 Next Steps

After setup, you should:

1. ✅ Add all your tanks and pipelines
2. ✅ Upload existing hydrotest records
3. ✅ Configure email notifications
4. ✅ Review compliance report
5. ✅ Set up regular monitoring schedule
6. ✅ Train staff on the system
7. ✅ Schedule upcoming tests

---

## 📚 Additional Resources

- **Full Documentation**: `HYDROTESTING_FEATURE_DOCUMENTATION.md`
- **API Reference**: See `hydrotesting.py` for all endpoints
- **Database Schema**: See `models.py` for table structures
- **Variance Integration**: See `hydrotest_variance_integration.py`
- **PESO Validation**: See `peso_compliance_validator.py`

---

**Version**: 1.0.0  
**Last Updated**: December 2025  
**Status**: Production Ready ✅

---

## 🎉 You're All Set!

Your hydrotesting feature is now fully configured and ready to use. Start by adding your equipment and recording your first hydrotest!

For questions or issues, refer to the troubleshooting section or contact support.
