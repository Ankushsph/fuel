#password_reset.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_mail import Message
from models import db, User, PumpOwner
from extensions import mail
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import current_user, login_required
import random

password_bp = Blueprint("password_bp", __name__)
otp_store = {}  # Temporary store, consider Redis for production

@password_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    # Get user type from query parameter (default to 'cab')
    user_type = request.args.get('type', 'cab')
    
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        user_type = request.form.get("user_type", "cab")
        
        # Check based on user type
        if user_type == "pump":
            user = PumpOwner.query.filter_by(email=email).first()
            redirect_url = "auth.pump_owner_auth"
            template_dir = "Pump-Owner"
        else:
            user = User.query.filter_by(email=email).first()
            redirect_url = "auth.cab_owner_auth"
            template_dir = "Cab-Owner"
        
        if not user:
            flash("Email not registered! Please register first.", "error")
            return redirect(url_for(redirect_url) + "#register")

        otp = random.randint(100000, 999999)
        otp_store[email] = {"otp": otp, "user_type": user_type}

        try:
            msg = Message(
                "Fuel Flux - Password Reset OTP",
                recipients=[email]
            )
            msg.body = f"""Dear User,

Your OTP for password reset is: {otp}

This OTP will expire in 5 minutes.

If you didn't request this, please ignore this email.

Best regards,
Fuel Flux Team"""
            mail.send(msg)
            flash("✅ OTP sent to your email. Please check your inbox.", "success")
        except Exception as e:
            print("Email sending failed:", e)
            flash("❌ Error sending email. Please try again later.", "error")
            return redirect(url_for("password_bp.forgot_password", type=user_type))

        return render_template(f"/{template_dir}/forgot_password.html", step="otp", email=email, user_type=user_type)

    # Determine template based on user type
    template_dir = "Pump-Owner" if user_type == "pump" else "Cab-Owner"
    return render_template(f"/{template_dir}/forgot_password.html", step="email", user_type=user_type)

@password_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    email = request.form.get("email")
    entered_otp = request.form.get("otp")
    user_type = request.form.get("user_type", "cab")
    
    # Validate OTP
    if email not in otp_store or str(otp_store[email]["otp"]) != entered_otp:
        flash("❌ Invalid OTP! Please try again.", "error")
        template_dir = "Pump-Owner" if user_type == "pump" else "Cab-Owner"
        return render_template(f"/{template_dir}/forgot_password.html", step="otp", email=email, user_type=user_type)

    flash("✅ OTP verified! Please set your new password.", "success")
    template_dir = "Pump-Owner" if user_type == "pump" else "Cab-Owner"
    return render_template(f"/{template_dir}/reset_password.html", email=email, user_type=user_type)

@password_bp.route("/reset-password", methods=["POST"])
def reset_password():
    email = request.form.get("email")
    password = request.form.get("password")
    confirm = request.form.get("confirm_password")
    user_type = request.form.get("user_type", "cab")

    if password != confirm:
        flash("❌ Passwords do not match!", "error")
        template_dir = "Pump-Owner" if user_type == "pump" else "Cab-Owner"
        return render_template(f"/{template_dir}/reset_password.html", email=email, user_type=user_type)

    # Get user based on type
    if user_type == "pump":
        user = PumpOwner.query.filter_by(email=email).first()
        redirect_url = "auth.pump_owner_auth"
    else:
        user = User.query.filter_by(email=email).first()
        redirect_url = "auth.cab_owner_auth"
    
    if not user:
        flash("❌ User not found!", "error")
        return redirect(url_for("password_bp.forgot_password", type=user_type))

    user.set_password(password)
    db.session.commit()
    otp_store.pop(email, None)

    flash("✅ Password reset successful! Please login with your new password.", "success")
    return redirect(url_for(redirect_url))

@password_bp.route("/change_password", methods=["POST"])
@login_required
def change_password():
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    # Validate input
    if not old_password or not new_password or not confirm_password:
        flash("All fields are required.", "error")
        return redirect(url_for("dashboard.dashboard"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("dashboard.dashboard"))

    if not current_user.check_password(old_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("dashboard.dashboard"))

    # Update password
    current_user.set_password(new_password)
    db.session.commit()

    flash("Password updated successfully.", "success")
    return redirect(url_for("dashboard.dashboard"))