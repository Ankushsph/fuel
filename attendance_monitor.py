"""
Live CCTV Monitoring with Face Recognition for Attendance
"""
import cv2
import threading
import time
import base64
import re
import urllib.parse
from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, Response, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Pump, PumpOwner, Employee, Attendance, StationVehicle

attendance_monitor_bp = Blueprint("attendance_monitor", __name__)

# Lazy initialization of face recognition service
_face_service = None

def get_face_service():
    """Get or initialize face recognition service - returns None if unavailable"""
    global _face_service
    if _face_service is None:
        try:
            from lib.face_recognition_service import FaceRecognitionService
            _face_service = FaceRecognitionService()
        except (ImportError, RuntimeError, Exception) as e:
            # Handle dlib/CUDA errors gracefully
            current_app.logger.warning(f"Face recognition service unavailable: {e}")
            _face_service = None  # Set to None to indicate unavailable
    return _face_service

# Store active monitoring sessions
active_sessions = {}
session_lock = threading.Lock()


def _pump_with_access(owner: PumpOwner, pump_id: int):
    """Verify pump belongs to owner"""
    return Pump.query.filter_by(id=pump_id, owner_id=owner.id).first()


def validate_rtsp_url(rtsp_url: str):
    """
    Validate RTSP URL format and basic structure.
    Returns (is_valid, error_message)
    """
    if not rtsp_url or not isinstance(rtsp_url, str):
        return False, "RTSP URL is required"
    
    rtsp_url = rtsp_url.strip()
    
    # Check if it starts with rtsp://
    if not rtsp_url.startswith(('rtsp://', 'rtsps://')):
        return False, "RTSP URL must start with rtsp:// or rtsps://"
    
    # Basic URL format validation
    try:
        parsed = urllib.parse.urlparse(rtsp_url)
        if not parsed.netloc:
            return False, "Invalid RTSP URL format: missing host/address"
        
        # Check for common fake patterns (but be lenient - only obvious fakes)
        # Don't block real URLs that might contain these words in paths
        fake_patterns = [
            r'rtsp://asdfghjkl',  # Only block if it's the hostname
            r'rtsp://test/',  # Only block if it's clearly a test host
            r'rtsp://fake/',  # Only block if it's clearly a fake host
            r'localhost:0',  # Invalid port on localhost
        ]
        url_lower = rtsp_url.lower()
        for pattern in fake_patterns:
            if re.search(pattern, url_lower):
                return False, "Invalid RTSP URL: appears to be a test/fake URL"
        
        # Check for valid IP or hostname
        host = parsed.hostname
        if not host:
            return False, "Invalid RTSP URL: missing hostname or IP address"
        
        # Validate port if present
        if parsed.port is not None:
            if parsed.port < 1 or parsed.port > 65535:
                return False, "Invalid RTSP URL: port must be between 1 and 65535"
        
    except Exception as e:
        return False, f"Invalid RTSP URL format: {str(e)}"
    
    return True, ""


def test_rtsp_connection(rtsp_url: str, timeout: int = 10):
    """
    Test RTSP connection with timeout - More lenient for real-world cameras.
    Returns (is_connected, error_message)
    """
    cap = None
    try:
        # Set OpenCV to use FFMPEG backend
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        
        # Set buffer size to reduce latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Increase timeout for real-world cameras
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        
        # Try to open with longer timeout for real cameras
        start_time = time.time()
        opened = False
        
        # Give more time for cameras to respond (especially ONVIF cameras)
        while time.time() - start_time < timeout:
            opened = cap.isOpened()
            if opened:
                # For validation, just check if it opens - don't require frame reading
                # Frame reading will happen during actual streaming
                return True, ""
            else:
                time.sleep(0.3)
        
        if not opened:
            # More lenient - just warn but don't fail if format is valid
            return False, f"Could not connect to RTSP stream. The URL format is valid, but connection failed. This may be normal for cameras that require authentication or are behind firewalls. Try loading the stream anyway."
        
        return True, ""
        
    except Exception as e:
        error_msg = str(e).lower()
        # More lenient error handling - don't fail on connection issues
        if 'timeout' in error_msg or 'timed out' in error_msg:
            return False, f"Connection timeout. The URL format is valid. Try loading the stream - it may work during actual streaming."
        elif 'refused' in error_msg or 'connection refused' in error_msg:
            return False, "Connection refused. Verify the camera is online and accessible."
        else:
            # Don't fail validation on connection errors - format validation is enough
            return False, f"Connection test failed, but URL format is valid. You can try loading the stream."
    
    finally:
        if cap is not None:
            cap.release()


