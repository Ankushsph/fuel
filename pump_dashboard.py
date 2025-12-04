# pump_dashboard.py
import os
import uuid
from datetime import datetime

from extensions import db
from flask import Blueprint, redirect, url_for, render_template, request, flash, jsonify, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from models import (
    Pump,
    PumpOwner,
    StationVehicle,
    VehicleVerification,
    PumpSubscription,
    PumpReceipt,
)
from lib.receipt_processor import process_receipt

pump_dashboard_bp = Blueprint("pump_dashboard", __name__)

RECEIPT_FEATURE_PLANS = {"gold", "diamond"}
RECEIPT_UPLOAD_DIR = os.path.join("uploads", "receipts")


def _ensure_upload_dir(app):
    target_dir = os.path.join(app.root_path, RECEIPT_UPLOAD_DIR)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


def _pump_with_access(owner: PumpOwner, pump_id: int):
    return Pump.query.filter_by(id=pump_id, owner_id=owner.id).first()


def _has_gold_features(owner_id: int, pump_id: int) -> bool:
    sub = (
        PumpSubscription.query.filter_by(
            user_id=owner_id, pump_id=pump_id, subscription_status="active"
        )
        .order_by(PumpSubscription.end_date.desc())
        .first()
    )
    if not sub or not sub.subscription_type:
        return False
    return sub.subscription_type.strip().lower() in RECEIPT_FEATURE_PLANS

