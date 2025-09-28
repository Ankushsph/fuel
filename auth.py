# auth.py
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from models import User, Wallet
from extensions import db, oauth, mail, csrf 
from config import Config
from flask_login import login_user, logout_user
from flask_wtf.csrf import generate_csrf, validate_csrf
from flask_wtf.csrf import CSRFError

auth_bp = Blueprint("auth", __name__)

# Google OAuth registration
google = oauth.register(
    name="google",
    client_id=Config.GOOGLE_CLIENT_ID,
    client_secret=Config.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# Home route
@auth_bp.route('/')
def index():
    return render_template('index.html')

# Cab Owner Auth page
@auth_bp.route('/cab-owner-auth')
def cab_owner_auth():
    return render_template('cab-owner-auth.html')

# --- AJAX-enabled Register ---
@auth_bp.route('/register', methods=["POST"])
def register():
    # Determine if request is JSON (AJAX)
    if request.is_json:
        csrf_token = request.headers.get("X-CSRFToken")
        try:
            validate_csrf(csrf_token)
        except CSRFError:
            return jsonify({"success": False, "message": "CSRF token missing or invalid"}), 400

        data = request.get_json()
        full_name = data.get("full_name")
        email = data.get("email", "").strip().lower()
        password = data.get("password")
        confirm = data.get("confirm_password")
    else:
        full_name = request.form.get("full_name")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

    # Validation
    if not password:
        msg = "Password cannot be empty!"
        if request.is_json: return jsonify({"success": False, "message": msg}), 400
        flash(msg, "error")
        return redirect(url_for("auth.cab_owner_auth"))

    if password != confirm:
        msg = "Passwords do not match!"
        if request.is_json: return jsonify({"success": False, "message": msg}), 400
        flash(msg, "error")
        return redirect(url_for("auth.cab_owner_auth"))

    if User.query.filter_by(email=email).first():
        msg = "Email already registered!"
        if request.is_json: return jsonify({"success": False, "message": msg}), 400
        flash(msg, "error")
        return redirect(url_for("auth.cab_owner_auth"))

    # Create user and wallet
    user = User(full_name=full_name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # get user.id

    wallet = Wallet(user_id=user.id, balance=0.0)
    db.session.add(wallet)
    db.session.commit()

    login_user(user)

    msg = "Registration successful!"
    if request.is_json:
        return jsonify({"success": True, "message": msg, "redirect_url": url_for("dashboard.dashboard")})
    
    flash(msg, "success")
    return redirect(url_for("dashboard.dashboard"))

# --- AJAX-enabled Login ---
@auth_bp.route('/login', methods=["POST"])
def login():
    if request.is_json:
        csrf_token = request.headers.get("X-CSRFToken")
        try:
            validate_csrf(csrf_token)
        except CSRFError:
            return jsonify({"success": False, "message": "CSRF token missing or invalid"}), 400

        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password")
    else:
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")

    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        login_user(user)
        msg = "Login successful!"
        if request.is_json:
            return jsonify({"success": True, "message": msg, "redirect_url": url_for("dashboard.dashboard")})
        flash(msg, "success")
        return redirect(url_for("dashboard.dashboard"))

    msg = "Invalid email or password"
    if request.is_json:
        return jsonify({"success": False, "message": msg}), 400
    flash(msg, "error")
    return redirect(url_for("auth.cab_owner_auth"))

# Google OAuth login
@csrf.exempt
@auth_bp.route("/auth/google")
def auth_google():
    redirect_uri = url_for("auth.auth_google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)

# Google OAuth callback
@csrf.exempt
@auth_bp.route("/auth/google/callback")
def auth_google_callback():
    try:
        token = google.authorize_access_token()
        resp = google.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
        user_info = resp.json()
    except Exception as e:
        print("Google Auth Error:", e)
        flash("Google login failed. Try again.", "error")
        return redirect(url_for("auth.cab_owner_auth"))

    email = user_info.get("email", "").lower()
    name = user_info.get("name", "Google User")

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(full_name=name, email=email, password_hash=None)
        db.session.add(user)
        db.session.flush()
        wallet = Wallet(user_id=user.id, balance=0.0)
        db.session.add(wallet)
        db.session.commit()
        flash("Account created via Google.", "success")

    login_user(user)
    flash("Login successful with Google!", "success")
    return redirect(url_for("dashboard.dashboard"))

# Logout
@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.index"))
