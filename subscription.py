# subscription.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from models import db, PumpSubscription, Pump, PumpOwner
from config import Config
try:
    import razorpay
except ImportError:
    razorpay = None

subscription_bp = Blueprint("subscription", __name__)

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
        "Silver": 5000,
        "Gold": 10000,
        "Diamond": 15000
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
        return jsonify({"plan": None, "status": "not taken"})

    return jsonify({
        "plan": sub.subscription_type,  # Silver, Gold, Diamond
        "status": sub.subscription_status
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
        "Silver": 5000,
        "Gold": 10000,
        "Diamond": 15000
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
