# subscription.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from models import db, PumpSubscription, Pump, PumpOwner, PaymentVerification
from config import Config
from werkzeug.utils import secure_filename
import os
import uuid
try:
    import razorpay
except ImportError:
    razorpay = None

subscription_bp = Blueprint("subscription", __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

PLAN_PRICES_INR = {
    "silver": 5000,
    "gold": 5000,
    "diamond": 15000,
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------------
# 🔹 View Subscription Plans Page
# ------------------------
@subscription_bp.route("/plans")
@login_required
def plans():
    """Show subscription plans for a specific pump"""
    pump_id = request.args.get('pump_id', type=int)
    if not pump_id:
        flash("Pump ID is required", "error")
        return redirect(url_for('pump.select_pump'))
    
    # Check if pump exists and belongs to user
    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        flash("Pump not found", "error")
        return redirect(url_for('pump.select_pump'))
    
    return render_template("subscription-plans.html", pump=pump, pump_id=pump_id)


# ------------------------
# 🔹 View Subscription Page (optional)
# ------------------------
@subscription_bp.route("/subscriptions")
@login_required
def subscriptions():
    # Get the user's pump and subscription
    subs = PumpSubscription.query.filter_by(user_id=current_user.id).all()
    return render_template("subscriptions.html", subscriptions=subs)


# ------------------------
# 🔹 Handle New Subscription
# ------------------------
@subscription_bp.route("/subscribe", methods=["POST"])
@login_required
def subscribe():
    """
    Handles subscription purchase for pump owners.
    Expects JSON or form data with:
        - plan_type (Silver/Gold/Diamond)
        - duration (1 Month / 6 Months / Annual)
        - pump_id
    """

    data = request.get_json() or request.form
    plan_type = data.get("plan_type")
    duration = data.get("duration")
    pump_id = data.get("pump_id")

    if not all([plan_type, duration, pump_id]):
        return jsonify({"error": "Missing required fields"}), 400

    # Fetch pump and wallet
    pump = Pump.query.get(pump_id)
    wallet = current_user.wallet

    if not pump or not wallet:
        return jsonify({"error": "Pump or wallet not found"}), 404

    # Base prices (in ₹)
    plan_prices = {
        "Silver": PLAN_PRICES_INR["silver"],
        "Gold": PLAN_PRICES_INR["gold"],
        "Diamond": PLAN_PRICES_INR["diamond"],
    }

    # Duration multipliers
    duration_map = {
        "1 Month": 1,
        "6 Months": 6,
        "Annual": 12
    }

    # Calculate total
    base_price = plan_prices.get(plan_type.capitalize())
    months = duration_map.get(duration)
    total_price = base_price * months

    # Check balance
    if wallet.balance < total_price:
        flash("Insufficient wallet balance. Please add funds.", "error")
        return jsonify({"error": "Insufficient funds"}), 402

    # Deduct balance
    wallet.balance -= total_price

    # Calculate subscription duration
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=30 * months)

    # Check existing subscription
    existing = PumpSubscription.query.filter_by(user_id=current_user.id, pump_id=pump.id).first()

    if existing:
        existing.subscription_type = plan_type
        existing.subscription_status = "active"
        existing.start_date = start_date
        existing.end_date = end_date
    else:
        new_sub = PumpSubscription(
            user_id=current_user.id,
            email=current_user.email,
            pump_id=pump.id,
            pump_name=pump.name,
            pump_location=pump.location,
            subscription_type=plan_type,
            subscription_status="active",
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(new_sub)

    db.session.commit()

    flash(f"✅ {plan_type} plan activated for {duration}!", "success")
    return jsonify({"success": True, "message": f"{plan_type} plan activated for {duration}."})


# ------------------------
# 🔹 Check Subscription Status
# ------------------------
@subscription_bp.route("/subscription-status/<int:pump_id>")
@login_required
def subscription_status(pump_id):
    sub = PumpSubscription.query.filter_by(user_id=current_user.id, pump_id=pump_id).first()
    if not sub:
        return jsonify({"status": "not taken"})

    status = {
        "status": sub.subscription_status,
        "type": sub.subscription_type,
        "start_date": sub.start_date.strftime("%Y-%m-%d") if sub.start_date else None,
        "end_date": sub.end_date.strftime("%Y-%m-%d") if sub.end_date else None
    }
    return jsonify(status)


@subscription_bp.route("/current-subscription/<int:pump_id>")
@login_required
def current_subscription(pump_id):
    sub = PumpSubscription.query.filter_by(user_id=current_user.id, pump_id=pump_id).first()
    if not sub:
        return jsonify({"plan": None, "status": "not taken", "active": False})

    return jsonify({
        "plan": sub.subscription_type,  # Silver, Gold, Diamond
        "status": sub.subscription_status,
        "active": sub.subscription_status == "active",
    })


# ------------------------
# 🔹 Create Razorpay Order
# ------------------------
@subscription_bp.route("/create-order", methods=["POST"])
@login_required
def create_order():
    """Create a Razorpay order for subscription payment"""
    data = request.get_json()
    plan_type = data.get("plan_type")
    duration = data.get("duration")
    pump_id = data.get("pump_id")

    if not all([plan_type, duration, pump_id]):
        return jsonify({"error": "Missing required fields"}), 400

    # Verify pump belongs to current user
    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        return jsonify({"error": "Pump not found"}), 404

    # Calculate total price
    plan_prices = {
        "Silver": PLAN_PRICES_INR["silver"],
        "Gold": PLAN_PRICES_INR["gold"],
        "Diamond": PLAN_PRICES_INR["diamond"],
    }
    duration_map = {
        "1 Month": 1,
        "6 Months": 6,
        "Annual": 12
    }

    base_price = plan_prices.get(plan_type.capitalize(), 0)
    months = duration_map.get(duration, 1)
    total_price = base_price * months

    if total_price <= 0:
        return jsonify({"error": "Invalid plan or duration"}), 400

    # Initialize Razorpay client
    if razorpay is None:
        return jsonify({"error": "Razorpay library not installed"}), 500
    
    try:
        razorpay_client = razorpay.Client(
            auth=(Config.RAZORPAY_KEY_ID or "rzp_test_RLoVxeTmO0idx0", 
                  Config.RAZORPAY_KEY_SECRET or "your_secret_key")
        )

        # Create order
        order_data = {
            "amount": total_price * 100,  # Amount in paise
            "currency": "INR",
            "receipt": f"sub_{pump_id}_{datetime.utcnow().timestamp()}",
            "notes": {
                "plan_type": plan_type,
                "duration": duration,
                "pump_id": str(pump_id),
                "user_id": str(current_user.id)
            }
        }

        order = razorpay_client.order.create(data=order_data)

        return jsonify({
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": Config.RAZORPAY_KEY_ID or "rzp_test_RLoVxeTmO0idx0"
        })

    except Exception as e:
        return jsonify({"error": f"Failed to create order: {str(e)}"}), 500


# ------------------------
# 🔹 Handle Payment Success
# ------------------------
@subscription_bp.route("/payment-success", methods=["POST"])
@login_required
def payment_success():
    """Handle successful Razorpay payment and activate subscription"""
    data = request.get_json()
    
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_signature = data.get("razorpay_signature")
    plan_type = data.get("plan_type")
    duration = data.get("duration")
    pump_id = data.get("pump_id")

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature, plan_type, duration, pump_id]):
        return jsonify({"error": "Missing payment details"}), 400

    # Verify payment signature (optional but recommended)
    # For now, we'll trust the payment and update subscription

    # Verify pump belongs to current user
    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        return jsonify({"error": "Pump not found"}), 404

    # Calculate subscription duration
    duration_map = {
        "1 Month": 1,
        "6 Months": 6,
        "Annual": 12
    }
    months = duration_map.get(duration, 1)
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=30 * months)

    # Update or create subscription
    existing = PumpSubscription.query.filter_by(user_id=current_user.id, pump_id=pump_id).first()

    if existing:
        existing.subscription_type = plan_type.capitalize()
        existing.subscription_status = "active"
        existing.start_date = start_date
        existing.end_date = end_date
    else:
        new_sub = PumpSubscription(
            user_id=current_user.id,
            email=current_user.email,
            pump_id=pump_id,
            pump_name=pump.name,
            pump_location=pump.location,
            subscription_type=plan_type.capitalize(),
            subscription_status="active",
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(new_sub)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"✅ {plan_type} subscription activated for {duration}!",
        "plan": plan_type.capitalize(),
        "status": "active"
    })


