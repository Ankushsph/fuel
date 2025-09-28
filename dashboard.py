# dashboard.py
from flask import Blueprint, redirect, url_for, render_template, request, flash
from models import User, Vehicle, db
from flask_login import current_user, login_required

dashboard_bp = Blueprint("dashboard", __name__)

# Dashboard route
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    vehicles = Vehicle.query.filter_by(user_id=user.id).all()
    wallet_balance = user.wallet.balance if user.wallet else 0.0
    return render_template(
        "dashboard.html",
        user=user,
        vehicles=vehicles,
        has_password=bool(user.password_hash),
        wallet_balance=wallet_balance
    )

# Update profile route
@dashboard_bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    user = current_user
    full_name = request.form.get("full_name", "").strip()
    if full_name:
        user.full_name = full_name
        db.session.commit()
        flash("Profile updated successfully!", "success")
    else:
        flash("Name cannot be empty.", "error")
    return redirect(url_for("dashboard.dashboard"))

# Change password route
@dashboard_bp.route("/change_password", methods=["POST"])
@login_required
def change_password():
    user = current_user
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    confirm = request.form.get("confirm_password")

    if not user.check_password(old_password):
        flash("Current password is incorrect.", "error")
    elif new_password != confirm:
        flash("New passwords do not match.", "error")
    else:
        user.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully!", "success")

    return redirect(url_for("dashboard.dashboard"))