# Pump Owner Dashboard
@pump_dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    owner = current_user
    if not isinstance(owner, PumpOwner):
        flash("Access denied.", "error")
        return redirect(url_for("auth.index"))
    
    pump = Pump.query.filter_by(owner_id=owner.id).first()
    if not pump:
        flash("Please add a pump first.", "info")
        return redirect(url_for("pump.select_pump"))
    
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
            "station_name": v.station_name,
            "location": v.location,
            "rtsp_url": v.rtsp_url,
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
    station_name = json_data.get("station_name") or request.form.get("station_name")
    location = json_data.get("location") or request.form.get("location")
    rtsp_url = json_data.get("rtsp_url") or request.form.get("rtsp_url")

    if not rtsp_url:
        return jsonify({"success": False, "message": "RTSP URL is required"}), 400

    # Get pump for defaults
    pump = Pump.query.filter_by(owner_id=owner.id).first()
    if not station_name and pump:
        station_name = pump.name
    if not location and pump:
        location = pump.location

    try:
        if verification_id:
            # Update existing record (ensure it belongs to the owner)
            verification = VehicleVerification.query.filter_by(
                id=int(verification_id), owner_id=owner.id
            ).first()

            if not verification:
                return jsonify({"success": False, "message": "Verification record not found"}), 404

            verification.station_name = station_name or verification.station_name
            verification.location = location or verification.location
            verification.rtsp_url = rtsp_url

            db.session.commit()
            return jsonify({
                "success": True,
                "message": "Vehicle verification updated successfully",
                "verification_id": verification.id
            })

        else:
            # Add a new record
            new_verification = VehicleVerification(
                owner_id=owner.id,
                station_name=station_name or (pump.name if pump else "Unnamed Station"),
                location=location or (pump.location if pump else ""),
                rtsp_url=rtsp_url
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


# --------------------------
# Receipt management & utilities (Gold+ plans)
# --------------------------

def _receipt_to_dict(receipt: PumpReceipt):
    data = receipt.ocr_data or {}
    return {
        "id": receipt.id,
        "original_filename": receipt.original_filename,
        "stored_filename": receipt.stored_filename,
        "file_size": receipt.file_size,
        "print_date": receipt.print_date.strftime("%d-%b-%Y") if receipt.print_date else None,
        "total_sales": receipt.total_sales,
        "created_at": receipt.created_at.strftime("%d-%b-%Y %H:%M") if receipt.created_at else None,
        "data": data,
    }


@pump_dashboard_bp.route("/<int:pump_id>/receipt/upload", methods=["POST"])
@login_required
def upload_receipt(pump_id):
    owner = current_user
    if not isinstance(owner, PumpOwner):
        current_app.logger.error("Access denied: not PumpOwner")
        return jsonify({"error": "Access denied"}), 403

    pump = _pump_with_access(owner, pump_id)
    if not pump:
        current_app.logger.error(f"Pump {pump_id} not found for owner {owner.id}")
        return jsonify({"error": "Pump not found"}), 404

    if not _has_gold_features(owner.id, pump_id):
        current_app.logger.warning(f"Gold features not available for pump {pump_id}")
        return jsonify({"error": "Please upgrade to the Gold plan to use this feature."}), 403

    current_app.logger.info(f"Files in request: {list(request.files.keys())}")
    current_app.logger.info(f"Form data: {list(request.form.keys())}")
    
    if "receipt" not in request.files:
        current_app.logger.error("No 'receipt' key in request.files")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["receipt"]
    current_app.logger.info(f"File received: {file.filename}, size: {file.content_length}")
    
    if not file.filename:
        current_app.logger.error("Empty filename")
        return jsonify({"error": "Invalid file"}), 400

    upload_dir = _ensure_upload_dir(current_app)
    safe_name = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    destination = os.path.join(upload_dir, unique_name)
    file.save(destination)

    try:
        ocr_result = process_receipt(destination)
    except Exception as exc:  # pragma: no cover - OCR errors handled at runtime
        current_app.logger.exception("OCR processing failed")
        os.remove(destination)
        return jsonify({"error": f"OCR failed: {exc}"}), 500

    print_date = None
    raw_date = ocr_result.get("printDate")
    if raw_date:
        for fmt in ("%d-%b-%Y", "%d-%b-%y"):
            try:
                print_date = datetime.strptime(raw_date, fmt)
                break
            except ValueError:
                continue

    receipt_record = PumpReceipt(
        owner_id=owner.id,
        pump_id=pump_id,
        original_filename=file.filename,
        stored_filename=unique_name,
        file_size=os.path.getsize(destination),
        ocr_data=ocr_result,
        print_date=print_date,
        total_sales=ocr_result.get("totalSales"),
    )
    db.session.add(receipt_record)
    db.session.commit()

    return jsonify({"success": True, "data": ocr_result, "record": _receipt_to_dict(receipt_record)})


@pump_dashboard_bp.route("/<int:pump_id>/receipt/history")
@login_required
def receipt_history(pump_id):
    owner = current_user
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"error": "Pump not found"}), 404
    if not _has_gold_features(owner.id, pump_id):
        return jsonify({"error": "Upgrade required"}), 403

    receipts = (
        PumpReceipt.query.filter_by(owner_id=owner.id, pump_id=pump_id)
        .order_by(PumpReceipt.print_date.desc(), PumpReceipt.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({"success": True, "receipts": [_receipt_to_dict(r) for r in receipts]})


@pump_dashboard_bp.route("/<int:pump_id>/receipt/comparison")
@login_required
def receipt_comparison(pump_id):
    owner = current_user
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"error": "Pump not found"}), 404
    if not _has_gold_features(owner.id, pump_id):
        return jsonify({"error": "Upgrade required"}), 403

    receipts = (
        PumpReceipt.query.filter_by(owner_id=owner.id, pump_id=pump_id)
        .order_by(PumpReceipt.print_date.desc(), PumpReceipt.created_at.desc())
        .limit(2)
        .all()
    )
    if len(receipts) < 2:
        return jsonify({"success": True, "message": "Need at least two receipts to compare."})

    latest, previous = receipts[0], receipts[1]

    prev_mapping = {}
    for nozzle in (previous.ocr_data or {}).get("nozzles", []):
        nozzle_id = str(nozzle.get("nozzle"))
        prev_mapping[nozzle_id] = nozzle.get("totSalesValue") or 0

    comparison = []
    for nozzle in (latest.ocr_data or {}).get("nozzles", []):
        nozzle_id = str(nozzle.get("nozzle"))
        current_value = nozzle.get("totSalesValue") or 0
        previous_value = prev_mapping.get(nozzle_id, 0)
        comparison.append(
            {
                "nozzle": nozzle_id,
                "current": current_value,
                "previous": previous_value,
                "difference": current_value - previous_value,
            }
        )

    net_sales = (latest.total_sales or 0) - (previous.total_sales or 0)

    return jsonify(
        {
            "success": True,
            "latest": _receipt_to_dict(latest),
            "previous": _receipt_to_dict(previous),
            "net_sales": net_sales,
            "comparison": comparison,
        }
    )


# --------------------------
# Density calculator
# --------------------------

@pump_dashboard_bp.route("/<int:pump_id>/density/calculate", methods=["POST"])
@login_required
def calculate_density(pump_id):
    owner = current_user
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"error": "Pump not found"}), 404
    if not _has_gold_features(owner.id, pump_id):
        return jsonify({"error": "Upgrade required"}), 403

    data = request.get_json() or {}
    fuel_type = (data.get("fuel_type") or "petrol").lower()
    density = data.get("density")
    temperature = data.get("temperature")

    try:
        density = float(density)
        temperature = float(temperature)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid density or temperature"}), 400

    coeff = 0.001 if fuel_type == "petrol" else 0.0007
    standard_density = density / (1 + coeff * (temperature - 15))

    return jsonify(
        {
            "success": True,
            "standard_density": round(standard_density, 5),
            "fuel_type": fuel_type,
        }
    )
