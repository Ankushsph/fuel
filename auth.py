# auth.py
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from models import User, Wallet, PumpOwner, PumpWallet
from extensions import db, oauth, csrf
from config import Config
from flask_login import login_user, logout_user
from flask_wtf.csrf import validate_csrf, CSRFError

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
    return render_template('/Cab-Owner/cab-owner-auth.html')

# Pump Owner Auth page
@auth_bp.route('/pump-owner-auth')
def pump_owner_auth():
    return render_template('/Pump-Owner/pump-owner-auth.html')


# -------------------------
# Unified Register
# -------------------------
@auth_bp.route('/register', methods=["POST"])
def register():
    # Determine if request is AJAX
    if request.is_json:
        csrf_token = request.headers.get("X-CSRFToken")
        try:
            validate_csrf(csrf_token)
        except CSRFError:
            return jsonify({"success": False, "message": "CSRF token missing or invalid"}), 400
        data = request.get_json()
        owner_type = data.get("owner_type", "cab")
        full_name = data.get("full_name")
        email = data.get("email", "").strip().lower()
        password = data.get("password")
        confirm = data.get("confirm_password")
    else:
        owner_type = request.form.get("owner_type", "cab")
        full_name = request.form.get("full_name")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

    # Determine model and wallet
    if owner_type == "pump":
        Model = PumpOwner
        WalletModel = PumpWallet
        auth_page = url_for("auth.pump_owner_auth")
    else:
        Model = User
        WalletModel = Wallet
        auth_page = url_for("auth.cab_owner_auth")

    # Validations
    if not password:
        msg = "Password cannot be empty!"
        if request.is_json:
            return jsonify({"success": False, "message": msg}), 400
        flash(msg, "error")
        return redirect(auth_page)

    if password != confirm:
        msg = "Passwords do not match!"
        if request.is_json:
            return jsonify({"success": False, "message": msg}), 400
        flash(msg, "error")
        return redirect(auth_page)

    if Model.query.filter_by(email=email).first():
        msg = "Email already registered!"
        if request.is_json:
            return jsonify({"success": False, "message": msg}), 400
        flash(msg, "error")
        return redirect(auth_page)

    # Create user
    user = Model(full_name=full_name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    # Create wallet
    wallet = WalletModel(user_id=user.id) if owner_type != "pump" else WalletModel(owner_id=user.id)
    wallet.balance = 0.0
    db.session.add(wallet)
    db.session.commit()

    login_user(user)
    msg = "Registration successful!"
    
    # Redirect based on user type
    if owner_type == "pump":
        redirect_url = url_for("pump.select_pump")
    else:
        redirect_url = url_for("dashboard.dashboard")
    
    if request.is_json:
        return jsonify({"success": True, "message": msg, "redirect_url": redirect_url})

    flash(msg, "success")
    return redirect(redirect_url)


# -------------------------
# Unified Login
# -------------------------
@auth_bp.route('/login', methods=["POST"])
def login():
    if request.is_json:
        csrf_token = request.headers.get("X-CSRFToken")
        try:
            validate_csrf(csrf_token)
        except CSRFError:
            return jsonify({"success": False, "message": "CSRF token missing or invalid"}), 400
        data = request.get_json()
        owner_type = data.get("owner_type", "cab")
        email = data.get("email", "").strip().lower()
        password = data.get("password")
    else:
        owner_type = request.form.get("owner_type", "cab")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")

    # Determine model
    if owner_type == "pump":
        Model = PumpOwner
        auth_page = url_for("auth.pump_owner_auth")
    else:
        Model = User
        auth_page = url_for("auth.cab_owner_auth")

    user = Model.query.filter_by(email=email).first()
    if user and user.check_password(password):
        login_user(user)
        msg = "Login successful!"
        
        # Redirect based on user type
        if owner_type == "pump":
            redirect_url = url_for("pump.select_pump")
        else:
            redirect_url = url_for("dashboard.dashboard")
        
        if request.is_json:
            return jsonify({"success": True, "message": msg, "redirect_url": redirect_url})
        flash(msg, "success")
        return redirect(redirect_url)

    msg = "Invalid email or password"
    if request.is_json:
        return jsonify({"success": False, "message": msg}), 400
    flash(msg, "error")
    return redirect(auth_page)


# -------------------------
# Unified Google OAuth
# -------------------------
@csrf.exempt
@auth_bp.route("/auth/google")
def auth_google():
    owner_type = request.args.get("owner_type", "cab")  # cab or pump
    redirect_uri = url_for("auth.auth_google_callback", _external=True)
    return google.authorize_redirect(redirect_uri, state=owner_type)


@csrf.exempt
@auth_bp.route("/auth/google/callback")
def auth_google_callback():
    owner_type = request.args.get("state", "cab")

    # Determine model and wallet
    if owner_type == "pump":
        Model = PumpOwner
        WalletModel = PumpWallet
        auth_page = url_for("auth.pump_owner_auth")
    else:
        Model = User
        WalletModel = Wallet
        auth_page = url_for("auth.cab_owner_auth")

    try:
        token = google.authorize_access_token()
        resp = google.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
        user_info = resp.json()
    except Exception as e:
        print("Google Auth Error:", e)
        flash("Google login failed. Try again.", "error")
        return redirect(auth_page)

    email = user_info.get("email", "").lower()
    name = user_info.get("name", "Google User")

    # Check if user exists
    user = Model.query.filter_by(email=email).first()
    if not user:
        user = Model(full_name=name, email=email, password_hash=None)
        db.session.add(user)
        db.session.flush()

        # Create wallet
        wallet = WalletModel(user_id=user.id) if owner_type != "pump" else WalletModel(owner_id=user.id)
        wallet.balance = 0.0
        db.session.add(wallet)
        db.session.commit()
        flash("Account created via Google.", "success")

    login_user(user)

    # Redirect based on user type
    if owner_type == "pump":
        flash("Login successful with Google as Pump Owner!", "success")
        return redirect(url_for("pump.select_pump"))  # change to your pump dashboard endpoint
    else:
        flash("Login successful with Google as Cab Owner!", "success")
        return redirect(url_for("dashboard.dashboard"))  # change to your cab dashboard endpoint




# Logout
@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.index"))
