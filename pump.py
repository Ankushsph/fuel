# pump.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Pump, PumpOwner, PumpRegistrationRequest
from datetime import datetime
from sqlalchemy.orm import joinedload

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

    # Get verified/approved pumps (pumps that have been verified by admin)
    # These are pumps where verified_at is not None
    all_owner_pumps = Pump.query.filter_by(owner_id=current_user.id).all()
    approved_pumps = [p for p in all_owner_pumps if p.verified_at is not None]
    
    print(f"DEBUG: Found {len(all_owner_pumps)} total pumps for user {current_user.id}")
    print(f"DEBUG: Found {len(approved_pumps)} approved/verified pumps")
    for pump in approved_pumps:
        print(f"DEBUG: Verified Pump {pump.id} - {pump.name} - verified_at: {pump.verified_at}")
    
    # Get pending registration requests (only those that are still pending)
    # Use join to eagerly load pump relationship
    pending_requests = PumpRegistrationRequest.query.options(
        joinedload(PumpRegistrationRequest.pump)
    ).filter_by(
        owner_id=current_user.id, 
        status='pending'
    ).all()
    
    # Filter out pending requests for pumps that are already verified
    verified_pump_ids = {p.id for p in approved_pumps}
    pending_requests = [req for req in pending_requests if req.pump_id not in verified_pump_ids]
    
    # Ensure all pending requests have valid pump relationships
    pending_requests = [req for req in pending_requests if req.pump is not None]
    
    print(f"DEBUG: Found {len(pending_requests)} pending requests (excluding verified pumps)")
    
    return render_template("/Pump-Owner/select-pump.html", 
                      approved_pumps=approved_pumps, 
                      verified_pumps=approved_pumps,
                      unverified_pumps=[], 
                      pending_requests=pending_requests, 
                      user=current_user)


# -------------------------
# Add Pump Registration Request
# -------------------------
@pump_bp.route("/add", methods=["POST"])
@login_required
def add_pump():
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    # Try parsing JSON safely
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({"success": False, "message": "Invalid JSON data."}), 400

    name = data.get("pump_name")
    location = data.get("location")
    contact_number = data.get("contact_number")
    opening_time = data.get("opening_time")
    closing_time = data.get("closing_time")

    if not name:
        return jsonify({"success": False, "message": "Pump name is required."}), 400
    if not location:
        return jsonify({"success": False, "message": "Location is required."}), 400
    if not contact_number:
        return jsonify({"success": False, "message": "Contact number is required."}), 400

    # Create pump registration request (not direct pump)
    try:
        # First create the pump record (unverified)
        new_pump = Pump(name=name, location=location, owner_id=current_user.id)
        db.session.add(new_pump)
        db.session.flush()  # Get the ID without committing
        
        # Ensure we have a valid pump ID
        if not new_pump.id:
            raise Exception("Failed to create pump record")
        
        # Create registration request for admin approval
        registration_request = PumpRegistrationRequest(
            pump_id=new_pump.id,
            owner_id=current_user.id,
            owner_name=current_user.full_name or current_user.email,
            pump_address=location,
            contact_number=contact_number,
            opening_time=opening_time or "09:00",
            closing_time=closing_time or "18:00",
            status='pending'
        )
        db.session.add(registration_request)
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Database error: " + str(e)}), 500

    return jsonify({
        "success": True,
        "message": f"Pump registration request for '{name}' submitted! Pending admin approval."
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

    pump_name = request.form.get("pumpName")
    owner_name = request.form.get("ownerName")
    address = request.form.get("address")
    contact = request.form.get("contact")
    open_time = request.form.get("openTime")
    close_time = request.form.get("closeTime")
    documents = request.files.getlist("documents[]")
    
    # Create a new pump for this registration (reliable linking)
    # Optional: allow passing pump_id if future UI supports it
    pump_id = request.form.get("pump_id")

    try:
        # Import PumpRegistrationRequest
        from models import PumpRegistrationRequest

        if not pump_id:
            if not pump_name:
                flash("Pump name is required.", "error")
                return redirect(url_for("pump.select_pump"))

            new_pump = Pump(
                name=pump_name.strip(),
                location=address.strip() if address else "",
                owner_id=current_user.id,
            )
            db.session.add(new_pump)
            db.session.flush()

            pump_id = new_pump.id
        else:
            existing_pump = Pump.query.filter_by(id=int(pump_id), owner_id=current_user.id).first()
            if not existing_pump:
                flash("Pump not found.", "error")
                return redirect(url_for("pump.select_pump"))
            pump_id = existing_pump.id
        
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
