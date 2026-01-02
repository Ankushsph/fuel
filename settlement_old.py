from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from models import PumpOwner


settlement_bp = Blueprint("settlement", __name__)


@settlement_bp.route("/pump-wallet", methods=["GET"])
@login_required
def pump_wallet_balance():
    """Return current pump wallet balance for the logged-in pump owner.

    This is a read-only helper endpoint for future settlement workflows.
    """
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    wallet = getattr(current_user, "wallet", None)
    balance = wallet.balance if wallet else 0.0
    return jsonify({"success": True, "balance": round(balance, 2)})


@settlement_bp.route("/pending", methods=["GET"])
@login_required
def pending_settlements():
    """List pending settlement records for the logged-in pump owner.

    Actual bank settlement processing is out of scope for Phase 1; this
    endpoint only exposes the current PumpSettlement rows (if any).
    """
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    # PumpSettlement is related via backref "settlements" on PumpOwner
    pending = []
    for s in getattr(current_user, "settlements", []):
        if s.status == "pending":
            pending.append(
                {
                    "id": s.id,
                    "amount": s.amount,
                    "currency": s.currency,
                    "status": s.status,
                    "requested_at": s.requested_at.isoformat() if s.requested_at else None,
                }
            )

    return jsonify({"success": True, "pending": pending})
