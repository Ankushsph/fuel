from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func

from extensions import db
from models import PumpOwner, PumpWallet, PumpSettlement, FuelTransaction


settlement_bp = Blueprint("settlement", __name__)


@settlement_bp.route("/pump-wallet", methods=["GET"])
@login_required
def pump_wallet_balance():
    """Return current pump wallet balance for the logged-in pump owner."""
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    wallet = getattr(current_user, "pump_wallet", None)
    balance = wallet.balance if wallet else 0.0
    return jsonify({"success": True, "balance": round(balance, 2)})


@settlement_bp.route("/pending", methods=["GET"])
@login_required
def pending_settlements():
    """List pending settlement records for the logged-in pump owner."""
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    try:
        settlements = PumpSettlement.query.filter_by(pump_owner_id=current_user.id, status="pending")\
            .order_by(PumpSettlement.requested_at.desc()).limit(20).all()

        return jsonify({
            "success": True,
            "pending": [
                {
                    "id": s.id,
                    "amount": s.amount,
                    "currency": s.currency,
                    "requested_at": s.requested_at.isoformat()
                }
                for s in settlements
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch pending settlements: {str(e)}"}), 500


@settlement_bp.route("/request", methods=["POST"])
@login_required
def request_settlement():
    """Request settlement of available pump wallet balance to bank account."""
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    data = request.get_json(force=True, silent=True) or {}
    amount = data.get("amount")
    bank_reference = data.get("bank_reference", "")

    if not amount or float(amount) <= 0:
        return jsonify({"success": False, "message": "Invalid settlement amount"}), 400

    try:
        amount = float(amount)
        wallet = current_user.pump_wallet
        if not wallet or wallet.balance < amount:
            return jsonify({"success": False, "message": "Insufficient wallet balance"}), 400

        # Create settlement request
        settlement = PumpSettlement(
            pump_wallet_id=wallet.id,
            pump_owner_id=current_user.id,
            amount=amount,
            bank_reference=bank_reference,
            status="pending"
        )
        db.session.add(settlement)
        db.session.flush()  # Get ID

        # Optional: Mark wallet balance as pending (not deducted until processed)
        # In production, you'd hold this amount or use a ledger

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Settlement request submitted. You will be notified upon processing.",
            "settlement_id": settlement.id,
            "amount": amount,
            "status": "pending"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Failed to request settlement: {str(e)}"}), 500


@settlement_bp.route("/history", methods=["GET"])
@login_required
def settlement_history():
    """Get settlement history for the pump owner."""
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    try:
        settlements = PumpSettlement.query.filter_by(pump_owner_id=current_user.id)\
            .order_by(PumpSettlement.requested_at.desc()).limit(50).all()

        return jsonify({
            "success": True,
            "settlements": [
                {
                    "id": s.id,
                    "amount": s.amount,
                    "currency": s.currency,
                    "status": s.status,
                    "bank_reference": s.bank_reference,
                    "requested_at": s.requested_at.isoformat(),
                    "processed_at": s.processed_at.isoformat() if s.processed_at else None
                }
                for s in settlements
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch settlement history: {str(e)}"}), 500


@settlement_bp.route("/summary", methods=["GET"])
@login_required
def settlement_summary():
    """Get settlement summary: available balance, pending settlements, today's sales."""
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    try:
        wallet = current_user.pump_wallet
        balance = wallet.balance if wallet else 0.0

        # Pending settlements amount
        pending = db.session.query(func.sum(PumpSettlement.amount))\
            .filter_by(pump_owner_id=current_user.id, status="pending").scalar()
        pending_amount = float(pending) if pending else 0.0

        # Today's sales (settled fuel transactions)
        today = datetime.utcnow().date()
        today_sales = db.session.query(func.sum(FuelTransaction.amount))\
            .join(Pump, FuelTransaction.pump_id == Pump.id)\
            .filter(Pump.owner_id == current_user.id,
                    FuelTransaction.status == "settled",
                    func.date(FuelTransaction.settled_at) == today).scalar()
        today_sales_amount = float(today_sales) if today_sales else 0.0

        return jsonify({
            "success": True,
            "summary": {
                "available_balance": round(balance, 2),
                "pending_settlements": round(pending_amount, 2),
                "today_sales": round(today_sales_amount, 2),
                "currency": "INR"
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch settlement summary: {str(e)}"}), 500


# Admin-only routes for processing settlements (Phase 1 manual)
@settlement_bp.route("/admin/list", methods=["GET"])
@login_required
def admin_list_pending():
    """List all pending settlements (admin only)."""
    # In production, add admin role check
    try:
        settlements = db.session.query(PumpSettlement, PumpOwner)\
            .join(PumpOwner, PumpSettlement.pump_owner_id == PumpOwner.id)\
            .filter(PumpSettlement.status == "pending")\
            .order_by(PumpSettlement.requested_at.asc()).all()

        return jsonify({
            "success": True,
            "settlements": [
                {
                    "id": s.id,
                    "amount": s.amount,
                    "currency": s.currency,
                    "bank_reference": s.bank_reference,
                    "requested_at": s.requested_at.isoformat(),
                    "pump_owner": {
                        "id": o.id,
                        "email": o.email,
                        "full_name": o.full_name
                    }
                }
                for s, o in settlements
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch pending settlements: {str(e)}"}), 500


@settlement_bp.route("/admin/process/<int:settlement_id>", methods=["POST"])
@login_required
def admin_process_settlement(settlement_id):
    """Process a settlement (admin only)."""
    # In production, add admin role check
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")  # "approve" or "reject"
    notes = data.get("notes", "")

    if action not in ("approve", "reject"):
        return jsonify({"success": False, "message": "Invalid action"}), 400

    try:
        settlement = PumpSettlement.query.get_or_404(settlement_id)
        if settlement.status != "pending":
            return jsonify({"success": False, "message": "Settlement already processed"}), 400

        if action == "approve":
            # Deduct from pump wallet
            wallet = settlement.pump_wallet
            if wallet.balance < settlement.amount:
                return jsonify({"success": False, "message": "Insufficient wallet balance to settle"}), 400

            wallet.balance -= settlement.amount
            settlement.status = "approved"
            settlement.processed_at = datetime.utcnow()
            # In production, you'd add bank_reference or transfer_id
        else:
            settlement.status = "rejected"
            settlement.processed_at = datetime.utcnow()
            # Add rejection notes to extra_data if needed

        db.session.add(settlement)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Settlement {action}d successfully.",
            "settlement_id": settlement.id,
            "status": settlement.status,
            "processed_at": settlement.processed_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Failed to process settlement: {str(e)}"}), 500
