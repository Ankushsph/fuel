# vehicle_count.py

import cv2
import os
import threading
import time
from flask import Blueprint, request, jsonify, current_app, render_template
from ultralytics import YOLO
from models import db, StationVehicle, Pump, PumpOwner

vehicle_count_bp = Blueprint('vehicle_count', __name__)

# --- Load YOLOv8 model (make sure you have your weights ready) ---
MODEL_PATH = "model/yolov8m.pt"  # adjust path
try:
    model = YOLO(MODEL_PATH)
except Exception as e:
    print(f"Warning: Could not load YOLO model: {e}")
    model = None

# --- Dictionary to keep latest vehicle count per pump ---
latest_counts = {}
rtsp_threads = {}
lock = threading.Lock()


def _resolve_video_source(rtsp_or_file: str):
    src = (rtsp_or_file or "").strip()
    if src.lower().startswith("file:"):
        rel_path = src[5:].lstrip("/\\")
        rel_path_norm = rel_path.replace("\\", "/")
        if not rel_path_norm.lower().startswith("uploads/videos/") or not rel_path_norm.lower().endswith(".mp4"):
            raise ValueError("Invalid video file source")

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploads", "videos"))
        abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), rel_path_norm))
        if not abs_path.startswith(base_dir + os.sep):
            raise ValueError("Invalid video file path")
        if not os.path.exists(abs_path):
            raise FileNotFoundError("Video file not found")
        return abs_path, True

    return src, False


def process_rtsp(pump_id, rtsp_url):
    """
    Process RTSP feed in a background thread, count vehicles using YOLO.
    """
    print(f"🔄 Starting vehicle counting for pump {pump_id}...")
    print(f"📹 RTSP URL: {rtsp_url}")

    try:
        capture_source, is_file_source = _resolve_video_source(rtsp_url)
    except Exception as e:
        print(f"❌ Invalid video source for pump {pump_id}: {e}")
        with lock:
            latest_counts[pump_id] = 0
        return
    
    cap = None
    if is_file_source:
        cap = cv2.VideoCapture(capture_source)
    else:
        # Try multiple backends for better compatibility
        connection_methods = [
            (cv2.CAP_FFMPEG, "FFMPEG"),
            (cv2.CAP_ANY, "ANY")
        ]
        
        for backend, backend_name in connection_methods:
            print(f"🔌 Trying {backend_name} backend...")
            cap = cv2.VideoCapture(capture_source, backend)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 20000)
            
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
        print(f"❌ Failed to open video source for pump {pump_id} after all attempts")
        with lock:
            latest_counts[pump_id] = 0
        return

    print(f"✅ Started RTSP processing for pump {pump_id}")
    print(f"🤖 YOLO model loaded: {model is not None}")
    
    if not model:
        print(f"⚠️  WARNING: YOLO model not loaded! Vehicle counting will not work.")
        print(f"⚠️  Please ensure model/yolov8m.pt exists")
        with lock:
            latest_counts[pump_id] = 0
        return
    
    # Use app context if available
    app_context = None
    try:
        app_context = current_app.app_context()
        app_context.push()
    except:
        print(f"⚠️  Running without app context")
        pass

    consecutive_failures = 0
    max_failures = 15
    frame_count = 0
    last_log_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            if is_file_source:
                try:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.05)
                    continue
                except Exception:
                    pass

            consecutive_failures += 1
            print(f"⚠️  Frame read failed for pump {pump_id} (attempt {consecutive_failures}/{max_failures})")
            if consecutive_failures >= max_failures:
                print(f"❌ Too many failures for pump {pump_id}, stopping")
                break
            time.sleep(1)
            continue
        
        consecutive_failures = 0
        frame_count += 1

        # Run YOLO detection if model is available
        if model:
            try:
                # Prefer tracking to reduce double-counting (unique track IDs)
                if hasattr(model, "track"):
                    results = model.track(frame, classes=[2, 3, 5, 7], verbose=False, conf=0.3, persist=True)
                else:
                    results = model(frame, classes=[2, 3, 5, 7], verbose=False, conf=0.3)

                count = 0
                for r in results:
                    if hasattr(r, "boxes") and r.boxes is not None:
                        ids = getattr(r.boxes, "id", None)
                        if ids is not None:
                            try:
                                count += len(set(int(x) for x in ids.tolist()))
                            except Exception:
                                count += len(r.boxes)
                        else:
                            count += len(r.boxes)

                with lock:
                    latest_counts[pump_id] = count
                
                # Log every 10 seconds
                current_time = time.time()
                if current_time - last_log_time >= 10:
                    print(f"🚗 Pump {pump_id}: Detected {count} vehicles (frame {frame_count})")
                    last_log_time = current_time
                    
            except Exception as e:
                print(f"❌ YOLO detection error for pump {pump_id}: {e}")
                import traceback
                traceback.print_exc()
        else:
            # If no model, return 0
            print(f"⚠️  No YOLO model available for pump {pump_id}")
            with lock:
                latest_counts[pump_id] = 0

        time.sleep(1)  # Check every 1 second for more responsive updates
    
    cap.release()
    if app_context:
        app_context.pop()
    with lock:
        latest_counts[pump_id] = 0


