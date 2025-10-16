#password_reset.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_mail import Message
from models import db, User
from extensions import mail  
import random

password_bp = Blueprint("password_bp", __name__)
otp_store = {}  # Temporary store, consider Redis for production

@password_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Email not registered! Please register first.", "error")
            return redirect(url_for("auth.cab_owner_auth") + "#register")

        otp = random.randint(100000, 999999)
        otp_store[email] = otp

        try:
            msg = Message(
                "Fuel Flux - OTP Verification",
                recipients=[email]
            )
            msg.body = f"Your OTP is: {otp}\n\nThis OTP will expire in 5 minutes."
            mail.send(msg)  # <-- use the imported mail instance
            flash("OTP sent to your email. Please enter it below.", "success")
        except Exception as e:
            print("Email sending failed:", e)
            flash("Error sending email. Please try again later.", "error")
            return redirect(url_for("password_bp.forgot_password"))

        return render_template("/Cab-Owner/forgot_password.html", step="otp", email=email)

    return render_template("/Cab-Owner/forgot_password.html", step="email")

@password_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    email = request.form.get("email")
    entered_otp = request.form.get("otp")

    if email not in otp_store or str(otp_store[email]) != entered_otp:
        flash("Invalid OTP! Try again.", "error")
        return render_template("/Cab-Owner/forgot_password.html", step="otp", email=email)

    flash("OTP verified! Please set your new password.", "success")
    return render_template("reset_password.html", email=email)

@password_bp.route("/reset-password", methods=["POST"])
def reset_password():
    email = request.form.get("email")
    password = request.form.get("password")
    confirm = request.form.get("confirm_password")

    if password != confirm:
        flash("Passwords do not match!", "error")
        return render_template("/Cab-Owner/reset_password.html", email=email)

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("password_bp.forgot_password"))

    user.set_password(password)
    db.session.commit()
    otp_store.pop(email, None)

    flash("Password reset successful. Please login.", "success")
    return redirect(url_for("auth.cab_owner_auth"))

@password_bp.route("/change_password", methods=["POST"])
def change_password():
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    # Validate input
    if not old_password or not new_password or not confirm_password:
        flash("All fields are required.", "error")
        return redirect(url_for("dashboard.index"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("dashboard.index"))

    if not check_password_hash(current_user.password_hash, old_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("dashboard.index"))

    # Update password
    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    flash("Password updated successfully.", "success")
    return redirect(url_for("dashboard.index"))