from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from extensions import db
from models import PumpOwner, FuelTransaction
from services.escrow_service import (
    EscrowError,
    InsufficientFundsError,
    VerificationRequiredError,
    InvalidStateError,
    create_fuel_transaction,
    verify_fuel_transaction,
    settle_fuel_transaction,
    get_transaction_receipt,
    list_pump_transactions,
    list_driver_transactions,
    get_pending_verifications_for_pump,
    get_daily_sales_for_pump
)


escrow_bp = Blueprint("escrow", __name__)


def _pump_owner_required():
    """Ensure current user is a PumpOwner and has an associated pump"""
    if not isinstance(current_user, PumpOwner):
        return False
    # Ensure pump owner has at least one pump
    return hasattr(current_user, 'pumps') and current_user.pumps


@escrow_bp.route("/fuel-transaction", methods=["POST"])
@login_required
def create_transaction():
    """
    Step 3: Create a fuel transaction record (Phase 1 manual entry by pump owner).
    No money moves yet. Status = pending_verification.
    """
    if not _pump_owner_required():
        return jsonify({"success": False, "message": "Access denied"}), 403

    data = request.get_json(force=True, silent=True) or {}
    required = ["pump_id", "vehicle_number", "fuel_type", "quantity_litres", "unit_price"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"success": False, "message": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        transaction = create_fuel_transaction(
            pump_id=int(data["pump_id"]),
            vehicle_number=data["vehicle_number"],
            fuel_type=data["fuel_type"],
            quantity_litres=float(data["quantity_litres"]),
            unit_price=float(data["unit_price"]),
            attendant_id=current_user.id,
            verification_level="manual",
            extra_data=data.get("extra_data")
        )
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Fuel transaction created. Pending verification.",
            "transaction_id": transaction.id,
            "status": transaction.status,
            "amount": transaction.amount
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Failed to create transaction: {str(e)}"}), 500


@escrow_bp.route("/fuel-transaction/<int:transaction_id>/verify", methods=["POST"])
@login_required
def verify_transaction(transaction_id):
    """
    Step 4: Verify a fuel transaction (Phase 1 manual verification by pump owner/supervisor).
    """
    if not _pump_owner_required():
        return jsonify({"success": False, "message": "Access denied"}), 403

    data = request.get_json(force=True, silent=True) or {}
    notes = data.get("notes")

    try:
        transaction = verify_fuel_transaction(transaction_id, current_user.id, notes)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Transaction verified. Ready to settle.",
            "transaction_id": transaction.id,
            "status": transaction.status,
            "verified_at": transaction.verified_at.isoformat()
        })
    except InvalidStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Verification failed: {str(e)}"}), 500


@escrow_bp.route("/fuel-transaction/<int:transaction_id>/settle", methods=["POST"])
@login_required
def settle_transaction(transaction_id):
    """
    Step 5: Atomic escrow release.
    Debits driver wallet, credits pump wallet, creates immutable ledger entries.
    If vehicle not linked to driver, marks as failed instead of error.
    """
    if not _pump_owner_required():
        return jsonify({"success": False, "message": "Access denied"}), 403

    try:
        transaction, group_uuid = settle_fuel_transaction(transaction_id)
        db.session.commit()
        if transaction.status == "failed":
            reason = transaction.extra_data.get("failure_reason", "Unknown error")
            return jsonify({
                "success": False,
                "message": f"Settlement failed: {reason}",
                "transaction_id": transaction.id,
                "status": transaction.status,
                "failure_reason": reason
            }), 400
        return jsonify({
            "success": True,
            "message": "Transaction settled. Funds transferred.",
            "transaction_id": transaction.id,
            "status": transaction.status,
            "settled_at": transaction.settled_at.isoformat(),
            "group_uuid": group_uuid
        })
    except VerificationRequiredError as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 400
    except EscrowError as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Settlement error for transaction {transaction_id}: {str(e)}")
        return jsonify({"success": False, "message": f"Settlement failed: {str(e)}"}), 500


@escrow_bp.route("/fuel-transaction/<int:transaction_id>/receipt", methods=["GET"])
@login_required
def transaction_receipt(transaction_id):
    """
    Step 6: Get a non-editable digital receipt.
    """
    try:
        receipt = get_transaction_receipt(transaction_id)
        return jsonify({"success": True, "receipt": receipt})
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to generate receipt: {str(e)}"}), 500


