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
