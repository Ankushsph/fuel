# vehicle_verification.py

import cv2
import threading
import time
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import db, VehicleVerification, VehicleDetails
import easyocr  # ALPR library
from datetime import datetime

vehicle_verification_bp = Blueprint('vehicle_verification', __name__)

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'])

# Keep track of active threads per verification ID
threads = {}
lock = threading.Lock()


def read_license_plate(frame):
    """
    Detect license plates in a given frame using EasyOCR.
    Returns a list of plate strings.
    """
    results = reader.readtext(frame)
    plates = []
    for (_, text, conf) in results:
        text = text.strip().replace(" ", "").upper()
        if len(text) >= 5:  # basic filter to ignore short text
            plates.append(text)
    return plates


def process_rtsp(verification: VehicleVerification):
    """
    Continuous monitoring of RTSP stream for one vehicle verification.
    """
    rtsp_url = verification.rtsp_url
    pump_id = verification.owner_id
    station_name = verification.station_name

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print(f"❌ Failed to open RTSP for {station_name}")
        return

    print(f"✅ Monitoring RTSP stream for {station_name}")

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"⚠️ Frame read failed for {station_name}, retrying in 1s...")
            time.sleep(1)
            continue

        # Optional: resize for faster processing
        frame_resized = cv2.resize(frame, (640, 480))

        # Run license plate recognition
        plates = read_license_plate(frame_resized)
        if not plates:
            time.sleep(0.5)
            continue

        with lock:
            for plate in plates:
                # Avoid duplicates
                existing = VehicleDetails.query.filter_by(plate_number=plate).first()
                if not existing:
                    new_vehicle = VehicleDetails(
                        plate_number=plate,
                        pump_id=pump_id,
                        detected_at=datetime.utcnow()
                    )
                    db.session.add(new_vehicle)
                    print(f"🛑 Detected plate: {plate} at {station_name}")
            db.session.commit()

        time.sleep(0.5)


def start_rtsp_thread(verification: VehicleVerification):
    """
    Start a background thread for RTSP monitoring if not already running.
    """
    if verification.id in threads:
        return
    thread = threading.Thread(target=process_rtsp, args=(verification,), daemon=True)
    threads[verification.id] = thread
    thread.start()


@vehicle_verification_bp.route("/start-vehicle-monitoring")
@login_required
def start_monitoring():
    """
    Start monitoring RTSP streams for all vehicle verifications of logged-in owner.
    """
    verifications = VehicleVerification.query.filter_by(owner_id=current_user.id).all()
    if not verifications:
        return jsonify({"success": False, "message": "No vehicle verification streams found."})

    for v in verifications:
        start_rtsp_thread(v)

    return jsonify({"success": True, "message": "Vehicle monitoring started."})


@vehicle_verification_bp.route("/vehicle-details")
@login_required
def get_vehicle_details():
    """
    Return all detected vehicle plates for the current owner.
    """
    plates = VehicleDetails.query.filter_by(pump_id=current_user.id).order_by(VehicleDetails.detected_at.desc()).limit(50).all()
    plate_list = [{"plate": p.plate_number, "detected_at": p.detected_at.isoformat()} for p in plates]

    return jsonify({"success": True, "plates": plate_list})
