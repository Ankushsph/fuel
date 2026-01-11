# models.py
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import func, UniqueConstraint
from datetime import datetime

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
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
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


class EscrowAccount(db.Model):
    __tablename__ = "escrow_accounts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, default="main")
    balance = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, server_default=func.now())


class WalletTopup(db.Model):
    __tablename__ = "wallet_topups"

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey("wallets.id"), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="INR")

    txn_uuid = db.Column(db.String(36), nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False, default="created")

    razorpay_order_id = db.Column(db.String(100), nullable=True)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)
    razorpay_signature = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, server_default=func.now())
    paid_at = db.Column(db.DateTime, nullable=True)

    driver = db.relationship("User", backref="wallet_topups")
    wallet = db.relationship("Wallet", backref="topups")


class FuelTransaction(db.Model):
    __tablename__ = "fuel_transactions"

    id = db.Column(db.Integer, primary_key=True)
    pump_id = db.Column(db.Integer, db.ForeignKey("pumps.id"), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False, index=True)
    fuel_type = db.Column(db.String(20), nullable=False)
    quantity_litres = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending_verification", index=True)  # pending_verification, verified, settled, failed
    verification_level = db.Column(db.String(20), nullable=False, default="manual")  # manual, semi_auto, auto
    attendant_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=True)  # who recorded the transaction
    verifier_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=True)  # who verified
    verified_at = db.Column(db.DateTime, nullable=True)
    settled_at = db.Column(db.DateTime, nullable=True)
    extra_data = db.Column(db.JSON, nullable=True)  # OCR results, pump pulse data, ANPR confidence, etc.
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    pump = db.relationship("Pump", backref="fuel_transactions")
    attendant = db.relationship("PumpOwner", foreign_keys=[attendant_id], backref="attended_transactions")
    verifier = db.relationship("PumpOwner", foreign_keys=[verifier_id], backref="verified_transactions")


class WalletLedgerEntry(db.Model):
    __tablename__ = "wallet_ledger_entries"
    id = db.Column(db.Integer, primary_key=True)
    group_uuid = db.Column(db.String(36), nullable=False, index=True)  # UUID to group related entries (e.g., a fuel transaction)
    event_type = db.Column(db.String(32), nullable=False)  # fuel_sale, wallet_topup, settlement, refund
    direction = db.Column(db.String(16), nullable=False)  # debit or credit
    wallet_type = db.Column(db.String(16), nullable=False)  # driver_wallet, pump_wallet, escrow
    wallet_id = db.Column(db.Integer, nullable=False)  # driver wallet.id or pump_wallet.id
    amount = db.Column(db.Float, nullable=False)
    balance_after = db.Column(db.Float, nullable=False)
    reference_id = db.Column(db.Integer, nullable=True)  # FuelTransaction.id, WalletTopupVerification.id, etc.
    reference_type = db.Column(db.String(32), nullable=True)  # fuel_transaction, wallet_topup, settlement
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    # No updates; ledger entries are immutable


class PumpSettlement(db.Model):
    __tablename__ = "pump_settlements"

    id = db.Column(db.Integer, primary_key=True)
    pump_wallet_id = db.Column(db.Integer, db.ForeignKey("pump_wallets.id"), nullable=False)
    pump_owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="INR")
    status = db.Column(db.String(20), nullable=False, default="pending")

    bank_reference = db.Column(db.String(100), nullable=True)
    requested_at = db.Column(db.DateTime, server_default=func.now())
    processed_at = db.Column(db.DateTime, nullable=True)

    pump_wallet = db.relationship("PumpWallet", backref="settlements")
    pump_owner = db.relationship("PumpOwner", backref="settlements")


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


class VehicleLocation(db.Model):
    __tablename__ = "vehicle_locations"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    vehicle_number = db.Column(db.String(20), nullable=False, index=True)

    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed_kmph = db.Column(db.Float, nullable=True)
    heading_deg = db.Column(db.Float, nullable=True)
    accuracy_m = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(20), nullable=False, default="gps")

    recorded_at = db.Column(db.DateTime, server_default=func.now(), nullable=False, index=True)

    owner = db.relationship("PumpOwner", backref="vehicle_locations")
    user = db.relationship("User", backref="vehicle_locations")


class LogisticsPartner(db.Model):
    __tablename__ = "logistics_partners"

    id = db.Column(db.Integer, primary_key=True)
    partner_type = db.Column(db.Enum("pump_owner", "user", name="logistics_partner_type"), nullable=False)
    pump_owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    pump_owner = db.relationship("PumpOwner", backref=db.backref("logistics_partner", uselist=False))
    user = db.relationship("User", backref=db.backref("logistics_partner", uselist=False))


