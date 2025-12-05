# pump.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
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
@pump_bp.route("/remove/<int:pump_id>", methods=["DELETE"])
@login_required
def remove_pump(pump_id):
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404

    try:
        db.session.delete(pump)
        db.session.commit()
        return jsonify({"success": True, "message": f"Pump '{pump.name}' removed successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Database error: " + str(e)}), 500

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


# -------------------------
# Pump registration form submit (modal in select-pump.html)
# -------------------------
@pump_bp.route("/submit", methods=["POST"])
@login_required
def submit_pump_registration():
    """
    Handles the Pump Registration Form POST from the modal in select-pump.html.
    Saves registration data for admin verification.
    """
    if not isinstance(current_user, PumpOwner):
        flash("Access denied.", "error")
        return redirect(url_for("auth.index"))

    owner_name = request.form.get("ownerName")
    address = request.form.get("address")
    contact = request.form.get("contact")
    open_time = request.form.get("openTime")
    close_time = request.form.get("closeTime")
    documents = request.files.getlist("documents[]")
    
    # Get pump_id from form or use the last created pump
    pump_id = request.form.get("pump_id")
    if not pump_id:
        # Use the most recent pump for this owner
        latest_pump = Pump.query.filter_by(owner_id=current_user.id).order_by(Pump.id.desc()).first()
        if not latest_pump:
            flash("Please add a pump first before registering.", "error")
            return redirect(url_for("pump.select_pump"))
        pump_id = latest_pump.id

    try:
        # Import PumpRegistrationRequest
        from models import PumpRegistrationRequest
        
        # Save uploaded documents
        saved_documents = []
        if documents:
            import os
            import uuid
            from werkzeug.utils import secure_filename
            
            os.makedirs('uploads/pump_documents', exist_ok=True)
            
            for doc in documents:
                if doc and doc.filename:
                    filename = secure_filename(doc.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    doc_path = os.path.join('uploads', 'pump_documents', unique_filename)
                    doc.save(doc_path)
                    saved_documents.append(unique_filename)
        
        # Create registration request
        registration = PumpRegistrationRequest(
            pump_id=pump_id,
            owner_id=current_user.id,
            owner_name=owner_name,
            pump_address=address,
            contact_number=contact,
            opening_time=open_time,
            closing_time=close_time,
            documents=saved_documents,
            status='pending'
        )
        
        db.session.add(registration)
        db.session.commit()
        
        current_app.logger.info(
            "Pump registration submitted by %s for pump_id=%s",
            current_user.email,
            pump_id
        )
        
        flash("✅ Pump registration submitted! Admin will verify within 24 hours.", "success")
    except Exception as e:
        current_app.logger.error("Error while handling pump registration submit: %s", e)
        db.session.rollback()
        flash("Something went wrong while submitting the form. Please try again.", "error")

    return redirect(url_for("pump.select_pump"))
