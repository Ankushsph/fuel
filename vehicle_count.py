# vehicle_count.py

import cv2
import threading
import time
from flask import Blueprint, request, jsonify
from ultralytics import YOLO
from models import db, StationVehicle

vehicle_count_bp = Blueprint('vehicle_count', __name__)

# --- Load YOLOv8 model (make sure you have your weights ready) ---
MODEL_PATH = "model/yolov8m.pt"  # adjust path
model = YOLO(MODEL_PATH)

# --- Dictionary to keep latest vehicle count per pump ---
latest_counts = {}
rtsp_threads = {}
lock = threading.Lock()


def process_rtsp(pump_id, rtsp_url):
    """
    Thread to read RTSP feed and update vehicle count
    """
    global latest_counts
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print(f"❌ Failed to open RTSP stream for pump {pump_id}")
        latest_counts[pump_id] = 0
        return

    print(f"✅ Started RTSP processing for pump {pump_id}")

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"⚠️ Frame read failed for pump {pump_id}, retrying in 1s...")
            time.sleep(1)
            continue

        # Run YOLO detection
        results = model(frame, classes=[2,3,5,7], verbose=False)  
        # class IDs for vehicles (COCO: car=2, motorcycle=3, bus=5, truck=7)

        # Count vehicles
        count = 0
        for r in results:
            count += len(r.boxes)

        with lock:
            latest_counts[pump_id] = count

        time.sleep(0.5)  # reduce CPU usage


def start_rtsp_thread(pump_id, rtsp_url):
    """
    Start a thread for a pump if not already running
    """
    if pump_id in rtsp_threads:
        return
    thread = threading.Thread(target=process_rtsp, args=(pump_id, rtsp_url), daemon=True)
    rtsp_threads[pump_id] = thread
    thread.start()


@vehicle_count_bp.route("/vehicle-count", methods=["GET"])
def get_vehicle_count():
    pump_id = request.args.get("pump_id")
    if not pump_id:
        return jsonify({"success": False, "message": "pump_id required"}), 400

    # Fetch RTSP URL from database
    station = StationVehicle.query.filter_by(owner_id=pump_id).first()
    if not station or not station.rtsp_url:
        return jsonify({"success": False, "message": "No RTSP URL configured", "vehicle_count": 0})

    # Start RTSP thread if not already started
    start_rtsp_thread(pump_id, station.rtsp_url)

    # Return latest vehicle count
    with lock:
        count = latest_counts.get(pump_id, 0)

    return jsonify({"success": True, "vehicle_count": count})
