# vehicle_verification.py

import cv2
import threading
import time
from flask import Blueprint, jsonify, current_app, render_template, request
from flask_login import login_required, current_user
from models import db, VehicleVerification, VehicleDetails, Pump, PumpOwner
from datetime import datetime, timedelta

vehicle_verification_bp = Blueprint('vehicle_verification', __name__)

# Initialize EasyOCR reader (lazy loading)
_reader = None

def get_ocr_reader():
    """Get or initialize EasyOCR reader"""
    global _reader
    if _reader is None:
        try:
            import easyocr
            _reader = easyocr.Reader(['en'], gpu=False)  # Use CPU to avoid CUDA issues
        except Exception as e:
            print(f"Failed to initialize EasyOCR: {e}")
            return None
    return _reader

# Keep track of active threads per verification ID
threads = {}
lock = threading.Lock()


def read_license_plate(frame):
    """
    Detect license plates in a given frame using EasyOCR.
    Returns a list of plate strings.
    """
    reader = get_ocr_reader()
    if not reader:
        return []
    
    try:
        results = reader.readtext(frame)
        plates = []
        for (_, text, conf) in results:
            text = text.strip().replace(" ", "").upper()
            # Filter: license plates are usually 5-12 characters
            if len(text) >= 5 and len(text) <= 12 and conf > 0.5:
                plates.append(text)
        return plates
    except Exception as e:
        print(f"Error reading license plate: {e}")
        return []


