# admin.py - Admin Panel for Fuel Flux
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from functools import wraps
from models import (
    db,
    PumpOwner,
    Pump,
    PumpSubscription,
    PaymentVerification,
    PumpRegistrationRequest,
    WalletTopupVerification,
    User,
    Wallet,
)
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash
import os

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

def admin_required(f):
    """Decorator to ensure only admin can access certain routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Access denied. Admin only.", "error")
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# ========================
# Admin Login
# ========================
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "")

        if not admin_email or not admin_password:
            flash("Admin login is not configured.", "error")
            return redirect(url_for('admin.admin_login'))
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if email == admin_email and password == admin_password:
            session['is_admin'] = True
            session['admin_email'] = email
            flash("✅ Admin login successful!", "success")
            return redirect(url_for('admin.dashboard'))
        else:
            flash("❌ Invalid admin credentials", "error")
    
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def admin_logout():
    """Admin logout"""
    session.pop('is_admin', None)
    session.pop('admin_email', None)
    flash("Logged out successfully", "success")
    return redirect(url_for('admin.admin_login'))


# ========================
# Admin Dashboard
# ========================
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Main admin dashboard"""
    pending_payments = PaymentVerification.query.filter_by(status='pending').all()
    pending_wallet_topups = WalletTopupVerification.query.filter_by(status='pending').all()
    pending_registrations = PumpRegistrationRequest.query.filter_by(status='pending').all()
    
    # Get statistics
    total_pumps = Pump.query.count()
    total_owners = PumpOwner.query.count()
    active_subs = PumpSubscription.query.filter_by(subscription_status='active').count()
    
    return render_template(
        'admin/dashboard.html',
        pending_payments=pending_payments,
        pending_wallet_topups=pending_wallet_topups,
        pending_registrations=pending_registrations,
        total_pumps=total_pumps,
        total_owners=total_owners,
        active_subs=active_subs,
    )


@admin_bp.route('/wallet-topups/pending')
@admin_required
def pending_wallet_topups():
    topups = (
        WalletTopupVerification.query
        .filter_by(status='pending')
        .order_by(WalletTopupVerification.created_at.desc())
        .all()
    )
    return render_template('admin/pending_wallet_topups.html', topups=topups)


@admin_bp.route('/wallet-topups/verify/<int:topup_id>', methods=['POST'])
@admin_required
def verify_wallet_topup(topup_id):
    topup = WalletTopupVerification.query.get_or_404(topup_id)

    if topup.status != 'pending':
        return jsonify({"error": "Top-up already processed"}), 400

    data = request.get_json() or {}
    action = data.get('action')

    if action == 'approve':
        user = topup.user
        if not user:
            return jsonify({"error": "User not found for this top-up"}), 404

        wallet = user.wallet
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=0.0)
            db.session.add(wallet)
            db.session.flush()
            user.wallet = wallet

        wallet.balance += topup.amount

        topup.status = 'approved'
        topup.verified_at = datetime.utcnow()
        topup.verified_by = session.get('admin_email')

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": f"Wallet top-up of ₹{topup.amount:.2f} approved and credited.",
            }
        )

    if action == 'reject':
        topup.status = 'rejected'
        topup.verified_at = datetime.utcnow()
        topup.verified_by = session.get('admin_email')
        topup.rejection_reason = data.get('reason', 'Invalid payment proof')

        db.session.commit()

        return jsonify({"success": True, "message": "Wallet top-up rejected"})

    return jsonify({"error": "Invalid action"}), 400


# ========================
# Payment Verification
# ========================
@admin_bp.route('/payments/pending')
@admin_required
def pending_payments():
    """View all pending payment verifications"""
    payments = PaymentVerification.query.filter_by(status='pending').order_by(PaymentVerification.created_at.desc()).all()
    return render_template('admin/pending_payments.html', payments=payments)