@attendance_monitor_bp.route("/<int:pump_id>/monitor")
@login_required
def monitor_page(pump_id):
    """Render the live monitoring page"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    # Get RTSP streams for this pump
    stations = StationVehicle.query.filter_by(owner_id=owner.id).all()
    
    # Check if employees are registered
    employees_count = Employee.query.filter_by(
        pump_id=pump_id,
        owner_id=owner.id,
        is_active=True
    ).count()
    
    return render_template(
        "/Pump-Owner/attendance_monitor.html",
        pump=pump,
        user=owner,
        stations=stations,
        employees_count=employees_count
    )


@attendance_monitor_bp.route("/<int:pump_id>/validate_stream", methods=["POST"])
@login_required
def validate_stream(pump_id):
    """Validate RTSP stream before loading"""
    try:
        owner = current_user
        if not isinstance(owner, PumpOwner):
            return jsonify({"success": False, "message": "Access denied"}), 403
        
        pump = _pump_with_access(owner, pump_id)
        if not pump:
            return jsonify({"success": False, "message": "Pump not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Invalid request data"}), 400
            
        rtsp_url = data.get("rtsp_url", "").strip()
        
        if not rtsp_url:
            return jsonify({"success": False, "message": "RTSP URL is required"}), 400
        
        # Validate format
        is_valid, error_msg = validate_rtsp_url(rtsp_url)
        if not is_valid:
            return jsonify({"success": False, "message": error_msg}), 400
        
        # For real-world deployment, accept any valid RTSP URL format
        # Don't test connection during validation - many cameras don't respond to quick tests
        # Connection will be tested during actual streaming where it matters
        current_app.logger.info(f"RTSP URL format validated for pump {pump_id}: {rtsp_url}")
        
        return jsonify({
            "success": True,
            "message": "RTSP URL format is valid. You can now load the stream."
        })
    except Exception as e:
        current_app.logger.exception(f"Error in validate_stream: {e}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@attendance_monitor_bp.route("/<int:pump_id>/video_feed")
@login_required
def video_feed(pump_id):
    """Video streaming route with face recognition"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return Response("Access denied", status=403)
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return Response("Pump not found", status=404)
    
    # Get RTSP URL from query parameter
    rtsp_url = request.args.get("rtsp_url")
    if not rtsp_url:
        current_app.logger.error("RTSP URL missing from request")
        return Response("RTSP URL required", status=400)
    
    # Decode URL in case it was double-encoded
    try:
        rtsp_url = urllib.parse.unquote(rtsp_url)
        # Handle multiple encodings
        if '%' in rtsp_url:
            rtsp_url = urllib.parse.unquote(rtsp_url)
    except Exception as e:
        current_app.logger.warning(f"URL decode warning: {e}")
    
    # Basic validation - just check format
    if not rtsp_url.startswith(('rtsp://', 'rtsps://')):
        current_app.logger.warning(f"Invalid RTSP URL format from user {owner.id}: {rtsp_url}")
        return Response("Invalid RTSP URL format", status=400)
    
    # Log the connection attempt
    current_app.logger.info(f"Starting RTSP stream for pump {pump_id}: {rtsp_url}")
    # Connection will be attempted during actual streaming with proper timeouts
    
    # Get employee encodings
    employees = Employee.query.filter_by(
        pump_id=pump_id,
        owner_id=owner.id,
        is_active=True
    ).all()
    
    employee_encodings = {}
    employee_info = {}
    
    # Get face service (may be None if CUDA/dlib unavailable)
    face_service = get_face_service()
    
    # Only process employees if face service is available
    if face_service and employees:
        for emp in employees:
            if emp.face_encoding:
                try:
                    encoding = face_service.deserialize_encoding(emp.face_encoding)
                    employee_encodings[emp.id] = encoding
                    employee_info[emp.id] = {
                        "name": emp.name,
                        "designation": emp.designation
                    }
                except Exception as e:
                    current_app.logger.warning(f"Failed to deserialize encoding for employee {emp.id}: {e}")
                    continue
    
    # Allow stream viewing even without employees or face recognition
    if not employee_encodings:
        if not face_service:
            current_app.logger.info(f"Face recognition unavailable (CUDA/dlib issue) - streaming video only for pump {pump_id}")
        else:
            current_app.logger.info(f"No employees registered for pump {pump_id} - streaming without face recognition")
    
    def generate_frames():
        """Generate video frames with face detection"""
        cap = None
        consecutive_failures = 0
        max_failures = 10  # Max consecutive frame read failures before giving up
        
        try:
            # Try multiple connection methods for better compatibility
            cap = None
            connection_methods = [
                (cv2.CAP_FFMPEG, "FFMPEG"),
                (cv2.CAP_ANY, "ANY")
            ]
            
            for backend, backend_name in connection_methods:
                current_app.logger.info(f"Attempting connection with {backend_name} backend...")
                cap = cv2.VideoCapture(rtsp_url, backend)
                
                # Set properties before opening
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000)  # 20 second timeout
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 20000)
                
                # Try to read a test frame
                max_connect_attempts = 8
                connected = False
                
                for attempt in range(max_connect_attempts):
                    if cap.isOpened():
                        # Try to read a frame to verify connection
                        ret, test_frame = cap.read()
                        if ret and test_frame is not None:
                            current_app.logger.info(f"Successfully connected with {backend_name} backend on attempt {attempt + 1}")
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
                current_app.logger.error(f"Failed to open RTSP stream after trying all backends: {rtsp_url}")
                # Yield multiple error frames so frontend can see it
                for _ in range(10):
                    yield _error_frame("Stream connection timeout. Check camera and network.")
                    time.sleep(1)
                return
            
            current_app.logger.info(f"RTSP stream opened successfully for pump {pump_id}")
            
            # Track last attendance mark per employee (to avoid duplicate marks)
            last_attendance_mark = {}
            attendance_cooldown = 30  # seconds between attendance marks for same employee
            
            frame_count = 0
            detection_interval = 5  # Process every 5th frame for performance
            
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    current_app.logger.warning(f"Frame read failed (attempt {consecutive_failures}/{max_failures})")
                    if consecutive_failures >= max_failures:
                        current_app.logger.error(f"Stream connection lost after {max_failures} consecutive failures")
                        for _ in range(5):
                            yield _error_frame("Stream connection lost. Reconnecting...")
                            time.sleep(1)
                        break
                    time.sleep(0.5)
                    continue
                
                # Reset failure counter on successful read
                consecutive_failures = 0
                
                frame_count += 1
                
                # Process frame for face detection (only if employees are registered and service is available)
                if employee_encodings and face_service and frame_count % detection_interval == 0:
                    try:
                        # Find employee in frame
                        result = face_service.find_employee_in_frame(frame, employee_encodings)
                        
                        if result:
                            employee_id, confidence, face_location = result
                            
                            # Draw bounding box and label
                            emp_info = employee_info[employee_id]
                            frame = face_service.draw_face_box(
                                frame, 
                                face_location, 
                                emp_info["name"], 
                                confidence
                            )
                            
                            # Mark attendance if confidence is high and cooldown passed
                            current_time = time.time()
                            if confidence >= 0.7:  # High confidence threshold
                                last_mark_time = last_attendance_mark.get(employee_id, 0)
                                
                                if current_time - last_mark_time >= attendance_cooldown:
                                    # Mark attendance in background thread
                                    threading.Thread(
                                        target=mark_attendance_async,
                                        args=(pump_id, employee_id, confidence),
                                        daemon=True
                                    ).start()
                                    
                                    last_attendance_mark[employee_id] = current_time
                                    
                                    # Draw attendance confirmation
                                    cv2.putText(
                                        frame,
                                        "ATTENDANCE MARKED",
                                        (10, 30),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.7,
                                        (0, 255, 0),
                                        2
                                    )
                    
                    except Exception as e:
                        current_app.logger.warning(f"Error in face detection: {e}")
                
                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ret:
                    continue
                
                frame_bytes = buffer.tobytes()
                
                # Yield frame in multipart format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        except Exception as e:
            current_app.logger.exception(f"Error in video stream generation: {e}")
            yield _error_frame(f"Stream error: {str(e)}")
        
        finally:
            if cap is not None:
                cap.release()
                try:
                    current_app.logger.info(f"RTSP stream released for pump {pump_id}")
                except RuntimeError:
                    # Outside app context - just print
                    print(f"RTSP stream released for pump {pump_id}")


    # Return the streaming response
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


