# pump_dashboard.py
import os
import uuid
import time
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
    VehicleDetails,
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
    
    # Get all pumps for this owner
    pumps = Pump.query.filter_by(owner_id=owner.id).all()
    if not pumps:
        flash("Please add a pump first.", "info")
        return redirect(url_for("pump.select_pump"))

    # Prefer explicit pump selection
    requested_pump_id = request.args.get("pump_id", type=int)
    selected_pump = None
    if requested_pump_id:
        selected_pump = _pump_with_access(owner, requested_pump_id)

    # Otherwise default to most recently verified pump, else newest pump
    if not selected_pump:
        selected_pump = (
            Pump.query.filter_by(owner_id=owner.id)
            .order_by(Pump.verified_at.is_(None), Pump.verified_at.desc(), Pump.id.desc())
            .first()
        )

    # Only warn if the *selected* pump is not yet verified
    if selected_pump and not selected_pump.verified_at:
        flash(
            "Your pump is pending admin verification. Please complete subscription after approval.",
            "warning",
        )
    
    wallet_balance = owner.wallet.balance if hasattr(owner, 'wallet') and owner.wallet else 0.0
    
    return render_template(
        "/Pump-Owner/pump_dashboard.html",
        user=owner,
        has_password=bool(owner.password_hash),
        wallet_balance=wallet_balance,
        pump=selected_pump,
        pumps=pumps
    )

# Pump Owner Dashboard with pump_id parameter
@pump_dashboard_bp.route("/<int:pump_id>/dashboard")
@login_required
def pump_dashboard(pump_id):
    owner = current_user
    if not isinstance(owner, PumpOwner):
        flash("Access denied.", "error")
        return redirect(url_for("auth.index"))
    
    # Get specific pump for this owner
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        flash("Pump not found.", "error")
        return redirect(url_for("pump.select_pump"))
    
    # Allow access even if not verified (for subscription flow)
    # The frontend will handle showing subscription view if show_subscription=true
    
    # Get all pumps for this owner (for switching)
    pumps = Pump.query.filter_by(owner_id=owner.id).all()
    
    wallet_balance = owner.wallet.balance if hasattr(owner, 'wallet') and owner.wallet else 0.0
    
    return render_template(
        "/Pump-Owner/pump_dashboard.html",
        user=owner,
        has_password=bool(owner.password_hash),
        wallet_balance=wallet_balance,
        pump=pump,
        pumps=pumps
    )


# Check subscription status
@pump_dashboard_bp.route("/<int:pump_id>/subscription-status")
@login_required
def subscription_status(pump_id):
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"active": False, "subscription": None})
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"active": False, "subscription": None})
    
    # Check if pump has active subscription
    subscription = PumpSubscription.query.filter_by(
        user_id=owner.id, 
        pump_id=pump_id, 
        subscription_status="active"
    ).first()
    
    if subscription:
        return jsonify({
            "active": True, 
            "subscription": {
                "plan_name": subscription.subscription_type,
                "end_date": subscription.end_date.isoformat() if subscription.end_date else None
            }
        })
    else:
        return jsonify({"active": False, "subscription": None})

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


@pump_dashboard_bp.route("/generate_random_plates", methods=["POST"])
@login_required
def generate_random_plates():
    """Insert 5–10 mock VehicleDetails rows for the current owner so the UI can show plates."""
    import random
    import string
    from datetime import datetime, timedelta

    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    def random_plate():
        # Indian-style plates: e.g., MH12AB1234, DL5CXYZ, KA01EE9999
        state_codes = ["MH", "DL", "KA", "TN", "GJ", "RJ", "WB", "UP", "PB", "HR"]
        numbers = [str(random.randint(1, 99)) for _ in range(2)]
        letters = ''.join(random.choices(string.ascii_uppercase, k=2))
        suffix = str(random.randint(1000, 9999))
        return f"{random.choice(state_codes)}{random.choice(numbers)}{letters}{suffix}"

    try:
        # Insert 5–10 mock plates with recent timestamps
        num = random.randint(5, 10)
        inserted = 0
        attempts = 0
        max_attempts = num * 6
        while inserted < num and attempts < max_attempts:
            attempts += 1
            plate = random_plate()
            # plate_number is the primary key in this schema; skip duplicates
            if VehicleDetails.query.filter_by(plate_number=plate).first():
                continue
            # Random time within last 2 hours
            detected_at = datetime.utcnow() - timedelta(minutes=random.randint(0, 120))
            vd = VehicleDetails(
                pump_id=owner.id,
                plate_number=plate,
                detected_at=detected_at,
            )
            db.session.add(vd)
            inserted += 1
        db.session.commit()
        return jsonify({"success": True, "message": f"Inserted {inserted} mock plates for testing."})
    except Exception as e:
        current_app.logger.exception("generate_random_plates error")
        db.session.rollback()
        return jsonify({"success": False, "message": f"Server error generating mock plates: {str(e)}"}), 500


