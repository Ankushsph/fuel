"""
ANPR (Automatic Number Plate Recognition) Processor
Uses OpenCV + EasyOCR for real-time number plate detection
"""

import cv2
import easyocr
import numpy as np
from datetime import datetime
import threading
import time
import re
import os
from collections import defaultdict

class ANPRProcessor:
    """Process RTSP streams for number plate detection"""
    
    def __init__(self):
        self.reader = None
        self.active_streams = {}
        self.detection_cache = defaultdict(list)
        self.initialize_ocr()
    
    def initialize_ocr(self):
        """Initialize EasyOCR reader"""
        try:
            self.reader = easyocr.Reader(['en'], gpu=False)
            print("✅ EasyOCR initialized successfully")
        except Exception as e:
            print(f"⚠️ EasyOCR initialization failed: {e}")
            self.reader = None
    
    def preprocess_image(self, image):
        """Preprocess image for better OCR results"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while keeping edges sharp
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        return thresh
    
    def detect_plate_region(self, image):
        """Detect potential license plate regions using contours"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.bilateralFilter(gray, 11, 17, 17)
        edged = cv2.Canny(blur, 30, 200)
        
        # Find contours
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
        
        plate_regions = []
        
        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.018 * peri, True)
            
            # License plates are typically rectangular (4 corners)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect_ratio = w / float(h)
                
                # Indian license plates have aspect ratio between 2:1 and 5:1
                if 2.0 <= aspect_ratio <= 5.0 and w > 80 and h > 20:
                    plate_regions.append((x, y, w, h))
        
        return plate_regions
    
    def clean_plate_text(self, text):
        """Clean and format detected plate text"""
        # Remove special characters and spaces
        text = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        # Indian plate format: XX00XX0000 or XX00X0000
        # Examples: KA19MB1234, MH12AB1234, DL8CAF1234
        
        # Try to match Indian plate patterns
        patterns = [
            r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$',  # KA19MB1234
            r'^[A-Z]{2}\d{2}[A-Z]{3}\d{4}$',     # DL8CAF1234
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return text
        
        # If no exact match, try to extract valid parts
        # Look for state code (2 letters)
        state_match = re.search(r'^[A-Z]{2}', text)
        if state_match and len(text) >= 8:
            return text[:10]  # Return first 10 characters
        
        return text if len(text) >= 6 else None
    
    def detect_number_plate(self, image, confidence_threshold=0.7):
        """Detect and read number plate from image"""
        if self.reader is None:
            return None, 0.0, None
        
        try:
            # Detect plate regions
            plate_regions = self.detect_plate_region(image)
            
            best_result = None
            best_confidence = 0.0
            best_plate_image = None
            
            # If plate regions found, focus on them
            if plate_regions:
                for (x, y, w, h) in plate_regions:
                    # Extract plate region
                    plate_roi = image[y:y+h, x:x+w]
                    
                    # Preprocess
                    processed = self.preprocess_image(plate_roi)
                    
                    # Run OCR
                    results = self.reader.readtext(processed)
                    
                    for (bbox, text, confidence) in results:
                        if confidence > best_confidence:
                            cleaned_text = self.clean_plate_text(text)
                            if cleaned_text:
                                best_result = cleaned_text
                                best_confidence = confidence
                                best_plate_image = plate_roi
            
            # If no good results from regions, try full image
            if best_confidence < confidence_threshold:
                results = self.reader.readtext(image)
                for (bbox, text, confidence) in results:
                    if confidence > best_confidence:
                        cleaned_text = self.clean_plate_text(text)
                        if cleaned_text:
                            best_result = cleaned_text
                            best_confidence = confidence
                            best_plate_image = image
            
            return best_result, best_confidence, best_plate_image
            
        except Exception as e:
            print(f"Error in plate detection: {e}")
            return None, 0.0, None
    
    def process_rtsp_stream(self, camera_id, rtsp_url, callback, 
                           detection_interval=2, confidence_threshold=0.7):
        """Process RTSP stream for continuous plate detection"""
        print(f"🎥 Starting ANPR stream for camera {camera_id}")
        print(f"📹 RTSP URL: {rtsp_url}")
        
        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            print(f"❌ Failed to open RTSP stream: {rtsp_url}")
            return
        
        frame_count = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        skip_frames = int(fps * detection_interval)
        
        print(f"✅ ANPR stream started (FPS: {fps}, Detection interval: {detection_interval}s)")
        
        while camera_id in self.active_streams:
            ret, frame = cap.read()
            
            if not ret:
                print(f"⚠️ Failed to read frame from camera {camera_id}")
                time.sleep(1)
                continue
            
            frame_count += 1
            
            # Process every N frames based on detection interval
            if frame_count % skip_frames == 0:
                plate_number, confidence, plate_image = self.detect_number_plate(
                    frame, confidence_threshold
                )
                
                if plate_number and confidence >= confidence_threshold:
                    # Check if this plate was recently detected (avoid duplicates)
                    recent_detections = self.detection_cache[camera_id]
                    current_time = time.time()
                    
                    # Clean old detections (older than 30 seconds)
                    self.detection_cache[camera_id] = [
                        (plate, timestamp) for plate, timestamp in recent_detections
                        if current_time - timestamp < 30
                    ]
                    
                    # Check if this plate was detected recently
                    is_duplicate = any(
                        plate == plate_number and current_time - timestamp < 10
                        for plate, timestamp in self.detection_cache[camera_id]
                    )
                    
                    if not is_duplicate:
                        print(f"🚗 Detected: {plate_number} (Confidence: {confidence:.2f})")
                        
                        # Add to cache
                        self.detection_cache[camera_id].append((plate_number, current_time))
                        
                        # Save images
                        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                        
                        # Save full frame
                        frame_path = f"uploads/anpr_detections/frame_{camera_id}_{timestamp_str}.jpg"
                        os.makedirs(os.path.dirname(frame_path), exist_ok=True)
                        cv2.imwrite(frame_path, frame)
                        
                        # Save plate image
                        plate_path = None
                        if plate_image is not None:
                            plate_path = f"uploads/anpr_detections/plate_{camera_id}_{timestamp_str}.jpg"
                            cv2.imwrite(plate_path, plate_image)
                        
                        # Callback with detection data
                        detection_data = {
                            'camera_id': camera_id,
                            'vehicle_number': plate_number,
                            'confidence': confidence,
                            'detected_at': datetime.now(),
                            'frame_path': frame_path,
                            'plate_path': plate_path
                        }
                        
                        callback(detection_data)
        
        cap.release()
        print(f"🛑 ANPR stream stopped for camera {camera_id}")
    
    def start_stream(self, camera_id, rtsp_url, callback, **kwargs):
        """Start processing RTSP stream in background thread"""
        if camera_id in self.active_streams:
            print(f"⚠️ Camera {camera_id} is already active")
            return False
        
        self.active_streams[camera_id] = True
        
        thread = threading.Thread(
            target=self.process_rtsp_stream,
            args=(camera_id, rtsp_url, callback),
            kwargs=kwargs,
            daemon=True
        )
        thread.start()
        
        return True
    
    def stop_stream(self, camera_id):
        """Stop processing RTSP stream"""
        if camera_id in self.active_streams:
            del self.active_streams[camera_id]
            print(f"🛑 Stopping ANPR stream for camera {camera_id}")
            return True
        return False
    
    def stop_all_streams(self):
        """Stop all active streams"""
        camera_ids = list(self.active_streams.keys())
        for camera_id in camera_ids:
            self.stop_stream(camera_id)


# Global ANPR processor instance
anpr_processor = ANPRProcessor()
