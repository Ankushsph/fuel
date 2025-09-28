# wallet.py
from flask import Blueprint, request, jsonify
from models import db, Wallet,User
from flask_login import current_user, login_required
from extensions import db, mail, oauth
wallet_bp = Blueprint("wallet", __name__)

# Add funds to wallet
@wallet_bp.route("/add_funds", methods=["POST"])
@login_required
def add_funds():
    try:
        data = request.get_json(force=True, silent=True) or {}
        amount = float(data.get("amount", 0))

        if amount <= 0:
            return jsonify({"success": False, "message": "Amount must be greater than zero."}), 400

        user = current_user

        # Initialize wallet if it doesn't exist
        if not user.wallet:
            wallet = Wallet(user_id=user.id, balance=amount)
            db.session.add(wallet)
            user.wallet = wallet
        else:
            user.wallet.balance += amount

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"₹{amount:.2f} added to wallet successfully!",
            "new_balance": round(user.wallet.balance, 2)
        })

    except ValueError:
        return jsonify({"success": False, "message": "Invalid amount entered."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

#  Get wallet balance
@wallet_bp.route("/get_balance", methods=["GET"])
@login_required
def get_balance():
    try:
        user = current_user
        balance = user.wallet.balance if user.wallet else 0.0
        return jsonify({
            "success": True,
            "balance": round(balance, 2)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@wallet_bp.route("/deduct_funds", methods=["POST"])
def deduct_funds():
    try:
        data = request.get_json(force=True, silent=True) or {}
        amount = float(data.get("amount", 0))
        cab_email = data.get("email")

        if amount <= 0:
            return jsonify({"success": False, "message": "Amount must be greater than zero."}), 400

        # Find cab owner by email
        cab_user = User.query.filter_by(email=cab_email).first()
        if not cab_user or not cab_user.wallet:
            return jsonify({"success": False, "message": "Cab owner wallet not found."}), 404

        if cab_user.wallet.balance < amount:
            return jsonify({
                "success": False,
                "message": f"Insufficient balance. Available: ₹{cab_user.wallet.balance:.2f}"
            }), 400

        cab_user.wallet.balance -= amount
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"₹{amount:.2f} deducted from {cab_email}'s wallet!",
            "new_balance": round(cab_user.wallet.balance, 2)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
