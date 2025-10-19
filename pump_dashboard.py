# pump_dashboard.py
from extensions import db 
from flask import Blueprint, redirect, url_for, render_template, request, flash, jsonify
from models import Pump, PumpOwner, StationVehicle, VehicleVerification

from flask_login import current_user, login_required

pump_dashboard_bp = Blueprint("pump_dashboard", __name__)

# Pump Owner Dashboard
@pump_dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    owner = current_user
    pump = Pump.query.filter_by(owner_id=owner.id).first()
    wallet_balance = owner.wallet.balance if hasattr(owner, 'wallet') and owner.wallet else 0.0
    return render_template(
        "/Pump-Owner/pump_dashboard.html",
        user=owner,
        has_password=bool(owner.password_hash),
        wallet_balance=wallet_balance,
        pump=pump
    )


# Update profile route
@pump_dashboard_bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    owner = current_user
    full_name = request.form.get("full_name", "").strip()
    if full_name:
        owner.full_name = full_name
        db.session.commit()
        flash("Profile updated successfully!", "success")
    else:
        flash("Name cannot be empty.", "error")
    return redirect(url_for("pump_dashboard.dashboard"))


# Change password route
@pump_dashboard_bp.route("/change_password", methods=["POST"])
@login_required
def change_password():
    owner = current_user
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    confirm = request.form.get("confirm_password")

    if not owner.check_password(old_password):
        flash("Current password is incorrect.", "error")
    elif new_password != confirm:
        flash("New passwords do not match.", "error")
    else:
        owner.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully!", "success")

    return redirect(url_for("pump_dashboard.dashboard"))


# Fetch RTSP streams for owner
# --------------------------
@pump_dashboard_bp.route("/get_rtsp_streams")
@login_required
def get_rtsp_streams():
    owner = current_user
    # Fetch all station vehicles for this owner
    stations = StationVehicle.query.filter_by(owner_id=owner.id).all()

    # Prepare data for frontend
    data = [
        {
            "station_id": station.id,
            "station_name": station.station_name,
            "location": station.location,
            "rtsp_url": station.rtsp_url
        }
        for station in stations
    ]

    return jsonify({"success": True, "stations": data})



@pump_dashboard_bp.route("/save_rtsp", methods=["POST"])
@login_required
def save_rtsp():
    owner = current_user

    # Try to accept JSON first, then fallback to form
    json_data = request.get_json(silent=True) or {}
    station_id = json_data.get("station_id") or request.form.get("station_id")
    station_name = json_data.get("station_name") or request.form.get("station_name")
    location = json_data.get("location") or request.form.get("location")
    rtsp_url = json_data.get("rtsp_url") or request.form.get("rtsp_url")

    # If pump exists in template context, we can default station_name/location to it
    pump = Pump.query.filter_by(owner_id=owner.id).first()
    if not station_name and pump:
        station_name = pump.name
    if not location and pump:
        location = pump.location

    if not rtsp_url:
        return jsonify({"success": False, "message": "RTSP URL is required"}), 400

    try:
        if station_id:
            # update existing station (ensure it belongs to owner)
            station = StationVehicle.query.filter_by(id=int(station_id), owner_id=owner.id).first()
            if not station:
                return jsonify({"success": False, "message": "Station not found"}), 404
            station.station_name = station_name or station.station_name
            station.location = location or station.location
            station.rtsp_url = rtsp_url
            db.session.commit()
            return jsonify({"success": True, "message": "Station updated successfully", "rtsp_url": station.rtsp_url})
        else:
            # add new station
            station = StationVehicle(
                owner_id=owner.id,
                station_name=station_name or (pump.name if pump else "Unnamed Station"),
                location=location or (pump.location if pump else ""),
                rtsp_url=rtsp_url
            )
            db.session.add(station)
            db.session.commit()
            return jsonify({"success": True, "message": "Station added successfully", "station_id": station.id, "rtsp_url": station.rtsp_url})
    except Exception as e:
        current_app.logger.exception("save_rtsp error")
        return jsonify({"success": False, "message": "Server error saving RTSP"}), 500
    

# --------------------------
# Vehicle Verification Routes
# --------------------------

@pump_dashboard_bp.route("/get_vehicle_verifications")
@login_required
def get_vehicle_verifications():
    """Fetch all vehicle verification records for the logged-in owner."""
    owner = current_user
    verifications = VehicleVerification.query.filter_by(owner_id=owner.id).all()

    data = [
        {
            "id": v.id,
            "vehicle_number": v.vehicle_number,
            "verification_status": v.verification_status,
            "verification_date": v.verification_date.strftime("%Y-%m-%d %H:%M:%S") if v.verification_date else None,
            "document_url": v.document_url,
        }
        for v in verifications
    ]

    return jsonify({"success": True, "verifications": data})


@pump_dashboard_bp.route("/save_vehicle_verification", methods=["POST"])
@login_required
def save_vehicle_verification():
    """Add or update a vehicle verification record for the current owner."""
    owner = current_user

    # Accept JSON or form data
    json_data = request.get_json(silent=True) or {}
    verification_id = json_data.get("verification_id") or request.form.get("verification_id")
    vehicle_number = json_data.get("vehicle_number") or request.form.get("vehicle_number")
    verification_status = json_data.get("verification_status") or request.form.get("verification_status")
    document_url = json_data.get("document_url") or request.form.get("document_url")

    if not vehicle_number:
        return jsonify({"success": False, "message": "Vehicle number is required"}), 400

    try:
        if verification_id:
            # Update existing record (ensure it belongs to the owner)
            verification = VehicleVerification.query.filter_by(
                id=int(verification_id), owner_id=owner.id
            ).first()

            if not verification:
                return jsonify({"success": False, "message": "Verification record not found"}), 404

            verification.vehicle_number = vehicle_number or verification.vehicle_number
            verification.verification_status = verification_status or verification.verification_status
            verification.document_url = document_url or verification.document_url

            # Record timestamp if status updated to "Verified"
            if verification_status and verification_status.lower() == "verified":
                from datetime import datetime
                verification.verification_date = datetime.utcnow()

            db.session.commit()
            return jsonify({
                "success": True,
                "message": "Vehicle verification updated successfully",
                "verification_id": verification.id
            })

        else:
            # Add a new record
            from datetime import datetime
            new_verification = VehicleVerification(
                owner_id=owner.id,
                vehicle_number=vehicle_number,
                verification_status=verification_status or "Pending",
                verification_date=(
                    datetime.utcnow()
                    if verification_status and verification_status.lower() == "verified"
                    else None
                ),
                document_url=document_url,
            )

            db.session.add(new_verification)
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Vehicle verification added successfully",
                "verification_id": new_verification.id
            })

    except Exception as e:
        current_app.logger.exception("save_vehicle_verification error")
        db.session.rollback()
        return jsonify({"success": False, "message": "Server error saving vehicle verification"}), 500