def process_rtsp(verification: VehicleVerification):
    """
    Process RTSP feed in a background thread, detect license plates.
    """
    rtsp_url = verification.rtsp_url
    pump_id = verification.owner_id
    station_name = verification.station_name

    print(f"🔄 Starting plate detection for {station_name}...")
    print(f"📹 RTSP URL: {rtsp_url}")

    # Try multiple backends
    cap = None
    backends = [(cv2.CAP_FFMPEG, "FFMPEG"), (cv2.CAP_ANY, "ANY")]
    
    for backend, backend_name in backends:
        print(f"🔌 Trying {backend_name} backend...")
        cap = cv2.VideoCapture(rtsp_url, backend)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 20000)
        
        # Verify connection with frame read
        max_attempts = 8
        connected = False
        for attempt in range(max_attempts):
            if cap.isOpened():
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    print(f"✅ Connected with {backend_name} on attempt {attempt + 1}")
                    connected = True
                    break
            time.sleep(1.5)
        
        if connected:
            break
        else:
            if cap:
                cap.release()
            cap = None
    
    if not cap or not cap.isOpened():
        print(f"❌ Failed to open RTSP for {station_name} after all attempts")
        return

    print(f"✅ Monitoring RTSP stream for {station_name}")
    print(f"🔍 EasyOCR reader loaded: {get_ocr_reader() is not None}")

    consecutive_failures = 0
    max_failures = 15
    frame_count = 0
    plates_detected = 0
    last_log_time = time.time()

    with flask_app.app_context():
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                consecutive_failures += 1
                print(f"⚠️  Frame read failed for {station_name} (attempt {consecutive_failures}/{max_failures})")
                if consecutive_failures >= max_failures:
                    print(f"❌ Too many failures for {station_name}, stopping")
                    break
                time.sleep(1)
                continue
            
            consecutive_failures = 0
            frame_count += 1
            
            # Process every 5th frame for better detection
            if frame_count % 5 != 0:
                time.sleep(0.1)
                continue

            # Optional: resize for faster processing
            frame_resized = cv2.resize(frame, (640, 480))

            # Run license plate recognition
            try:
                plates = read_license_plate(frame_resized)
                
                # Log progress every 30 seconds
                current_time = time.time()
                if current_time - last_log_time >= 30:
                    print(f"📊 {station_name}: Processed {frame_count} frames, detected {plates_detected} plates")
                    last_log_time = current_time
                
                if plates:
                    with lock:
                        for plate in plates:
                            # Avoid duplicates - check if same plate detected recently (within 5 minutes)
                            recent = VehicleDetails.query.filter_by(
                                plate_number=plate,
                                pump_id=pump_id
                            ).filter(
                                VehicleDetails.detected_at >= datetime.utcnow() - timedelta(minutes=5)
                            ).first()
                            
                            if not recent:
                                new_vehicle = VehicleDetails(
                                    plate_number=plate,
                                    pump_id=pump_id,
                                    detected_at=datetime.utcnow()
                                )
                                db.session.add(new_vehicle)
                                db.session.commit()
                                plates_detected += 1
                                print(f"🚗 PLATE DETECTED: {plate} at {station_name} (Total: {plates_detected})")
            except Exception as e:
                print(f"❌ Error processing frame for {station_name}: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                time.sleep(1)
                continue

            time.sleep(0.3)
    
    cap.release()
    print(f"Stopped monitoring RTSP for {station_name}")


def start_rtsp_thread(verification: VehicleVerification):
    """
    Start a background thread for RTSP monitoring if not already running.
    """
    if verification.id in threads:
        thread = threads[verification.id]
        if thread.is_alive():
            return  # Already running
    
    thread = threading.Thread(target=process_rtsp, args=(verification,), daemon=True)
    threads[verification.id] = thread
    thread.start()
    try:
        current_app.logger.info(f"Started monitoring thread for verification {verification.id}")
    except:
        print(f"Started monitoring thread for verification {verification.id}")


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

    return jsonify({"success": True, "message": f"Vehicle monitoring started for {len(verifications)} stream(s)."})


@vehicle_verification_bp.route("/vehicle-details")
@login_required
def get_vehicle_details():
    """
    Return all detected vehicle plates for the current owner.
    """
    plates = VehicleDetails.query.filter_by(pump_id=current_user.id).order_by(VehicleDetails.detected_at.desc()).limit(50).all()
    plate_list = [
        {
            "plate": p.plate_number, 
            "detected_at": p.detected_at.isoformat() if p.detected_at else None
        } 
        for p in plates
    ]

    return jsonify({"success": True, "plates": plate_list})


@vehicle_verification_bp.route("/<int:pump_id>/page")
@login_required
def vehicle_verification_page(pump_id):
    """
    Render vehicle verification page
    """
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    return render_template(
        "/Pump-Owner/vehicle_verification.html",
        pump=pump,
        user=current_user
    )


@vehicle_verification_bp.route("/list-streams/<int:pump_id>")
@login_required
def list_streams(pump_id):
    """
    List all vehicle verification streams for a pump
    """
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    streams = VehicleVerification.query.filter_by(owner_id=current_user.id).all()
    stream_list = [
        {
            "id": s.id,
            "station_name": s.station_name,
            "location": s.location,
            "rtsp_url": s.rtsp_url,
            "is_active": s.id in threads and threads[s.id].is_alive()
        }
        for s in streams
    ]
    
    return jsonify({"success": True, "streams": stream_list})


@vehicle_verification_bp.route("/add-stream/<int:pump_id>", methods=["POST"])
@login_required
def add_stream(pump_id):
    """
    Add a new vehicle verification stream
    """
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    try:
        data = request.get_json()
        station_name = data.get("station_name", "").strip()
        location = data.get("location", "").strip()
        rtsp_url = data.get("rtsp_url", "").strip()
        
        if not station_name or not location or not rtsp_url:
            return jsonify({"success": False, "message": "All fields are required"}), 400
        
        # Create new stream
        new_stream = VehicleVerification(
            owner_id=current_user.id,
            station_name=station_name,
            location=location,
            rtsp_url=rtsp_url
        )
        
        db.session.add(new_stream)
        db.session.commit()
        
        # Start monitoring thread
        start_rtsp_thread(new_stream)
        
        return jsonify({
            "success": True,
            "message": f"Stream '{station_name}' added and monitoring started!"
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error adding stream")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@vehicle_verification_bp.route("/delete-stream/<int:stream_id>", methods=["DELETE"])
@login_required
def delete_stream(stream_id):
    """
    Delete a vehicle verification stream
    """
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    stream = VehicleVerification.query.filter_by(id=stream_id, owner_id=current_user.id).first()
    if not stream:
        return jsonify({"success": False, "message": "Stream not found"}), 404
    
    try:
        station_name = stream.station_name
        db.session.delete(stream)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Stream '{station_name}' deleted successfully"
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error deleting stream")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
