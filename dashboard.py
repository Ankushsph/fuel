# dashboard.py
from flask import Blueprint, redirect, url_for, render_template, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import datetime, timedelta

from config import Config
from models import User, Vehicle, db, FuelTransaction, Pump

dashboard_bp = Blueprint("dashboard", __name__)

# Dashboard route
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    vehicles = Vehicle.query.filter_by(user_id=user.id).all()
    wallet_balance = user.wallet.balance if user.wallet else 0.0
    return render_template(
        "/Cab-Owner/dashboard.html",
        user=user,
        vehicles=vehicles,
        has_password=bool(user.password_hash),
        wallet_balance=wallet_balance,
        upi_id=Config.UPI_ID,
        business_name=Config.BUSINESS_NAME,
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


# Transaction details route
@dashboard_bp.route("/transactions")
@login_required
def transactions():
    """Show detailed transaction history for cab owner"""
    user = current_user
    
    # Get all fuel transactions for this user's vehicles
    transactions = db.session.query(FuelTransaction, Pump, Vehicle)\
        .join(Pump, FuelTransaction.pump_id == Pump.id)\
        .join(Vehicle, FuelTransaction.vehicle_number == Vehicle.name)\
        .filter(Vehicle.user_id == user.id)\
        .order_by(FuelTransaction.created_at.desc())\
        .limit(50)\
        .all()
    
    # Format transaction data
    transaction_list = []
    for transaction, pump, vehicle in transactions:
        transaction_list.append({
            'id': transaction.id,
            'vehicle_number': vehicle.name,
            'vehicle_type': vehicle.vehicle_type,
            'pump_name': pump.name if pump else 'Unknown',
            'pump_location': pump.location if pump else 'Unknown',
            'fuel_type': transaction.fuel_type,
            'quantity_litres': transaction.quantity_litres,
            'unit_price': transaction.unit_price,
            'amount': transaction.amount,
            'status': transaction.status,
            'verification_level': transaction.verification_level,
            'attendant': transaction.attendant.full_name if transaction.attendant else 'System',
            'verifier': transaction.verifier.full_name if transaction.verifier else 'Not verified',
            'created_at': transaction.created_at,
            'verified_at': transaction.verified_at,
            'settled_at': transaction.settled_at,
            'extra_data': transaction.extra_data
        })
    
    return render_template(
        "/Cab-Owner/transactions.html",
        user=user,
        transactions=transaction_list,
        wallet_balance=user.wallet.balance if user.wallet else 0.0,
        upi_id=Config.UPI_ID,
        business_name=Config.BUSINESS_NAME,
    )


# Transaction details API route
@dashboard_bp.route("/transaction/<int:transaction_id>")
@login_required
def transaction_details(transaction_id):
    """Get detailed information about a specific transaction"""
    user = current_user
    
    # Get transaction with pump and vehicle details
    transaction = db.session.query(FuelTransaction, Pump, Vehicle)\
        .join(Pump, FuelTransaction.pump_id == Pump.id)\
        .join(Vehicle, FuelTransaction.vehicle_number == Vehicle.name)\
        .filter(FuelTransaction.id == transaction_id)\
        .filter(Vehicle.user_id == user.id)\
        .first()
    
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    trans, pump, vehicle = transaction
    
    return jsonify({
        'id': trans.id,
        'vehicle_number': vehicle.name,
        'vehicle_type': vehicle.vehicle_type,
        'pump_name': pump.name if pump else 'Unknown',
        'pump_location': pump.location if pump else 'Unknown',
        'pump_address': pump.address if pump else 'Unknown',
        'pump_phone': pump.phone if pump else 'Unknown',
        'fuel_type': trans.fuel_type,
        'quantity_litres': trans.quantity_litres,
        'unit_price': trans.unit_price,
        'amount': trans.amount,
        'status': trans.status,
        'verification_level': trans.verification_level,
        'attendant': trans.attendant.full_name if trans.attendant else 'System',
        'verifier': trans.verifier.full_name if trans.verifier else 'Not verified',
        'created_at': trans.created_at.isoformat() if trans.created_at else None,
        'verified_at': trans.verified_at.isoformat() if trans.verified_at else None,
        'settled_at': trans.settled_at.isoformat() if trans.settled_at else None,
        'extra_data': trans.extra_data
    })