def _error_frame(message: str) -> bytes:
    """Generate an error frame image with message"""
    import numpy as np
    # Create a black frame with error message
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, "STREAM ERROR", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(frame, message[:50], (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if ret:
        frame_bytes = buffer.tobytes()
        return (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    return b''


def mark_attendance_async(pump_id: int, employee_id: int, confidence: float):
    """Mark attendance asynchronously"""
    try:
        with current_app.app_context():
            today = date.today()
            now = datetime.now()
            
            # Check if attendance already marked today
            attendance = Attendance.query.filter_by(
                employee_id=employee_id,
                attendance_date=today
            ).first()
            
            if attendance:
                # Update check-in time if not set, or update check-out if check-in exists
                if not attendance.check_in_time:
                    attendance.check_in_time = now
                    attendance.status = "present"
                    attendance.detection_method = "face_recognition"
                    attendance.detected_confidence = confidence
                else:
                    # Update check-out time
                    attendance.check_out_time = now
                    if attendance.check_in_time:
                        delta = now - attendance.check_in_time
                        attendance.total_hours = delta.total_seconds() / 3600.0
            else:
                # Create new attendance record
                attendance = Attendance(
                    employee_id=employee_id,
                    pump_id=pump_id,
                    attendance_date=today,
                    check_in_time=now,
                    status="present",
                    detection_method="face_recognition",
                    detected_confidence=confidence
                )
                db.session.add(attendance)
            
            db.session.commit()
            current_app.logger.info(
                f"Attendance marked for employee {employee_id} at pump {pump_id} "
                f"(confidence: {confidence:.2f})"
            )
    
    except Exception as e:
        current_app.logger.exception(f"Error marking attendance async: {e}")
        db.session.rollback()


@attendance_monitor_bp.route("/<int:pump_id>/attendance/report")
@login_required
def attendance_report(pump_id):
    """Attendance report page"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    # Get employees for filter
    employees = Employee.query.filter_by(
        pump_id=pump_id,
        owner_id=owner.id,
        is_active=True
    ).all()
    
    return render_template(
        "/Pump-Owner/attendance_report.html",
        pump=pump,
        user=owner,
        employees=employees
    )


@attendance_monitor_bp.route("/<int:pump_id>/detect_face", methods=["POST"])
@login_required
def detect_face(pump_id):
    """Detect face in uploaded frame and mark attendance"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    try:
        # Get image data (base64 encoded)
        data = request.get_json()
        image_data = data.get("image")
        
        if not image_data:
            return jsonify({"success": False, "message": "Image data required"}), 400
        
        # Decode base64 image
        import base64
        import numpy as np
        from PIL import Image
        import io
        
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Get employee encodings
        employees = Employee.query.filter_by(
            pump_id=pump_id,
            owner_id=owner.id,
            is_active=True
        ).all()
        
        employee_encodings = {}
        employee_info = {}
        
        face_service = get_face_service()
        if not face_service:
            return jsonify({"success": False, "message": "Face recognition service unavailable (CUDA/dlib issue)"}), 503
        
        for emp in employees:
            if emp.face_encoding:
                try:
                    encoding = face_service.deserialize_encoding(emp.face_encoding)
                    employee_encodings[emp.id] = encoding
                    employee_info[emp.id] = {
                        "name": emp.name,
                        "designation": emp.designation
                    }
                except Exception as e:
                    current_app.logger.warning(f"Failed to deserialize encoding: {e}")
                    continue
        
        if not employee_encodings:
            return jsonify({"success": False, "message": "No employees registered"}), 400
        
        # Find employee in frame
        result = face_service.find_employee_in_frame(frame, employee_encodings)
        
        if not result:
            return jsonify({
                "success": False,
                "message": "No recognized employee found in the image"
            }), 404
        
        employee_id, confidence, face_location = result
        
        if confidence < 0.7:
            return jsonify({
                "success": False,
                "message": f"Low confidence match ({confidence:.2f}). Please ensure clear face visibility."
            }), 400
        
        # Mark attendance
        today = date.today()
        now = datetime.now()
        
        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            attendance_date=today
        ).first()
        
        if attendance:
            if not attendance.check_in_time:
                attendance.check_in_time = now
                attendance.status = "present"
            else:
                attendance.check_out_time = now
                if attendance.check_in_time:
                    delta = now - attendance.check_in_time
                    attendance.total_hours = delta.total_seconds() / 3600.0
        else:
            attendance = Attendance(
                employee_id=employee_id,
                pump_id=pump_id,
                attendance_date=today,
                check_in_time=now,
                status="present",
                detection_method="face_recognition",
                detected_confidence=confidence
            )
            db.session.add(attendance)
        
        db.session.commit()
        
        emp_info = employee_info[employee_id]
        
        return jsonify({
            "success": True,
            "message": f"Attendance marked for {emp_info['name']}",
            "employee": {
                "id": employee_id,
                "name": emp_info["name"],
                "designation": emp_info["designation"]
            },
            "confidence": confidence,
            "attendance": {
                "check_in_time": attendance.check_in_time.isoformat() if attendance.check_in_time else None,
                "check_out_time": attendance.check_out_time.isoformat() if attendance.check_out_time else None,
                "status": attendance.status
            }
        })
    
    except Exception as e:
        current_app.logger.exception("Error in face detection endpoint")
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