class LogisticsVehicleType(db.Model):
    __tablename__ = "logistics_vehicle_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    capacity_tons = db.Column(db.Float, nullable=False)
    fixed_cost = db.Column(db.Float, nullable=False, default=0.0)
    variable_cost_per_km = db.Column(db.Float, nullable=False, default=0.0)
    sbq_tons = db.Column(db.Float, nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LogisticsVehicle(db.Model):
    __tablename__ = "logistics_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("logistics_partners.id"), nullable=False, index=True)
    vehicle_type_id = db.Column(db.Integer, db.ForeignKey("logistics_vehicle_types.id"), nullable=False, index=True)
    vehicle_number = db.Column(db.String(40), nullable=False, index=True)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    partner = db.relationship("LogisticsPartner", backref=db.backref("vehicles", cascade="all, delete-orphan", lazy=True))
    vehicle_type = db.relationship("LogisticsVehicleType")

    __table_args__ = (
        UniqueConstraint("partner_id", "vehicle_number", name="uq_logistics_vehicle_partner_number"),
    )


class LogisticsBooking(db.Model):
    __tablename__ = "logistics_bookings"

    id = db.Column(db.Integer, primary_key=True)
    requester_owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=True, index=True)
    requester_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=True, index=True)

    from_location = db.Column(db.String(200))
    to_location = db.Column(db.String(200))
    distance_km = db.Column(db.Float)
    period = db.Column(db.Integer)
    quantity_tons = db.Column(db.Float, nullable=False)
    single_vehicle = db.Column(db.Boolean, nullable=False, default=False)

    status = db.Column(db.String(30), nullable=False, default="created", index=True)
    selected_vehicle_id = db.Column(db.Integer, db.ForeignKey("logistics_vehicles.id"), nullable=True, index=True)
    estimated_cost = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    requester_owner = db.relationship("PumpOwner", backref=db.backref("logistics_bookings", lazy=True))
    requester_user = db.relationship("User", backref=db.backref("logistics_bookings", lazy=True))
    scenario = db.relationship("ClinkerScenario", backref=db.backref("logistics_bookings", lazy=True))
    selected_vehicle = db.relationship("LogisticsVehicle")


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


class WalletTopupVerification(db.Model):
    __tablename__ = "wallet_topup_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    screenshot_filename = db.Column(db.String(255), nullable=False)
    transaction_id = db.Column(db.String(100), nullable=True)

    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, server_default=func.now())
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.String(120), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    user = db.relationship("User", backref="wallet_topup_verifications")

    def __repr__(self):
        return f"<WalletTopupVerification user={self.user_email} amount={self.amount} status={self.status}>"


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
        return f"<VehicleEntryLog {self.vehicle_number} | Entry: {self.detected_at}>"


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


# ==================== INVESTOR PORTAL MODELS ====================

class Investor(db.Model, UserMixin):
    """Investor account for accessing investor portal"""
    __tablename__ = "investors"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        return f"investor_{self.id}"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Investor {self.email}>"