# ========================
# QR Code Payment Submission
# ========================
@subscription_bp.route("/submit-qr-payment", methods=["POST"])
@login_required
def submit_qr_payment():
    """Submit QR code payment screenshot for admin verification"""
    
    # Get form data
    plan_type = request.form.get("plan_type")
    duration = request.form.get("duration")
    pump_id = request.form.get("pump_id")
    transaction_id = request.form.get("transaction_id", "")  # Optional
    
    # Get screenshot file
    if 'screenshot' not in request.files:
        return jsonify({"error": "Payment screenshot is required"}), 400
    
    screenshot = request.files['screenshot']
    
    if screenshot.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(screenshot.filename):
        return jsonify({"error": "Invalid file type. Only PNG, JPG, JPEG, PDF allowed"}), 400
    
    # Verify pump belongs to current user
    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        return jsonify({"error": "Pump not found"}), 404
    
    # Calculate amount
    plan_prices = {
        "Silver": PLAN_PRICES_INR["silver"],
        "Gold": PLAN_PRICES_INR["gold"],
        "Diamond": PLAN_PRICES_INR["diamond"],
    }
    duration_map = {
        "1 Month": 1,
        "6 Months": 6,
        "Annual": 12
    }
    
    base_price = plan_prices.get(plan_type.capitalize(), 0)
    months = duration_map.get(duration, 1)
    total_amount = base_price * months
    
    if total_amount <= 0:
        return jsonify({"error": "Invalid plan or duration"}), 400
    
    # Save screenshot
    filename = secure_filename(screenshot.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    screenshot_path = os.path.join('uploads', 'payment_proofs', unique_filename)
    screenshot.save(screenshot_path)
    
    # Create payment verification record
    payment_verification = PaymentVerification(
        user_id=current_user.id,
        user_email=current_user.email,
        pump_id=pump_id,
        plan_type=plan_type.capitalize(),
        duration=duration,
        amount=total_amount,
        screenshot_filename=unique_filename,
        transaction_id=transaction_id,
        status='pending'
    )
    
    db.session.add(payment_verification)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "✅ Payment screenshot submitted! Admin will verify within 24 hours.",
        "verification_id": payment_verification.id
    })