@pump_dashboard_bp.route("/save_vehicle_verification", methods=["POST"])
@login_required
def save_vehicle_verification():
    """Add or update a vehicle verification record for the current owner."""
    owner = current_user

    # Accept JSON or form data
    json_data = request.get_json(silent=True) or {}
    verification_id = json_data.get("verification_id") or json_data.get("id") or request.form.get("verification_id") or request.form.get("id")
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
            app_obj = current_app._get_current_object()
            verification_pk = verification.id

            import threading

            def restart_monitoring_background():
                try:
                    with app_obj.app_context():
                        from vehicle_verification import restart_rtsp_thread
                        v = VehicleVerification.query.filter_by(id=verification_pk, owner_id=owner.id).first()
                        if v:
                            restart_rtsp_thread(v)
                except Exception as e:
                    try:
                        current_app.logger.warning(f"Could not restart monitoring: {e}")
                    except Exception:
                        pass

            threading.Thread(target=restart_monitoring_background, daemon=True).start()

            return jsonify(
                {
                    "success": True,
                    "message": "Vehicle verification updated successfully. Monitoring restarted.",
                    "verification_id": verification.id,
                    "rtsp_url": verification.rtsp_url,
                    "id": verification.id,
                }
            )

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

            # Auto-start monitoring for new verification in background
            app_obj = current_app._get_current_object()
            verification_pk = new_verification.id

            import threading

            def start_monitoring_background():
                time.sleep(0.5)
                try:
                    with app_obj.app_context():
                        from vehicle_verification import restart_rtsp_thread
                        v = VehicleVerification.query.filter_by(id=verification_pk, owner_id=owner.id).first()
                        if v:
                            restart_rtsp_thread(v)
                except Exception as e:
                    try:
                        current_app.logger.warning(f"Could not auto-start monitoring: {e}")
                    except Exception:
                        pass

            threading.Thread(target=start_monitoring_background, daemon=True).start()
            
            return jsonify({
                "success": True,
                "message": "Vehicle verification added successfully. Monitoring started.",
                "id": new_verification.id,
                "verification_id": new_verification.id,
                "rtsp_url": new_verification.rtsp_url,
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

    coeff_map = {
        "petrol": 0.001,
        "diesel": 0.0007,
        "cng": 0.001,
    }
    coeff = coeff_map.get(fuel_type)
    if coeff is None:
        return jsonify({"error": "Unsupported fuel type"}), 400
    standard_density = density / (1 + coeff * (temperature - 15))

    return jsonify(
        {
            "success": True,
            "standard_density": round(standard_density, 5),
            "fuel_type": fuel_type,
        }
    )



@pump_dashboard_bp.route("/<int:pump_id>/video/upload", methods=["POST"])
@login_required
def upload_video(pump_id):
    owner = current_user
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404

    if "video" not in request.files:
        return jsonify({"success": False, "message": "No video file uploaded"}), 400

    file = request.files["video"]
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Invalid video file"}), 400

    safe_name = secure_filename(file.filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in {".mp4"}:
        return jsonify({"success": False, "message": "Only .mp4 videos are supported"}), 400

    try:
        upload_dir = os.path.join(current_app.root_path, "uploads", "videos")
        os.makedirs(upload_dir, exist_ok=True)

        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        destination = os.path.join(upload_dir, unique_name)
        file.save(destination)

        # Use a file: prefix so we can store it in existing rtsp_url columns without schema changes.
        video_source = f"file:uploads/videos/{unique_name}"
        return jsonify(
            {
                "success": True,
                "message": "Video uploaded successfully",
                "video_source": video_source,
            }
        )
    except Exception as e:
        current_app.logger.exception("Video upload failed")
        return jsonify({"success": False, "message": f"Upload failed: {str(e)}"}), 500