class ClinkerScenario(db.Model):
    __tablename__ = "clinker_scenarios"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("pump_owners.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    num_periods = db.Column(db.Integer, nullable=False)
    period_type = db.Column(db.String(20), nullable=False, default="day")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = db.relationship("PumpOwner", backref=db.backref("clinker_scenarios", lazy=True))


class ClinkerPlant(db.Model):
    __tablename__ = "clinker_plants"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    plant_type = db.Column(db.Enum("IU", "GU", name="clinker_plant_type"), nullable=False)
    location = db.Column(db.String(200))
    initial_inventory = db.Column(db.Float, nullable=False, default=0.0)
    safety_stock_requirement = db.Column(db.Float, nullable=False, default=0.0)
    holding_cost_per_ton = db.Column(db.Float, nullable=False, default=0.0)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("plants", cascade="all, delete-orphan", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("scenario_id", "name", name="uq_clinker_plant_scenario_name"),
    )


class ClinkerProductionCapacity(db.Model):
    __tablename__ = "clinker_production_capacities"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    max_capacity = db.Column(db.Float, nullable=False)
    production_cost_per_ton = db.Column(db.Float, nullable=False)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("production_capacities", cascade="all, delete-orphan", lazy=True),
    )
    plant = db.relationship(
        "ClinkerPlant",
        backref=db.backref("production_capacities", cascade="all, delete-orphan", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("scenario_id", "plant_id", "period", name="uq_clinker_prodcap"),
    )


class ClinkerDemandRequirement(db.Model):
    __tablename__ = "clinker_demand_requirements"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    demand_quantity = db.Column(db.Float, nullable=False)
    min_fulfillment_pct = db.Column(db.Float, nullable=False, default=100.0)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("demands", cascade="all, delete-orphan", lazy=True),
    )
    plant = db.relationship(
        "ClinkerPlant",
        backref=db.backref("demands", cascade="all, delete-orphan", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("scenario_id", "plant_id", "period", name="uq_clinker_demand"),
    )


class ClinkerInventoryBound(db.Model):
    __tablename__ = "clinker_inventory_bounds"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    min_closing_stock = db.Column(db.Float)
    max_closing_stock = db.Column(db.Float)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("inventory_bounds", cascade="all, delete-orphan", lazy=True),
    )
    plant = db.relationship(
        "ClinkerPlant",
        backref=db.backref("inventory_bounds", cascade="all, delete-orphan", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("scenario_id", "plant_id", "period", name="uq_clinker_inventory_bound"),
    )


class ClinkerTransportMode(db.Model):
    __tablename__ = "clinker_transport_modes"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    cost_per_trip = db.Column(db.Float, nullable=False)
    capacity_per_trip = db.Column(db.Float, nullable=False)
    minimum_shipment = db.Column(db.Float, nullable=False, default=0.0)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("transport_modes", cascade="all, delete-orphan", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("scenario_id", "name", name="uq_clinker_transport_mode_name"),
    )


class ClinkerTransportLane(db.Model):
    __tablename__ = "clinker_transport_lanes"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    source_plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    destination_plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    mode_id = db.Column(db.Integer, db.ForeignKey("clinker_transport_modes.id"), nullable=False, index=True)
    cost_per_trip_override = db.Column(db.Float)
    capacity_per_trip_override = db.Column(db.Float)
    minimum_shipment_override = db.Column(db.Float)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("transport_lanes", cascade="all, delete-orphan", lazy=True),
    )
    source_plant = db.relationship("ClinkerPlant", foreign_keys=[source_plant_id])
    destination_plant = db.relationship("ClinkerPlant", foreign_keys=[destination_plant_id])
    mode = db.relationship("ClinkerTransportMode")

    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "source_plant_id",
            "destination_plant_id",
            "mode_id",
            name="uq_clinker_lane",
        ),
    )