# ========================
# Get Payment QR Code Details
# ========================
@subscription_bp.route("/payment-details", methods=["GET"])
@login_required
def payment_details():
    """Get payment QR code and UPI details"""
    # Get QR code path from config (remove 'static/' prefix for url_for)
    qr_path = Config.PAYMENT_QR_CODE.replace('static/', '')
    return jsonify({
        "upi_id": Config.UPI_ID,
        "business_name": Config.BUSINESS_NAME,
        "qr_code_url": url_for('static', filename=qr_path, _external=True)
    })


# ========================
# Check Payment Verification Status
# ========================
@subscription_bp.route("/payment-status/<int:verification_id>", methods=["GET"])
@login_required
def payment_status(verification_id):
    """Check payment verification status"""
    verification = PaymentVerification.query.filter_by(
        id=verification_id,
        user_id=current_user.id
    ).first()
    
    if not verification:
        return jsonify({"error": "Verification not found"}), 404
    
    return jsonify({
        "status": verification.status,
        "plan_type": verification.plan_type,
        "duration": verification.duration,
        "amount": verification.amount,
        "created_at": verification.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "verified_at": verification.verified_at.strftime("%Y-%m-%d %H:%M:%S") if verification.verified_at else None,
        "rejection_reason": verification.rejection_reason if verification.status == 'rejected' else None
    })


@subscription_bp.route("/is-new-pump/<int:pump_id>")
@login_required
def is_new_pump(pump_id):
    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        return jsonify({"error": "Pump not found"}), 404

    sub = PumpSubscription.query.filter_by(user_id=current_user.id, pump_id=pump_id).first()
    return jsonify({"is_new": sub is None})
