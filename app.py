import os
import sys
from flask import Flask, redirect, url_for, request, jsonify, render_template
from config import Config
from extensions import db, mail, oauth, csrf, migrate
from flask_login import LoginManager
from models import User, PumpOwner, Admin
from flask_cors import CORS
from sqlalchemy import text
from pump import pump_bp
from escrow import escrow_bp
from settlement import settlement_bp

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.instance_path, exist_ok=True)

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
    'uploads/hydrotest_documents',
    'uploads/videos'
]
for folder in UPLOAD_FOLDERS:
    os.makedirs(folder, exist_ok=True)

# --- Flask-Login setup ---
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@app.teardown_appcontext
def _shutdown_session(exception=None):
    try:
        db.session.remove()
    except Exception:
        pass


@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')


# --- User loader ---
@login_manager.user_loader
def load_user(user_id):
    try:
        if "_" not in str(user_id):
            return db.session.get(User, int(user_id))

        user_type, real_id = str(user_id).split("_", 1)
        real_id_i = int(real_id)
        if user_type == "user":
            return db.session.get(User, real_id_i)
        elif user_type == "pump":
            return db.session.get(PumpOwner, real_id_i)
        elif user_type == "admin":
            return db.session.get(Admin, real_id_i)
        elif user_type == "investor":
            from models import Investor
            return db.session.get(Investor, real_id_i)
        return None
    except Exception:
        return None



@login_manager.unauthorized_handler
def unauthorized_callback():
    return jsonify({"success": False, "message": "Login required."}), 401


# --- Import and register blueprints ---
from auth import auth_bp
from dashboard import dashboard_bp
from pump_dashboard import pump_dashboard_bp
from logistics import logistics_bp
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
from escrow import escrow_bp
from settlement import settlement_bp
from investor import investor_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(pump_dashboard_bp, url_prefix="/pump")
app.register_blueprint(logistics_bp)
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
app.register_blueprint(escrow_bp, url_prefix="/escrow")
app.register_blueprint(settlement_bp, url_prefix="/settlement")
app.register_blueprint(investor_bp, url_prefix="/investor")


def _is_flask_cli() -> bool:
    return os.environ.get("FLASK_RUN_FROM_CLI") in {"true", "1", "True"}


def _is_server_process() -> bool:
    if not _is_flask_cli():
        return True
    return "run" in sys.argv


def _sqlite_has_column(conn, table_name: str, column_name: str) -> bool:
    try:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    except Exception:
        return False
    for r in rows:
        if len(r) >= 2 and str(r[1]).lower() == str(column_name).lower():
            return True
    return False


def _sqlite_add_column(conn, table_name: str, ddl_fragment: str):
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl_fragment}"))

# --- Initialize database tables and run migrations (runs even with Gunicorn) ---
if _is_server_process():
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
            admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
            admin_password = os.getenv("ADMIN_PASSWORD", "")

            if admin_email and admin_password:
                new_admin = Admin.query.filter_by(email=admin_email).first()
                if not new_admin:
                    admin = Admin(email=admin_email)
                    admin.set_password(admin_password)
                    db.session.add(admin)
                    db.session.commit()
                    print(f"✅ Admin user created: {admin_email}")
                else:
                    print("✅ Admin user already exists")

            old_admin_email = os.getenv("ADMIN_REMOVE_EMAIL", "").strip().lower()
            if old_admin_email:
                old_admin = Admin.query.filter_by(email=old_admin_email).first()
                if old_admin:
                    db.session.delete(old_admin)
                    db.session.commit()
                    print(f"✅ Old admin user removed: {old_admin_email}")
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