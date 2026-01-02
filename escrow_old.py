from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import PumpOwner
from services.escrow_service import (
    process_fuel_transaction_for_pump,
    get_driver_fuel_history,
    get_pump_fuel_history,
)


escrow_bp = Blueprint("escrow", __name__)


@escrow_bp.route("/fuel-transaction", methods=["POST"])
@login_required
def fuel_transaction():
    """Create a closed-loop fuel transaction from driver wallet to pump wallet.

    Only pump owners can call this route (from their dashboard/billing UI).
    """
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    data = request.get_json(force=True, silent=True) or {}
    required = ["pump_id", "vehicle_number", "fuel_type", "quantity_litres", "unit_price"]
    if not all(data.get(k) for k in required):
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    try:
        result = process_fuel_transaction_for_pump(
            pump_owner=current_user,
            pump_id=int(data["pump_id"]),
            vehicle_number=data["vehicle_number"],
            fuel_type=data["fuel_type"],
            quantity_litres=float(data["quantity_litres"]),
            unit_price=float(data["unit_price"]),
            txn_uuid=data.get("txn_uuid"),
            attendant_id=data.get("attendant_id"),
        )
        return jsonify({"success": True, **result})
    except ValueError as ve:
        db.session.rollback()
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@escrow_bp.route("/fuel-transactions/driver", methods=["GET"])
@login_required
def driver_fuel_history():
    """Return authenticated driver's fuel transaction history."""
    data = get_driver_fuel_history(current_user)
    return jsonify({"success": True, **data})


@escrow_bp.route("/fuel-transactions/pump", methods=["GET"])
@login_required
def pump_fuel_history():
    """Return fuel sales history for the logged-in pump owner."""
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    pump_id = request.args.get("pump_id", type=int)
    data = get_pump_fuel_history(current_user, pump_id=pump_id)
    return jsonify({"success": True, **data})
