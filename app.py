from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
import random
from dotenv import load_dotenv
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")
load_dotenv()

# ---------------- DATABASE CONFIG ----------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://fueluser:fuelpass123@localhost:3306/fuelflux'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------- MAIL CONFIG ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = (os.getenv("MAIL_DEFAULT_SENDER_NAME", "Fuel Flux"), os.getenv("MAIL_USERNAME"))
mail = Mail(app)

# ---------------- GOOGLE OAUTH CONFIG ----------------
app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ---------------- USER MODEL ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)  # ✅ NULL for Google users

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password) if self.password_hash else False

# ---------------- VEHICLE MODEL ----------------
class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User", backref=db.backref("vehicles", lazy=True))

# ---------------- OTP STORE ----------------
otp_store = {}

# ---------------- ROUTES ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cab-owner-auth')
def cab_owner_auth():
    return render_template('cab-owner-auth.html')

# ---------------- REGISTER ----------------
@app.route('/register', methods=["POST"])
def register():
    full_name = request.form.get("full_name")
    email = request.form.get("email").strip().lower()
    password = request.form.get("password")
    confirm = request.form.get("confirm_password")

    if not password:
        flash("Password cannot be empty!", "error")
        return redirect(url_for("cab_owner_auth"))

    if password != confirm:
        flash("Passwords do not match!", "error")
        return redirect(url_for("cab_owner_auth"))

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash("Email already registered!", "error")
        return redirect(url_for("cab_owner_auth"))

    user = User(full_name=full_name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    session["user_id"] = user.id
    flash("Registration successful!", "success")
    return redirect(url_for("dashboard"))

# ---------------- LOGIN ----------------
@app.route('/login', methods=["POST"])
def login():
    email = request.form.get("email").strip().lower()
    password = request.form.get("password")

    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        session["user_id"] = user.id
        flash("Login successful!", "success")
        return redirect(url_for("dashboard"))
    else:
        flash("Invalid email or password", "error")
        return redirect(url_for("cab_owner_auth"))

# ---------------- GOOGLE LOGIN ----------------
@app.route("/auth/google")
def auth_google():
    redirect_uri = url_for("auth_google_callback", _external=True, _scheme="http")
    print("Redirect URI:", redirect_uri)
    return google.authorize_redirect(redirect_uri)

@app.route("/auth/google/callback")
def auth_google_callback():
    try:
        token = google.authorize_access_token()
        user_info = google.userinfo()
    except Exception as e:
        print("Google Auth Error:", e)
        flash("Google login failed. Try again.", "error")
        return redirect(url_for("cab_owner_auth"))

    email = user_info["email"].lower()
    name = user_info.get("name", "Google User")

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(full_name=name, email=email, password_hash=None)
        db.session.add(user)
        db.session.commit()
        flash("Account created via Google.", "success")

    session["user_id"] = user.id
    flash("Login successful with Google!", "success")
    return redirect(url_for("dashboard"))

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("cab_owner_auth"))
    
    user = User.query.get(session["user_id"])
    vehicles = Vehicle.query.filter_by(user_id=user.id).all()
    # Removed "Book Slot" references from dashboard template
    return render_template("dashboard.html", user=user, vehicles=vehicles)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("cab_owner_auth"))

# ---------------- VEHICLE CRUD ----------------
@app.route("/add_vehicle", methods=["POST"])
def add_vehicle():
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("cab_owner_auth"))

    name = request.form.get("name").strip()
    type_ = request.form.get("type").strip()
    if not name or not type_:
        flash("All fields are required.", "error")
        return redirect(url_for("dashboard"))

    vehicle = Vehicle(name=name, type=type_, user_id=session["user_id"])
    db.session.add(vehicle)
    db.session.commit()
    flash("Vehicle added successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/remove_vehicle/<int:vehicle_id>", methods=["POST"])
def remove_vehicle(vehicle_id):
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("cab_owner_auth"))

    vehicle = Vehicle.query.get(vehicle_id)
    if vehicle and vehicle.user_id == session["user_id"]:
        db.session.delete(vehicle)
        db.session.commit()
        flash("Vehicle removed successfully!", "success")
    else:
        flash("Vehicle not found or unauthorized.", "error")
    return redirect(url_for("dashboard"))

# ---------------- PASSWORD RESET ----------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Email not registered! Please register first.", "error")
            return redirect(url_for("cab_owner_auth") + "#register")

        otp = random.randint(100000, 999999)
        otp_store[email] = otp

        try:
            msg = Message("Fuel Flux - OTP Verification", recipients=[email])
            msg.body = f"Your OTP is: {otp}\n\nThis OTP will expire in 5 minutes."
            mail.send(msg)
            flash("OTP sent to your email. Please enter it below.", "success")
        except Exception as e:
            print("Email sending failed:", e)
            flash("Error sending email. Please try again later.", "error")
            return redirect(url_for("forgot_password"))

        return render_template("forgot_password.html", step="otp", email=email)

    return render_template("forgot_password.html", step="email")

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    email = request.form.get("email")
    entered_otp = request.form.get("otp")

    if email not in otp_store or str(otp_store[email]) != entered_otp:
        flash("Invalid OTP! Try again.", "error")
        return render_template("forgot_password.html", step="otp", email=email)

    flash("OTP verified! Please set your new password.", "success")
    return render_template("reset_password.html", email=email)

@app.route("/reset-password", methods=["POST"])
def reset_password():
    email = request.form.get("email")
    password = request.form.get("password")
    confirm = request.form.get("confirm_password")

    if password != confirm:
        flash("Passwords do not match!", "error")
        return render_template("reset_password.html", email=email)

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("forgot_password"))

    user.set_password(password)
    db.session.commit()
    otp_store.pop(email, None)

    flash("Password reset successful. Please login.", "success")
    return redirect(url_for("cab_owner_auth"))

# ---------------- MAIN ----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5001)
