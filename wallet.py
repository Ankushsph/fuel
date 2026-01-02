from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
import os
import uuid

from extensions import db
from models import Wallet, User, WalletTopupVerification


wallet_bp = Blueprint("wallet", __name__)


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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


@wallet_bp.route("/submit-qr-topup", methods=["POST"])
@login_required
def submit_qr_topup():
    try:
        amount_raw = request.form.get("amount")
        transaction_id = request.form.get("transaction_id", "")
        screenshot = request.files.get("screenshot")

        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Invalid amount entered."}), 400

        if amount <= 0:
            return jsonify({"success": False, "message": "Amount must be greater than zero."}), 400

        if not screenshot or screenshot.filename == "":
            return jsonify({"success": False, "message": "Payment screenshot is required."}), 400

        if not allowed_file(screenshot.filename):
            return jsonify({"success": False, "message": "Invalid file type. Only PNG, JPG, JPEG, PDF allowed."}), 400

        filename = secure_filename(screenshot.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        upload_dir = os.path.join("uploads", "payment_proofs")
        os.makedirs(upload_dir, exist_ok=True)
        screenshot_path = os.path.join(upload_dir, unique_filename)
        screenshot.save(screenshot_path)

        user = current_user

        topup = WalletTopupVerification(
            user_id=user.id,
            user_email=user.email,
            amount=amount,
            screenshot_filename=unique_filename,
            transaction_id=transaction_id,
            status="pending",
        )

        db.session.add(topup)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Payment screenshot submitted. Admin will verify within 24 hours.",
                "verification_id": topup.id,
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