def start_rtsp_thread(pump_id, rtsp_url):
    """
    Start a thread for a pump if not already running
    """
    if pump_id in rtsp_threads:
        thread = rtsp_threads[pump_id]
        if thread.is_alive():
            return  # Already running
    
    thread = threading.Thread(target=process_rtsp, args=(pump_id, rtsp_url), daemon=True)
    rtsp_threads[pump_id] = thread
    thread.start()


@vehicle_count_bp.route("/vehicle-count", methods=["GET"])
def get_vehicle_count():
    pump_id = request.args.get("pump_id")
    if not pump_id:
        return jsonify({"success": False, "message": "pump_id required", "vehicle_count": 0}), 400

    try:
        pump_id = int(pump_id)
    except:
        return jsonify({"success": False, "message": "Invalid pump_id", "vehicle_count": 0}), 400

    # Fetch RTSP URL from database - use owner_id from current user context
    from flask_login import current_user
    if hasattr(current_user, 'id'):
        owner_id = current_user.id
    else:
        owner_id = pump_id
    
    station = StationVehicle.query.filter_by(owner_id=owner_id).first()
    if not station or not station.rtsp_url:
        with lock:
            count = latest_counts.get(pump_id, 0)
        return jsonify({"success": True, "message": "No RTSP URL configured", "vehicle_count": count})

    # Start RTSP thread if not already started
    start_rtsp_thread(pump_id, station.rtsp_url)

    # Return latest vehicle count
    with lock:
        count = latest_counts.get(pump_id, 0)

    return jsonify({"success": True, "vehicle_count": count})


@vehicle_count_bp.route("/<int:pump_id>/page")
def station_vehicle_data_page(pump_id):
    """
    Render station vehicle data page
    """
    from flask_login import login_required, current_user
    
    @login_required
    def _render():
        if not isinstance(current_user, PumpOwner):
            return jsonify({"success": False, "message": "Access denied"}), 403
        
        pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
        if not pump:
            return jsonify({"success": False, "message": "Pump not found"}), 404
        
        return render_template(
            "/Pump-Owner/station_vehicle_data.html",
            pump=pump,
            user=current_user
        )
    
    return _render()


@vehicle_count_bp.route("/list-streams/<int:pump_id>")
def list_streams(pump_id):
    """
    List all station vehicle streams for a pump
    """
    from flask_login import login_required, current_user
    
    @login_required
    def _list():
        if not isinstance(current_user, PumpOwner):
            return jsonify({"success": False, "message": "Access denied"}), 403
        
        streams = StationVehicle.query.filter_by(owner_id=current_user.id).all()
        stream_list = [
            {
                "id": s.id,
                "station_name": s.station_name,
                "location": s.location,
                "rtsp_url": s.rtsp_url,
                "is_active": current_user.id in rtsp_threads and rtsp_threads[current_user.id].is_alive()
            }
            for s in streams
        ]
        
        return jsonify({"success": True, "streams": stream_list})
    
    return _list()


@vehicle_count_bp.route("/add-stream/<int:pump_id>", methods=["POST"])
def add_stream(pump_id):
    """
    Add a new station vehicle stream
    """
    from flask_login import login_required, current_user
    
    @login_required
    def _add():
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
            new_stream = StationVehicle(
                owner_id=current_user.id,
                station_name=station_name,
                location=location,
                rtsp_url=rtsp_url
            )
            
            db.session.add(new_stream)
            db.session.commit()
            
            # Start monitoring thread
            start_rtsp_thread(current_user.id, rtsp_url)
            
            return jsonify({
                "success": True,
                "message": f"Stream '{station_name}' added and monitoring started!"
            })
        
        except Exception as e:
            db.session.rollback()
            try:
                current_app.logger.exception("Error adding stream")
            except:
                print(f"Error adding stream: {e}")
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    
    return _add()


@vehicle_count_bp.route("/delete-stream/<int:stream_id>", methods=["DELETE"])
def delete_stream(stream_id):
    """
    Delete a station vehicle stream
    """
    from flask_login import login_required, current_user
    
    @login_required
    def _delete():
        if not isinstance(current_user, PumpOwner):
            return jsonify({"success": False, "message": "Access denied"}), 403
        
        stream = StationVehicle.query.filter_by(id=stream_id, owner_id=current_user.id).first()
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
            try:
                current_app.logger.exception("Error deleting stream")
            except:
                print(f"Error deleting stream: {e}")
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    
    return _delete()
