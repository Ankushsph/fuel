import os
from flask import Flask, redirect, url_for, request, jsonify, render_template
from config import Config
from extensions import db, mail, oauth, csrf, migrate
from flask_login import LoginManager
from models import User, PumpOwner, Admin
from flask_cors import CORS
from pump import pump_bp

app = Flask(__name__)
app.config.from_object(Config)

# --- Session cookie settings ---
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'  # auto-detect production

# --- Allow CORS for frontend ---
CORS(app, supports_credentials=True, origins=["http://127.0.0.1:5001"])

# --- Initialize extensions ---
db.init_app(app)
mail.init_app(app)
oauth.init_app(app)
csrf.init_app(app)
migrate.init_app(app, db)

# --- Create upload directories ---
UPLOAD_FOLDERS = [
    'uploads/receipts',
    'uploads/payment_proofs',
    'uploads/pump_documents',
    'uploads/employee_photos',
    'uploads/hydrotest_documents'
]
for folder in UPLOAD_FOLDERS:
    os.makedirs(folder, exist_ok=True)

# --- Flask-Login setup ---
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')


# --- User loader ---
@login_manager.user_loader
def load_user(user_id):
    if "_" not in str(user_id):
        return User.query.get(int(user_id))
    user_type, real_id = user_id.split("_", 1)
    if user_type == "user":
        return User.query.get(int(real_id))
    elif user_type == "pump":
        return PumpOwner.query.get(int(real_id))
    elif user_type == "admin":
        return Admin.query.get(int(real_id))
    return None



@login_manager.unauthorized_handler
def unauthorized_callback():
    return jsonify({"success": False, "message": "Login required."}), 401


# --- Import and register blueprints ---
from auth import auth_bp
from dashboard import dashboard_bp
from pump_dashboard import pump_dashboard_bp
from vehicle import vehicle_bp
from wallet import wallet_bp
from password_reset import password_bp
from subscription import subscription_bp
from vehicle_count import vehicle_count_bp
from admin import admin_bp
from employee import employee_bp
from attendance_monitor import attendance_monitor_bp
from vehicle_verification import vehicle_verification_bp
from hydrotesting import hydrotesting_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(pump_dashboard_bp, url_prefix="/pump")
app.register_blueprint(vehicle_bp)
app.register_blueprint(wallet_bp)
app.register_blueprint(password_bp)
app.register_blueprint(pump_bp)
app.register_blueprint(subscription_bp, url_prefix="/subscription")
app.register_blueprint(vehicle_count_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(attendance_monitor_bp, url_prefix="/attendance_monitor")
app.register_blueprint(vehicle_verification_bp, url_prefix="/vehicle_verification")
app.register_blueprint(hydrotesting_bp, url_prefix="/hydrotesting")

# --- Initialize database tables and run migrations (runs even with Gunicorn) ---
with app.app_context():
    # Try to run migrations first
    try:
        from flask_migrate import upgrade as migrate_upgrade
        migrate_upgrade()
        print("✅ Database migrations completed successfully!")
    except Exception as e:
        print(f"⚠️  Migration warning (may be normal): {e}")
    
    # Ensure all tables exist
    db.create_all()
    print("✅ Database tables created successfully!")
    
    # Create admin user if not exists
    try:
        from models import Admin
        # Check if new admin exists
        new_admin = Admin.query.filter_by(email="web3.ankitrai@gmail.com").first()
        if not new_admin:
            admin = Admin(email="web3.ankitrai@gmail.com")
            admin.set_password("123466")
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created: web3.ankitrai@gmail.com")
        else:
            print("✅ Admin user already exists")
        
        # Remove old admin if exists
        old_admin = Admin.query.filter_by(email="ankushn2005@gmail.com").first()
        if old_admin:
            db.session.delete(old_admin)
            db.session.commit()
            print("✅ Old admin user removed")
    except Exception as e:
        print(f"⚠️  Admin creation warning: {e}")
    
    # Auto-start all saved RTSP monitoring streams
    try:
        from models import StationVehicle, VehicleVerification
        from vehicle_count import start_rtsp_thread as start_vehicle_count
        from vehicle_verification import start_rtsp_thread as start_plate_detection
        
        # Start vehicle counting for all saved streams
        vehicle_streams = StationVehicle.query.all()
        for stream in vehicle_streams:
            try:
                start_vehicle_count(stream.owner_id, stream.rtsp_url)
                print(f"🚗 Auto-started vehicle counting for: {stream.station_name}")
            except Exception as e:
                print(f"⚠️  Could not auto-start vehicle counting for {stream.station_name}: {e}")
        
        # Start plate detection for all saved streams
        plate_streams = VehicleVerification.query.all()
        for stream in plate_streams:
            try:
                start_plate_detection(stream)
                print(f"🛑 Auto-started plate detection for: {stream.station_name}")
            except Exception as e:
                print(f"⚠️  Could not auto-start plate detection for {stream.station_name}: {e}")
        
        if vehicle_streams or plate_streams:
            print(f"\n✅ Auto-started monitoring for {len(vehicle_streams)} vehicle counting + {len(plate_streams)} plate detection streams")
        else:
            print("ℹ️  No saved streams found. Add streams to start monitoring.")
    except Exception as e:
        print(f"⚠️  Auto-start warning: {e}")
    
    # Start hydrotest notification service
    try:
        from hydrotest_notification_service import start_notification_service
        start_notification_service(app)
    except Exception as e:
        print(f"⚠️  Hydrotest notification service warning: {e}")

# --- Create all tables and run app ---
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)