"""
Face Recognition Service for Employee Attendance
Uses face_recognition library for face detection and recognition
"""
import os
import sys
import pickle
import numpy as np
import cv2
from typing import Optional, List, Tuple, Dict

# Try to add Anaconda site-packages to path (for dlib installed via conda)
try:
    import site
    anaconda_path = os.path.join(os.environ.get('USERPROFILE', ''), 'anaconda3', 'Lib', 'site-packages')
    if os.path.exists(anaconda_path) and anaconda_path not in sys.path:
        sys.path.insert(0, anaconda_path)
    # Also try Anaconda3 (capital A)
    anaconda_path2 = os.path.join(os.environ.get('USERPROFILE', ''), 'Anaconda3', 'Lib', 'site-packages')
    if os.path.exists(anaconda_path2) and anaconda_path2 not in sys.path:
        sys.path.insert(0, anaconda_path2)
except Exception:
    pass

# Try to import face_recognition, but make it optional
FACE_RECOGNITION_AVAILABLE = False
face_recognition = None

try:
    import face_recognition
    # Test if dlib actually works (conda dlib might not work with venv Python)
    try:
        import dlib
        # Try to use dlib to verify it works
        test_array = np.zeros((100, 100, 3), dtype=np.uint8)
        _ = dlib.rectangle(0, 0, 10, 10)  # Simple test
        FACE_RECOGNITION_AVAILABLE = True
    except (ImportError, AttributeError, ModuleNotFoundError) as e:
        # dlib is installed but not compatible with this Python
        FACE_RECOGNITION_AVAILABLE = False
        face_recognition = None
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    face_recognition = None

try:
    from PIL import Image
except ImportError:
    Image = None

class FaceRecognitionService:
    """Service for face recognition operations"""
    
    def __init__(self):
        if not FACE_RECOGNITION_AVAILABLE:
            # Check if it's an import issue or compatibility issue
            try:
                import dlib
                dlib_available = True
            except (ImportError, ModuleNotFoundError):
                dlib_available = False
            
            if dlib_available:
                error_msg = (
                    "dlib is installed but not compatible with this Python version. "
                    "The conda-installed dlib was built for a different Python. "
                    "Solutions:\n"
                    "1. Use conda environment: conda create -n fuelflux python=3.12 && conda install -c conda-forge dlib\n"
                    "2. Install Visual Studio Build Tools and run: pip install dlib\n"
                    "3. See SETUP_COMPLETE.md for detailed instructions"
                )
            else:
                error_msg = (
                    "face_recognition library is not installed. "
                    "Please install it using: pip install face-recognition dlib. "
                    "See INSTALL_FACE_RECOGNITION.md for detailed instructions."
                )
            raise ImportError(error_msg)
        self.tolerance = 0.6  # Lower = more strict (default is 0.6)
    
    def encode_face_from_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        Extract face encoding from an image file.
        Returns the face encoding if a face is found, None otherwise.
        """
        try:
            # Load image using face_recognition (handles various formats)
            image = face_recognition.load_image_file(image_path)
            
            # Find face locations
            face_locations = face_recognition.face_locations(image)
            
            if not face_locations:
                return None
            
            # Get face encodings (use first face if multiple)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                return None
            
            # Return the first face encoding
            return face_encodings[0]
            
        except Exception as e:
            print(f"Error encoding face from image {image_path}: {e}")
            return None
    
    def encode_face_from_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract face encoding from a video frame (numpy array).
        Returns the face encoding if a face is found, None otherwise.
        """
        try:
            # Convert BGR to RGB (face_recognition uses RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Find face locations
            face_locations = face_recognition.face_locations(rgb_frame)
            
            if not face_locations:
                return None
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            
            if not face_encodings:
                return None
            
            # Return the first face encoding
            return face_encodings[0]
            
        except Exception as e:
            print(f"Error encoding face from frame: {e}")
            return None
    
    def compare_faces(self, known_encoding: np.ndarray, face_encoding: np.ndarray) -> Tuple[bool, float]:
        """
        Compare a known face encoding with a detected face encoding.
        Returns (is_match, distance) tuple.
        """
        try:
            # Calculate face distance
            distance = face_recognition.face_distance([known_encoding], face_encoding)[0]
            
            # Check if faces match (within tolerance)
            is_match = distance <= self.tolerance
            
            # Convert distance to confidence (0-1 scale, higher is better)
            # Distance of 0 = perfect match, distance of 1.0 = very different
            confidence = max(0.0, 1.0 - distance)
            
            return is_match, confidence
            
        except Exception as e:
            print(f"Error comparing faces: {e}")
            return False, 0.0
    
    def find_employee_in_frame(
        self, 
        frame: np.ndarray, 
        employee_encodings: Dict[int, np.ndarray]
    ) -> Optional[Tuple[int, float, Tuple[int, int, int, int]]]:
        """
        Find an employee in a video frame.
        
        Args:
            frame: Video frame (BGR numpy array)
            employee_encodings: Dict mapping employee_id -> face_encoding
            
        Returns:
            Tuple of (employee_id, confidence, face_location) if found, None otherwise
            face_location is (top, right, bottom, left)
        """
        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Find all face locations in the frame
            face_locations = face_recognition.face_locations(rgb_frame)
            
            if not face_locations:
                return None
            
            # Get face encodings for all detected faces
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            
            if not face_encodings:
                return None
            
            # Compare each detected face with known employees
            best_match = None
            best_confidence = 0.0
            
            for face_encoding, face_location in zip(face_encodings, face_locations):
                for employee_id, known_encoding in employee_encodings.items():
                    is_match, confidence = self.compare_faces(known_encoding, face_encoding)
                    
                    if is_match and confidence > best_confidence:
                        best_match = (employee_id, confidence, face_location)
                        best_confidence = confidence
            
            return best_match
            
        except Exception as e:
            print(f"Error finding employee in frame: {e}")
            return None
    
    def serialize_encoding(self, encoding: np.ndarray) -> bytes:
        """Serialize face encoding to bytes for database storage"""
        return pickle.dumps(encoding)
    
    def deserialize_encoding(self, encoding_bytes: bytes) -> np.ndarray:
        """Deserialize face encoding from bytes"""
        return pickle.loads(encoding_bytes)
    
    def draw_face_box(
        self, 
        frame: np.ndarray, 
        face_location: Tuple[int, int, int, int], 
        name: str, 
        confidence: float
    ) -> np.ndarray:
        """
        Draw a bounding box and label on the frame for a detected face.
        
        Args:
            frame: Video frame (BGR)
            face_location: (top, right, bottom, left)
            name: Employee name to display
            confidence: Confidence score (0-1)
            
        Returns:
            Frame with bounding box and label drawn
        """
        top, right, bottom, left = face_location
        
        # Draw rectangle
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        
        # Draw label background
        label = f"{name} ({confidence:.2f})"
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        label_y = top - 10 if top - 10 > 10 else top + 20
        
        cv2.rectangle(
            frame, 
            (left, label_y - label_size[1] - 5), 
            (left + label_size[0], label_y + 5), 
            (0, 255, 0), 
            -1
        )
        
        # Draw label text
        cv2.putText(
            frame, 
            label, 
            (left, label_y), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.6, 
            (0, 0, 0), 
            2
        )
        
        return frame

