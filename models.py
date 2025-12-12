# models.py
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import func

class User(db.Model, UserMixin):  
    __tablename__ = "users"  # explicit table name
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)  # NULL for Google users

    # Relationships
    vehicles = db.relationship("Vehicle", backref="user", lazy=True)
    wallet = db.relationship("Wallet", backref="user", uselist=False, cascade="all, delete-orphan")

    # Password methods
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password) if self.password_hash else False

    @property
    def wallet_balance(self):
        return self.wallet.balance if self.wallet else 0.0

    # Debugging representation
    def __repr__(self):
        return f"<User {self.email} | Wallet: {self.wallet_balance}>"


class Vehicle(db.Model):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(10), nullable=False)
    license = db.Column(db.String(50), nullable=False)
    fuel_type = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class Wallet(db.Model):
    __tablename__ = "wallets"
    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)



# --------------------------
# Pump Owner Models
# --------------------------

class PumpOwner(db.Model, UserMixin):
    __tablename__ = "pump_owners"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)

    # Relationships
    pumps = db.relationship("Pump", backref="owner", lazy=True)
    wallet = db.relationship("PumpWallet", backref="owner", uselist=False, cascade="all, delete-orphan")

    def get_id(self):
        return f"pump_{self.id}"

    # Password methods
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<PumpOwner {self.email} | Wallet: {self.wallet.balance if self.wallet else 0}>"


class Pump(db.Model):
    __tablename__ = "pumps"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    fuel_types = db.Column(db.String(200), nullable=True)  # e.g., "Petrol, Diesel, CNG"
    owner_id = db.Column(db.Integer, db.ForeignKey('pump_owners.id'), nullable=False)
    
    # Admin verification fields
    is_verified = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)
    verified_at = db.Column(db.DateTime, nullable=True)


class PumpWallet(db.Model):
    __tablename__ = "pump_wallets"
    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Float, default=0.0)
    owner_id = db.Column(db.Integer, db.ForeignKey('pump_owners.id'), nullable=False)


class PumpSubscription(db.Model):
    __tablename__ = "pump_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    email = db.Column(db.String(120), nullable=False)

    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    pump_name = db.Column(db.String(150), nullable=False)
    pump_location = db.Column(db.String(200), nullable=False)

    subscription_status = db.Column(db.String(20), nullable=False, default="not taken")  
    subscription_type = db.Column(db.String(50), nullable=True)  # silver, gold, diamond, or None
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)


class StationVehicle(db.Model):
    __tablename__ = "station_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    station_name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    rtsp_url = db.Column(db.String(500), nullable=False)  # RTSP stream URL

    # Relationship to PumpOwner
    owner = db.relationship("PumpOwner", backref="station_vehicles")

    def __repr__(self):
        return f"<StationVehicle {self.station_name} | Owner ID: {self.owner_id}>"


class VehicleVerification(db.Model):
    __tablename__ = "vehicle_verifications"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    station_name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    rtsp_url = db.Column(db.String(500), nullable=False)  # RTSP stream URL

    # Relationship to PumpOwner
    owner = db.relationship("PumpOwner", backref="vehicle_verifications")

    def __repr__(self):
        return f"<StationVehicle {self.station_name} | Owner ID: {self.owner_id}>"
    
    
class VehicleDetails(db.Model):
    __tablename__ = "vehicle_details"

    plate_number = db.Column(db.String(20), primary_key=True)  # license plate as primary key
    pump_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    detected_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    # Relationship to PumpOwner
    pump = db.relationship("PumpOwner", backref="detected_vehicles")

    def __repr__(self):
        return f"<VehicleDetails {self.plate_number} | Pump ID: {self.pump_id} | Detected at: {self.detected_at}>"


class PumpReceipt(db.Model):
    __tablename__ = "pump_receipts"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    ocr_data = db.Column(db.JSON, nullable=True)
    print_date = db.Column(db.DateTime, nullable=True)
    total_sales = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())

    owner = db.relationship("PumpOwner", backref="receipts")
    pump = db.relationship("Pump", backref="receipts")

    def __repr__(self):
        return f"<PumpReceipt pump={self.pump_id} date={self.print_date}>"


