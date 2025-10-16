# pump.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Pump, PumpOwner

pump_bp = Blueprint("pump", __name__, url_prefix="/pump")


# -------------------------
# Select Pumps Page
# -------------------------
@pump_bp.route("/select")
@login_required
def select_pump():
    # Only pump owners can access
    if not isinstance(current_user, PumpOwner):
        flash("Access denied.", "error")
        return redirect(url_for("auth.index"))

    pumps = Pump.query.filter_by(owner_id=current_user.id).all()
    # Pass 'user' to template
    return render_template("/Pump-Owner/select-pump.html", pumps=pumps, user=current_user)


# -------------------------
# Add Pump
# -------------------------
@pump_bp.route("/add", methods=["POST"])
@login_required
def add_pump():
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    # Try parsing JSON safely
    try:
        data = request.get_json(force=True)  # force=True ensures parsing even if is_json=False
    except Exception as e:
        return jsonify({"success": False, "message": "Invalid JSON data."}), 400

    name = data.get("pump_name")
    location = data.get("location")

    if not name:
        return jsonify({"success": False, "message": "Pump name is required."}), 400
    if not location:
        return jsonify({"success": False, "message": "Location is required."}), 400

    # Create and save pump
    try:
        new_pump = Pump(name=name, location=location, owner_id=current_user.id)
        db.session.add(new_pump)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Database error: " + str(e)}), 500

    return jsonify({
        "success": True,
        "message": f"Pump '{name}' added successfully!"
    }), 200




# -------------------------
# Remove Pump
# -------------------------
@pump_bp.route("/remove/<int:pump_id>", methods=["POST"])
@login_required
def remove_pump(pump_id):
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        flash("Pump not found.", "error")
        return redirect(url_for("pump.select_pump"))

    db.session.delete(pump)
    db.session.commit()
    flash(f"Pump '{pump.name}' removed successfully!", "success")
    return redirect(url_for("pump.select_pump"))


# -------------------------
# Go to Pump Dashboard
# -------------------------
@pump_bp.route("/<int:pump_id>/dashboard")
@login_required
def pump_dashboard(pump_id):
    if not isinstance(current_user, PumpOwner):
        flash("Access denied.", "error")
        return redirect(url_for("auth.index"))

    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        flash("Pump not found.", "error")
        return redirect(url_for("pump.select_pump"))

    # Render a dashboard page for this pump
    return render_template("/Pump-Owner/pump_dashboard.html", pump=pump, user=current_user)