@escrow_bp.route("/fuel-transactions/pump", methods=["GET"])
@login_required
def pump_fuel_transactions():
    """List fuel transactions for a pump, with optional status filter."""
    if not _pump_owner_required():
        return jsonify({"success": False, "message": "Access denied"}), 403

    pump_id = request.args.get("pump_id", type=int)
    if not pump_id:
        return jsonify({"success": False, "message": "pump_id required"}), 400

    status = request.args.get("status")
    limit = min(request.args.get("limit", 100, type=int), 500)
    offset = request.args.get("offset", 0, type=int)

    try:
        transactions, total = list_pump_transactions(pump_id, status, limit, offset)
        return jsonify({
            "success": True,
            "transactions": [
                {
                    "id": t.id,
                    "vehicle_number": t.vehicle_number,
                    "fuel_type": t.fuel_type,
                    "quantity_litres": t.quantity_litres,
                    "unit_price": t.unit_price,
                    "amount": t.amount,
                    "status": t.status,
                    "verification_level": t.verification_level,
                    "created_at": t.created_at.isoformat(),
                    "verified_at": t.verified_at.isoformat() if t.verified_at else None,
                    "settled_at": t.settled_at.isoformat() if t.settled_at else None,
                    "attendant": t.attendant.full_name if t.attendant else None,
                    "verifier": t.verifier.full_name if t.verifier else None
                }
                for t in transactions
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch transactions: {str(e)}"}), 500


@escrow_bp.route("/fuel-transactions/driver", methods=["GET"])
@login_required
def driver_fuel_transactions():
    """List fuel transactions for the logged-in driver (cab owner)."""
    if isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    limit = min(request.args.get("limit", 100, type=int), 500)
    offset = request.args.get("offset", 0, type=int)

    try:
        transactions, total = list_driver_transactions(current_user.id, limit, offset)
        return jsonify({
            "success": True,
            "transactions": [
                {
                    "id": t.id,
                    "vehicle_number": t.vehicle_number,
                    "fuel_type": t.fuel_type,
                    "quantity_litres": t.quantity_litres,
                    "unit_price": t.unit_price,
                    "amount": t.amount,
                    "status": t.status,
                    "verification_level": t.verification_level,
                    "created_at": t.created_at.isoformat(),
                    "verified_at": t.verified_at.isoformat() if t.verified_at else None,
                    "settled_at": t.settled_at.isoformat() if t.settled_at else None,
                    "pump": {
                        "id": t.pump.id,
                        "name": t.pump.name,
                        "location": t.pump.location
                    }
                }
                for t in transactions
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch transactions: {str(e)}"}), 500


@escrow_bp.route("/fuel-transactions/pending-verification", methods=["GET"])
@login_required
def pending_verifications():
    """Get transactions pending verification for the pump owner's pumps."""
    if not _pump_owner_required():
        return jsonify({"success": False, "message": "Access denied"}), 403

    pump_id = request.args.get("pump_id", type=int)
    try:
        if pump_id:
            # Verify this pump belongs to the current owner
            pump = next((p for p in current_user.pumps if p.id == pump_id), None)
            if not pump:
                return jsonify({"success": False, "message": "Pump not found"}), 404
            pending = get_pending_verifications_for_pump(pump_id)
        else:
            # Get pending for all pumps owned by this user
            pending = []
            for pump in current_user.pumps:
                pending.extend(get_pending_verifications_for_pump(pump.id))
            # Sort by created_at
            pending.sort(key=lambda t: t.created_at)

        return jsonify({
            "success": True,
            "pending_transactions": [
                {
                    "id": t.id,
                    "vehicle_number": t.vehicle_number,
                    "fuel_type": t.fuel_type,
                    "quantity_litres": t.quantity_litres,
                    "unit_price": t.unit_price,
                    "amount": t.amount,
                    "created_at": t.created_at.isoformat(),
                    "attendant": t.attendant.full_name if t.attendant else None
                }
                for t in pending
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch pending verifications: {str(e)}"}), 500


@escrow_bp.route("/sales/daily", methods=["GET"])
@login_required
def daily_sales():
    """Get daily sales summary for a pump."""
    if not _pump_owner_required():
        return jsonify({"success": False, "message": "Access denied"}), 403

    pump_id = request.args.get("pump_id", type=int)
    date_str = request.args.get("date")
    if not pump_id or not date_str:
        return jsonify({"success": False, "message": "pump_id and date required"}), 400

    try:
        date = datetime.fromisoformat(date_str).date()
        # Verify pump ownership
        pump = next((p for p in current_user.pumps if p.id == pump_id), None)
        if not pump:
            return jsonify({"success": False, "message": "Pump not found"}), 404

        summary = get_daily_sales_for_pump(pump_id, datetime.combine(date, datetime.min.time()))
        return jsonify({"success": True, "summary": summary})
    except ValueError:
        return jsonify({"success": False, "message": "Invalid date format. Use YYYY-MM-DD"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch daily sales: {str(e)}"}), 500
