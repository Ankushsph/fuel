# subscription.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from models import db, PumpSubscription, Pump, Wallet

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
        return jsonify({"plan": None})

    return jsonify({
        "plan": sub.subscription_type,  # Silver, Gold, Diamond
        "status": sub.subscription_status
    })