class PaymentVerification(db.Model):
    """Model to store payment screenshot submissions for admin verification"""
    __tablename__ = "payment_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    
    plan_type = db.Column(db.String(50), nullable=False)  # Silver, Gold, Diamond
    duration = db.Column(db.String(50), nullable=False)  # 1 Month, 6 Months, Annual
    amount = db.Column(db.Float, nullable=False)
    
    screenshot_filename = db.Column(db.String(255), nullable=False)  # Payment proof
    transaction_id = db.Column(db.String(100), nullable=True)  # Optional UTR/Transaction ID
    
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, server_default=func.now())
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.String(120), nullable=True)  # Admin email
    rejection_reason = db.Column(db.Text, nullable=True)
    
    owner = db.relationship("PumpOwner", backref="payment_verifications")
    pump = db.relationship("Pump", backref="payment_verifications")

    def __repr__(self):
        return f"<PaymentVerification user={self.user_email} amount={self.amount} status={self.status}>"


class PumpRegistrationRequest(db.Model):
    """Model to store pump registration requests for admin approval"""
    __tablename__ = "pump_registration_requests"

    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    
    owner_name = db.Column(db.String(100), nullable=False)
    pump_address = db.Column(db.Text, nullable=False)
    contact_number = db.Column(db.String(20), nullable=False)
    opening_time = db.Column(db.String(10), nullable=False)
    closing_time = db.Column(db.String(10), nullable=False)
    
    documents = db.Column(db.JSON, nullable=True)  # List of uploaded document filenames
    
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, server_default=func.now())
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.String(120), nullable=True)  # Admin email
    rejection_reason = db.Column(db.Text, nullable=True)
    
    owner = db.relationship("PumpOwner", backref="registration_requests")
    pump = db.relationship("Pump", backref="registration_requests")

    def __repr__(self):
        return f"<PumpRegistrationRequest pump={self.pump_id} status={self.status}>"


class Admin(db.Model, UserMixin):
    """Admin model for admin panel authentication"""
    __tablename__ = "admins"
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return f"admin_{self.id}"
    
    def __repr__(self):
        return f"<Admin {self.email}>"