class ClinkerTransportLanePeriod(db.Model):
    __tablename__ = "clinker_transport_lane_periods"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    lane_id = db.Column(db.Integer, db.ForeignKey("clinker_transport_lanes.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    cost_per_trip_override = db.Column(db.Float)
    capacity_per_trip_override = db.Column(db.Float)
    minimum_shipment_override = db.Column(db.Float)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("transport_lane_periods", cascade="all, delete-orphan", lazy=True),
    )
    lane = db.relationship(
        "ClinkerTransportLane",
        backref=db.backref("period_overrides", cascade="all, delete-orphan", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("scenario_id", "lane_id", "period", name="uq_clinker_lane_period"),
    )


class ClinkerLaneCostBound(db.Model):
    __tablename__ = "clinker_lane_cost_bounds"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    lane_id = db.Column(db.Integer, db.ForeignKey("clinker_transport_lanes.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    bound_type = db.Column(db.Enum("L", "E", name="clinker_cost_bound_type"), nullable=False)
    value = db.Column(db.Float, nullable=False)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("lane_cost_bounds", cascade="all, delete-orphan", lazy=True),
    )
    lane = db.relationship(
        "ClinkerTransportLane",
        backref=db.backref("cost_bounds", cascade="all, delete-orphan", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("scenario_id", "lane_id", "period", name="uq_clinker_lane_cost_bound"),
    )


class ClinkerDataImport(db.Model):
    __tablename__ = "clinker_data_imports"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    source_type = db.Column(db.String(40), nullable=False, default="xlsx")
    filename = db.Column(db.String(255))
    report_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("data_imports", cascade="all, delete-orphan", lazy=True),
    )


class ClinkerOptimizationRun(db.Model):
    __tablename__ = "clinker_optimization_runs"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default="created")
    solver_status = db.Column(db.String(60))
    total_cost = db.Column(db.Float)
    production_cost = db.Column(db.Float)
    transport_cost = db.Column(db.Float)
    holding_cost = db.Column(db.Float)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("runs", cascade="all, delete-orphan", lazy=True),
    )


class ClinkerDemandFulfillment(db.Model):
    __tablename__ = "clinker_demand_fulfillments"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("clinker_optimization_runs.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    demand_quantity = db.Column(db.Float, nullable=False, default=0.0)
    served_quantity = db.Column(db.Float, nullable=False, default=0.0)
    unmet_quantity = db.Column(db.Float, nullable=False, default=0.0)

    run = db.relationship(
        "ClinkerOptimizationRun",
        backref=db.backref("demand_fulfillments", cascade="all, delete-orphan", lazy=True),
    )
    plant = db.relationship("ClinkerPlant")

    __table_args__ = (
        UniqueConstraint("run_id", "plant_id", "period", name="uq_clinker_demand_fulfillment"),
    )


class ClinkerDemandScenario(db.Model):
    __tablename__ = "clinker_demand_scenarios"

    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    probability = db.Column(db.Float, nullable=False, default=1.0)
    multiplier = db.Column(db.Float, nullable=False, default=1.0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("demand_scenarios", cascade="all, delete-orphan", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("scenario_id", "name", name="uq_clinker_demand_scenario_name"),
    )


class ClinkerDemandScenarioOverride(db.Model):
    __tablename__ = "clinker_demand_scenario_overrides"

    id = db.Column(db.Integer, primary_key=True)
    demand_scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_demand_scenarios.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    demand_quantity = db.Column(db.Float, nullable=False)

    demand_scenario = db.relationship(
        "ClinkerDemandScenario",
        backref=db.backref("overrides", cascade="all, delete-orphan", lazy=True),
    )
    plant = db.relationship("ClinkerPlant")

    __table_args__ = (
        UniqueConstraint("demand_scenario_id", "plant_id", "period", name="uq_clinker_demand_scenario_override"),
    )


class ClinkerUncertaintyRunGroup(db.Model):
    __tablename__ = "clinker_uncertainty_run_groups"

    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_scenarios.id"), nullable=False, index=True)
    method = db.Column(db.Enum("scenario", name="clinker_uncertainty_method"), nullable=False, default="scenario")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scenario = db.relationship(
        "ClinkerScenario",
        backref=db.backref("uncertainty_run_groups", cascade="all, delete-orphan", lazy=True),
    )


class ClinkerUncertaintyScenarioRun(db.Model):
    __tablename__ = "clinker_uncertainty_scenario_runs"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("clinker_uncertainty_run_groups.id"), nullable=False, index=True)
    demand_scenario_id = db.Column(db.Integer, db.ForeignKey("clinker_demand_scenarios.id"), nullable=False, index=True)
    run_id = db.Column(db.Integer, db.ForeignKey("clinker_optimization_runs.id"), nullable=False, index=True)
    probability = db.Column(db.Float, nullable=False, default=1.0)
    expected_cost_component = db.Column(db.Float)

    group = db.relationship(
        "ClinkerUncertaintyRunGroup",
        backref=db.backref("scenario_runs", cascade="all, delete-orphan", lazy=True),
    )
    demand_scenario = db.relationship("ClinkerDemandScenario")
    run = db.relationship("ClinkerOptimizationRun")

    __table_args__ = (
        UniqueConstraint("group_id", "demand_scenario_id", name="uq_clinker_uncertainty_group_scenario"),
    )


class ClinkerProductionPlan(db.Model):
    __tablename__ = "clinker_production_plans"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("clinker_optimization_runs.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    production_quantity = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, nullable=False, default=0.0)

    run = db.relationship(
        "ClinkerOptimizationRun",
        backref=db.backref("production_plans", cascade="all, delete-orphan", lazy=True),
    )
    plant = db.relationship("ClinkerPlant")

    __table_args__ = (
        UniqueConstraint("run_id", "plant_id", "period", name="uq_clinker_prodplan"),
    )


class ClinkerShipmentPlan(db.Model):
    __tablename__ = "clinker_shipment_plans"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("clinker_optimization_runs.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    source_plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    destination_plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    mode_id = db.Column(db.Integer, db.ForeignKey("clinker_transport_modes.id"), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    trips = db.Column(db.Integer, nullable=False)
    cost = db.Column(db.Float, nullable=False, default=0.0)

    run = db.relationship(
        "ClinkerOptimizationRun",
        backref=db.backref("shipment_plans", cascade="all, delete-orphan", lazy=True),
    )
    source_plant = db.relationship("ClinkerPlant", foreign_keys=[source_plant_id])
    destination_plant = db.relationship("ClinkerPlant", foreign_keys=[destination_plant_id])
    mode = db.relationship("ClinkerTransportMode")


class ClinkerInventoryLevel(db.Model):
    __tablename__ = "clinker_inventory_levels"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("clinker_optimization_runs.id"), nullable=False, index=True)
    plant_id = db.Column(db.Integer, db.ForeignKey("clinker_plants.id"), nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    opening_inventory = db.Column(db.Float, nullable=False, default=0.0)
    closing_inventory = db.Column(db.Float, nullable=False, default=0.0)
    holding_cost = db.Column(db.Float, nullable=False, default=0.0)

    run = db.relationship(
        "ClinkerOptimizationRun",
        backref=db.backref("inventory_levels", cascade="all, delete-orphan", lazy=True),
    )
    plant = db.relationship("ClinkerPlant")

    __table_args__ = (
        UniqueConstraint("run_id", "plant_id", "period", name="uq_clinker_inventory"),
    )