@admin_bp.route('/payments/verify/<int:payment_id>', methods=['POST'])
@admin_required
def verify_payment(payment_id):
    """Verify a payment and activate subscription"""
    payment = PaymentVerification.query.get_or_404(payment_id)
    
    if payment.status != 'pending':
        return jsonify({"error": "Payment already processed"}), 400
    
    action = request.json.get('action')  # 'approve' or 'reject'
    
    if action == 'approve':
        # Activate subscription
        pump = Pump.query.get(payment.pump_id)
        if not pump:
            return jsonify({"error": "Pump not found"}), 404
        
        # Calculate duration
        duration_map = {
            "1 Month": 1,
            "6 Months": 6,
            "Annual": 12
        }
        months = duration_map.get(payment.duration, 1)
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30 * months)
        
        # Update or create subscription
        existing = PumpSubscription.query.filter_by(
            user_id=payment.user_id, 
            pump_id=payment.pump_id
        ).first()
        
        if existing:
            existing.subscription_type = payment.plan_type
            existing.subscription_status = "active"
            existing.start_date = start_date
            existing.end_date = end_date
        else:
            new_sub = PumpSubscription(
                user_id=payment.user_id,
                email=payment.user_email,
                pump_id=payment.pump_id,
                pump_name=pump.name,
                pump_location=pump.location,
                subscription_type=payment.plan_type,
                subscription_status="active",
                start_date=start_date,
                end_date=end_date
            )
            db.session.add(new_sub)
        
        payment.status = 'approved'
        payment.verified_at = datetime.utcnow()
        payment.verified_by = session.get('admin_email')
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"✅ Payment approved! {payment.plan_type} subscription activated."
        })
    
    elif action == 'reject':
        payment.status = 'rejected'
        payment.verified_at = datetime.utcnow()
        payment.verified_by = session.get('admin_email')
        payment.rejection_reason = request.json.get('reason', 'Invalid payment proof')
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "❌ Payment rejected"
        })
    
    return jsonify({"error": "Invalid action"}), 400


# ========================
# Pump Registration Verification
# ========================
@admin_bp.route('/registrations/pending')
@admin_required
def pending_registrations():
    """View all pending pump registrations"""
    registrations = PumpRegistrationRequest.query.filter_by(status='pending').order_by(PumpRegistrationRequest.created_at.desc()).all()
    return render_template('admin/pending_registrations.html', registrations=registrations)


@admin_bp.route('/registrations/verify/<int:registration_id>', methods=['POST'])
@admin_required
def verify_registration(registration_id):
    """Verify or reject a pump registration"""
    print(f"DEBUG: verify_registration called for ID: {registration_id}")
    print(f"DEBUG: Admin session: {session.get('is_admin')}")
    print(f"DEBUG: Admin email: {session.get('admin_email')}")
    
    registration = PumpRegistrationRequest.query.get_or_404(registration_id)
    print(f"DEBUG: Registration found: {registration.id}, status: {registration.status}")
    
    if registration.status != 'pending':
        return jsonify({"error": "Registration already processed"}), 400
    
    try:
        # Get JSON data
        if not request.is_json:
            print("DEBUG: Request is not JSON")
            return jsonify({"error": "Content-Type must be application/json"}), 400
            
        data = request.get_json()
        print(f"DEBUG: Request data: {data}")
        
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
            
        action = data.get('action')
        print(f"DEBUG: Action: {action}")
        
    except Exception as e:
        print(f"DEBUG: Error parsing JSON: {e}")
        return jsonify({"error": f"Invalid JSON data: {str(e)}"}), 400
    
    if action == 'approve':
        # Activate the pump (mark as verified)
        pump = Pump.query.get(registration.pump_id)
        if pump:
            pump.is_verified = True
            pump.verified_at = datetime.utcnow()
        
        registration.status = 'approved'
        registration.verified_at = datetime.utcnow()
        registration.verified_by = session.get('admin_email')
        
        db.session.commit()
        print("DEBUG: Registration approved successfully")
        
        return jsonify({
            "success": True,
            "message": "✅ Pump registration approved!"
        })
    
    elif action == 'reject':
        registration.status = 'rejected'
        registration.verified_at = datetime.utcnow()
        registration.verified_by = session.get('admin_email')
        registration.rejection_reason = data.get('reason', 'Invalid documents or information')
        
        # Optionally block the pump
        pump = Pump.query.get(registration.pump_id)
        if pump:
            pump.is_blocked = True
        
        db.session.commit()
        print("DEBUG: Registration rejected successfully")
        
        return jsonify({
            "success": True,
            "message": "❌ Pump registration rejected"
        })
    
    print(f"DEBUG: Invalid action: {action}")
    return jsonify({"error": "Invalid action"}), 400


# ========================
# View Screenshot
# ========================
@admin_bp.route('/screenshot/<filename>')
@admin_required
def view_screenshot(filename):
    """Serve payment screenshot"""
    from flask import send_from_directory
    return send_from_directory(os.path.join('uploads', 'payment_proofs'), filename)


@admin_bp.route('/documents/<filename>')
@admin_required
def view_document(filename):
    """Serve pump registration documents"""
    from flask import send_from_directory
    return send_from_directory(os.path.join('uploads', 'pump_documents'), filename)