class Employee(db.Model):
    """Employee model for pump employees"""
    __tablename__ = "employees"
    
    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    designation = db.Column(db.String(100), nullable=True)  # e.g., "Cashier", "Attendant", "Manager"
    employee_id = db.Column(db.String(50), nullable=True)  # Employee ID number
    
    # Face recognition data
    photo_filename = db.Column(db.String(255), nullable=False)  # Stored photo filename
    face_encoding = db.Column(db.LargeBinary, nullable=True)  # Serialized face encoding
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    pump = db.relationship("Pump", backref="employees")
    owner = db.relationship("PumpOwner", backref="employees")
    attendance_records = db.relationship("Attendance", backref="employee", lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Employee {self.name} | Pump ID: {self.pump_id}>"


class Attendance(db.Model):
    """Attendance records for employees"""
    __tablename__ = "attendance"
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    
    # Attendance date and time
    attendance_date = db.Column(db.Date, nullable=False)  # Date of attendance
    check_in_time = db.Column(db.DateTime, nullable=True)  # First check-in
    check_out_time = db.Column(db.DateTime, nullable=True)  # Last check-out
    
    # Status
    status = db.Column(db.String(20), default="present")  # present, absent, late, half_day
    total_hours = db.Column(db.Float, nullable=True)  # Total working hours
    
    # Detection method
    detection_method = db.Column(db.String(20), default="face_recognition")  # face_recognition, manual
    detected_confidence = db.Column(db.Float, nullable=True)  # Confidence score if face recognition
    
    # Notes
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    # Relationships
    pump = db.relationship("Pump", backref="attendance_records")
    
    def __repr__(self):
        return f"<Attendance Employee ID: {self.employee_id} | Date: {self.attendance_date} | Status: {self.status}>"


class Tank(db.Model):
    """Model for storage tanks at petrol bunks"""
    __tablename__ = "tanks"
    
    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    
    tank_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Float, nullable=False)
    fuel_type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    installation_date = db.Column(db.Date, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    
    pump = db.relationship("Pump", backref="tanks")
    owner = db.relationship("PumpOwner", backref="tanks")
    hydrotests = db.relationship("Hydrotest", backref="tank", lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Tank {self.tank_id} | Capacity: {self.capacity}L | Pump ID: {self.pump_id}>"


class Pipeline(db.Model):
    """Model for pipelines at petrol bunks"""
    __tablename__ = "pipelines"
    
    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    
    line_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    length = db.Column(db.Float, nullable=False)
    diameter = db.Column(db.Float, nullable=True)
    fuel_type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    installation_date = db.Column(db.Date, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    
    pump = db.relationship("Pump", backref="pipelines")
    owner = db.relationship("PumpOwner", backref="pipelines")
    hydrotests = db.relationship("Hydrotest", backref="pipeline", lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Pipeline {self.line_id} | Length: {self.length}m | Pump ID: {self.pump_id}>"


class Hydrotest(db.Model):
    """Model for hydrotest records"""
    __tablename__ = "hydrotests"
    
    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    
    tank_id = db.Column(db.Integer, db.ForeignKey("tanks.id"), nullable=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey("pipelines.id"), nullable=True)
    
    test_type = db.Column(db.String(50), nullable=False)
    test_date = db.Column(db.Date, nullable=False)
    
    peso_contractor_name = db.Column(db.String(200), nullable=False)
    competent_person_licence = db.Column(db.String(100), nullable=False)
    
    test_pressure = db.Column(db.Float, nullable=False)
    pressure_unit = db.Column(db.String(10), default="bar")
    hold_duration = db.Column(db.Integer, nullable=False)
    
    result = db.Column(db.String(20), nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    
    next_due_date = db.Column(db.Date, nullable=False)
    validity_years = db.Column(db.Integer, default=5)
    
    peso_approved = db.Column(db.Boolean, default=False)
    peso_approval_date = db.Column(db.Date, nullable=True)
    peso_certificate_number = db.Column(db.String(100), nullable=True)
    
    created_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    
    pump = db.relationship("Pump", backref="hydrotests")
    owner = db.relationship("PumpOwner", backref="hydrotests")
    files = db.relationship("HydrotestFile", backref="hydrotest", lazy=True, cascade="all, delete-orphan")
    
    def get_compliance_status(self):
        """Calculate compliance status based on next due date"""
        from datetime import datetime, timedelta
        
        if not self.next_due_date:
            return "unknown"
        
        today = datetime.now().date()
        days_until_expiry = (self.next_due_date - today).days
        
        if days_until_expiry < 0:
            return "expired"
        elif days_until_expiry <= 30:
            return "due_soon"
        elif days_until_expiry <= 90:
            return "warning"
        else:
            return "compliant"
    
    def get_days_until_expiry(self):
        """Get days until test expiry"""
        from datetime import datetime
        
        if not self.next_due_date:
            return None
        
        today = datetime.now().date()
        return (self.next_due_date - today).days
    
    def __repr__(self):
        return f"<Hydrotest {self.test_type} | Date: {self.test_date} | Result: {self.result}>"


class HydrotestFile(db.Model):
    """Model for hydrotest document uploads"""
    __tablename__ = "hydrotest_files"
    
    id = db.Column(db.Integer, primary_key=True)
    hydrotest_id = db.Column(db.Integer, db.ForeignKey("hydrotests.id"), nullable=False)
    
    file_type = db.Column(db.String(50), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    
    uploaded_at = db.Column(db.DateTime, server_default=func.now())
    uploaded_by = db.Column(db.String(100), nullable=True)
    
    def __repr__(self):
        return f"<HydrotestFile {self.file_type} | Hydrotest ID: {self.hydrotest_id}>"


class HydrotestNotification(db.Model):
    """Model for hydrotest expiry notifications"""
    __tablename__ = "hydrotest_notifications"
    
    id = db.Column(db.Integer, primary_key=True)
    hydrotest_id = db.Column(db.Integer, db.ForeignKey("hydrotests.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)
    
    notification_type = db.Column(db.String(50), nullable=False)
    notification_date = db.Column(db.Date, nullable=False)
    days_before_expiry = db.Column(db.Integer, nullable=False)
    
    sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    
    email_sent = db.Column(db.Boolean, default=False)
    sms_sent = db.Column(db.Boolean, default=False)
    
    message = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    hydrotest = db.relationship("Hydrotest", backref="notifications")
    owner = db.relationship("PumpOwner", backref="hydrotest_notifications")
    
    def __repr__(self):
        return f"<HydrotestNotification Type: {self.notification_type} | Days: {self.days_before_expiry}>"


class ContractorMaster(db.Model):
    """Model for PESO contractor master data"""
    __tablename__ = "contractor_master"
    
    id = db.Column(db.Integer, primary_key=True)
    
    contractor_name = db.Column(db.String(200), nullable=False)
    licence_number = db.Column(db.String(100), unique=True, nullable=False)
    contact_person = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    
    peso_registration_number = db.Column(db.String(100), nullable=True)
    licence_valid_from = db.Column(db.Date, nullable=True)
    licence_valid_until = db.Column(db.Date, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    is_peso_verified = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ContractorMaster {self.contractor_name} | Licence: {self.licence_number}>"


# ==================== ANPR Vehicle Compliance Models ====================

class VehicleCompliance(db.Model):
    """Vehicle compliance records for ANPR gate control"""
    __tablename__ = "vehicle_compliance"
    
    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey('pumps.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('pump_owners.id'), nullable=False)
    
    # Vehicle Information
    vehicle_number = db.Column(db.String(20), nullable=False, index=True)
    vehicle_type = db.Column(db.String(50), nullable=False)
    vehicle_make = db.Column(db.String(100))
    vehicle_model = db.Column(db.String(100))
    
    # Hydrotest Information
    hydrotest_expiry_date = db.Column(db.Date, nullable=False)
    last_hydrotest_date = db.Column(db.Date)
    hydrotest_certificate_number = db.Column(db.String(100))
    hydrotest_certificate_path = db.Column(db.String(500))
    
    # Compliance Status
    is_compliant = db.Column(db.Boolean, default=True)
    compliance_status = db.Column(db.String(20), default='compliant')
    
    # Additional Details
    owner_name = db.Column(db.String(200))
    owner_contact = db.Column(db.String(20))
    remarks = db.Column(db.Text)
    
    # Access Control
    is_blacklisted = db.Column(db.Boolean, default=False)
    blacklist_reason = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    entry_logs = db.relationship('VehicleEntryLog', backref='vehicle', lazy=True, cascade="all, delete-orphan")
    
    def get_compliance_status(self):
        """Calculate current compliance status"""
        from datetime import date
        today = date.today()
        
        if self.is_blacklisted:
            return 'blacklisted'
        
        if self.hydrotest_expiry_date < today:
            self.is_compliant = False
            self.compliance_status = 'expired'
            return 'expired'
        
        days_until_expiry = (self.hydrotest_expiry_date - today).days
        
        if days_until_expiry <= 30:
            self.compliance_status = 'expiring_soon'
            return 'expiring_soon'
        
        self.is_compliant = True
        self.compliance_status = 'compliant'
        return 'compliant'
    
    def get_days_until_expiry(self):
        """Get days until hydrotest expiry"""
        from datetime import date
        return (self.hydrotest_expiry_date - date.today()).days
    
    def __repr__(self):
        return f"<VehicleCompliance {self.vehicle_number} | Status: {self.compliance_status}>"


class VehicleEntryLog(db.Model):
    """Log of vehicle entries detected by ANPR"""
    __tablename__ = "vehicle_entry_logs"
    
    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey('pumps.id'), nullable=False)
    vehicle_compliance_id = db.Column(db.Integer, db.ForeignKey('vehicle_compliance.id'), nullable=True)
    
    # Detection Information
    vehicle_number = db.Column(db.String(20), nullable=False, index=True)
    detected_at = db.Column(db.DateTime, server_default=func.now())
    detection_confidence = db.Column(db.Float)
    
    # Image Data
    image_path = db.Column(db.String(500))
    plate_image_path = db.Column(db.String(500))
    
    # Compliance Check Result
    compliance_status = db.Column(db.String(20))
    is_allowed_entry = db.Column(db.Boolean, default=False)
    gate_action = db.Column(db.String(20))
    
    # Alert Information
    alert_triggered = db.Column(db.Boolean, default=False)
    alert_message = db.Column(db.Text)
    
    # Manual Override
    manual_override = db.Column(db.Boolean, default=False)
    override_by = db.Column(db.String(100))
    override_reason = db.Column(db.Text)
    
    # Exit Information
    exit_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)
    
    def __repr__(self):
        return f"<VehicleEntryLog {self.vehicle_number} | {self.detected_at} | {self.compliance_status}>"


class ANPRCamera(db.Model):
    """ANPR Camera configuration for each pump"""
    __tablename__ = "anpr_cameras"
    
    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey('pumps.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('pump_owners.id'), nullable=False)
    
    # Camera Information
    camera_name = db.Column(db.String(100), nullable=False)
    camera_location = db.Column(db.String(200))
    rtsp_url = db.Column(db.String(500), nullable=False)
    
    # Camera Settings
    is_active = db.Column(db.Boolean, default=True)
    detection_enabled = db.Column(db.Boolean, default=True)
    gate_control_enabled = db.Column(db.Boolean, default=False)
    
    # Detection Settings
    confidence_threshold = db.Column(db.Float, default=0.7)
    detection_interval_seconds = db.Column(db.Integer, default=2)
    
    # Gate Control Settings
    gate_ip_address = db.Column(db.String(50))
    gate_control_type = db.Column(db.String(50))
    auto_close_delay_seconds = db.Column(db.Integer, default=10)
    
    # Timestamps
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    last_active_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f"<ANPRCamera {self.camera_name} | Pump: {self.pump_id}>"
