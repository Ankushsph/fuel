"""
Employee Management Routes
Handles employee registration, listing, and management
"""
import os
import uuid
from datetime import datetime, date
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import Pump, PumpOwner, Employee, Attendance

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")

# Lazy initialization of face recognition service
_face_service = None

def get_face_service():
    """Get or initialize face recognition service"""
    global _face_service
    if _face_service is None:
        try:
            from lib.face_recognition_service import FaceRecognitionService
            _face_service = FaceRecognitionService()
        except ImportError as e:
            error_msg = (
                "Face recognition library is not installed. "
                "Please install it using: pip install face-recognition dlib. "
                "See INSTALL_FACE_RECOGNITION.md for detailed instructions."
            )
            current_app.logger.error(error_msg)
            raise ImportError(error_msg) from e
    return _face_service

# Upload directory for employee photos
EMPLOYEE_PHOTO_DIR = os.path.join("uploads", "employee_photos")


def _ensure_upload_dir():
    """Ensure employee photo upload directory exists"""
    os.makedirs(EMPLOYEE_PHOTO_DIR, exist_ok=True)
    return EMPLOYEE_PHOTO_DIR


def _pump_with_access(owner: PumpOwner, pump_id: int):
    """Verify pump belongs to owner"""
    return Pump.query.filter_by(id=pump_id, owner_id=owner.id).first()


@employee_bp.route("/<int:pump_id>/add", methods=["POST"])
@login_required
def add_employee(pump_id):
    """Add a new employee to a pump"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    try:
        # Get form data
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        designation = request.form.get("designation", "").strip()
        employee_id = request.form.get("employee_id", "").strip()
        
        if not name:
            return jsonify({"success": False, "message": "Employee name is required"}), 400
        
        # Get photo file
        if "photo" not in request.files:
            return jsonify({"success": False, "message": "Employee photo is required"}), 400
        
        photo_file = request.files["photo"]
        if not photo_file or not photo_file.filename:
            return jsonify({"success": False, "message": "Invalid photo file. Please select an image file."}), 400
        
        # Validate file extension
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        file_ext = os.path.splitext(photo_file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({"success": False, "message": f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"}), 400
        
        # Save photo
        upload_dir = _ensure_upload_dir()
        safe_filename = secure_filename(photo_file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
        photo_path = os.path.join(upload_dir, unique_filename)
        photo_file.save(photo_path)
        
        # Extract face encoding (optional - allow employee without face recognition)
        encoding_bytes = None
        try:
            face_service = get_face_service()
            face_encoding = face_service.encode_face_from_image(photo_path)
            
            if face_encoding is None:
                # Warn but don't fail - allow employee without face encoding
                current_app.logger.warning(f"No face detected in photo for employee {name}, but allowing registration")
            else:
                # Serialize face encoding
                encoding_bytes = face_service.serialize_encoding(face_encoding)
        except ImportError as e:
            # Face recognition not available - allow employee without encoding
            current_app.logger.warning(f"Face recognition not available: {e}. Employee will be added without face encoding.")
        except Exception as e:
            # Other face recognition errors - log but continue
            current_app.logger.warning(f"Face encoding failed for employee {name}: {e}. Employee will be added without face encoding.")
        
        # Create employee record
        employee = Employee(
            pump_id=pump_id,
            owner_id=owner.id,
            name=name,
            phone=phone if phone else None,
            email=email if email else None,
            designation=designation if designation else None,
            employee_id=employee_id if employee_id else None,
            photo_filename=unique_filename,
            face_encoding=encoding_bytes,
            is_active=True
        )
        
        db.session.add(employee)
        db.session.commit()
        
        current_app.logger.info(f"Employee {name} added to pump {pump_id} by owner {owner.id}")
        
        return jsonify({
            "success": True,
            "message": f"Employee '{name}' added successfully!",
            "employee": {
                "id": employee.id,
                "name": employee.name,
                "phone": employee.phone,
                "email": employee.email,
                "designation": employee.designation,
                "employee_id": employee.employee_id,
                "photo_filename": employee.photo_filename
            }
        })
        
    except Exception as e:
        current_app.logger.exception("Error adding employee")
        db.session.rollback()
        # Clean up uploaded photo if it exists
        try:
            if 'photo_path' in locals() and os.path.exists(photo_path):
                os.remove(photo_path)
        except:
            pass
        # Provide more detailed error message
        error_msg = str(e)
        if "face_recognition" in error_msg.lower() or "dlib" in error_msg.lower():
            error_msg = "Face recognition is not available. Please ensure you're running the app with the conda environment. Employee can still be added manually for attendance tracking."
        return jsonify({"success": False, "message": f"Error adding employee: {error_msg}"}), 500


@employee_bp.route("/<int:pump_id>/list", methods=["GET"])
@login_required
def list_employees(pump_id):
    """Get list of all employees for a pump"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    try:
        employees = Employee.query.filter_by(
            pump_id=pump_id, 
            owner_id=owner.id,
            is_active=True
        ).order_by(Employee.created_at.desc()).all()
        
        employee_list = []
        for emp in employees:
            employee_list.append({
                "id": emp.id,
                "name": emp.name,
                "phone": emp.phone,
                "email": emp.email,
                "designation": emp.designation,
                "employee_id": emp.employee_id,
                "photo_filename": emp.photo_filename,
                "photo_url": f"/uploads/employee_photos/{emp.photo_filename}",
                "created_at": emp.created_at.strftime("%Y-%m-%d") if emp.created_at else None
            })
        
        return jsonify({
            "success": True,
            "employees": employee_list,
            "count": len(employee_list)
        })
        
    except Exception as e:
        current_app.logger.exception("Error listing employees")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@employee_bp.route("/<int:employee_id>/delete", methods=["DELETE"])
@login_required
def delete_employee(employee_id):
    """Delete (deactivate) an employee"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    employee = Employee.query.filter_by(id=employee_id, owner_id=owner.id).first()
    if not employee:
        return jsonify({"success": False, "message": "Employee not found"}), 404
    
    try:
        # Soft delete - mark as inactive
        employee.is_active = False
        db.session.commit()
        
        current_app.logger.info(f"Employee {employee_id} deactivated by owner {owner.id}")
        
        return jsonify({
            "success": True,
            "message": f"Employee '{employee.name}' removed successfully"
        })
        
    except Exception as e:
        current_app.logger.exception("Error deleting employee")
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@employee_bp.route("/<int:pump_id>/encodings", methods=["GET"])
@login_required
def get_employee_encodings(pump_id):
    """Get face encodings for all active employees of a pump (for attendance detection)"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    try:
        employees = Employee.query.filter_by(
            pump_id=pump_id,
            owner_id=owner.id,
            is_active=True
        ).all()
        
        encodings_dict = {}
        employee_info = {}
        
        face_service = get_face_service()
        for emp in employees:
            if emp.face_encoding:
                try:
                    encoding = face_service.deserialize_encoding(emp.face_encoding)
                    encodings_dict[emp.id] = encoding
                    employee_info[emp.id] = {
                        "name": emp.name,
                        "designation": emp.designation
                    }
                except Exception as e:
                    current_app.logger.warning(f"Failed to deserialize encoding for employee {emp.id}: {e}")
                    continue
        
        # Return as JSON (we'll need to handle numpy arrays specially)
        # For now, we'll return employee IDs and fetch encodings server-side
        return jsonify({
            "success": True,
            "employee_ids": list(encodings_dict.keys()),
            "employee_info": employee_info,
            "count": len(encodings_dict)
        })
        
    except Exception as e:
        current_app.logger.exception("Error getting employee encodings")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@employee_bp.route("/<int:pump_id>/attendance/mark", methods=["POST"])
@login_required
def mark_attendance(pump_id):
    """Mark attendance for an employee"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    try:
        data = request.get_json()
        employee_id = data.get("employee_id")
        detection_method = data.get("detection_method", "face_recognition")
        confidence = data.get("confidence")
        check_type = data.get("check_type", "check_in")  # check_in or check_out
        
        if not employee_id:
            return jsonify({"success": False, "message": "Employee ID is required"}), 400
        
        employee = Employee.query.filter_by(
            id=employee_id,
            pump_id=pump_id,
            owner_id=owner.id,
            is_active=True
        ).first()
        
        if not employee:
            return jsonify({"success": False, "message": "Employee not found"}), 404
        
        today = date.today()
        now = datetime.now()
        
        # Check if attendance record exists for today
        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            attendance_date=today
        ).first()
        
        if check_type == "check_in":
            if attendance:
                # Update existing record
                if not attendance.check_in_time:
                    attendance.check_in_time = now
                    attendance.status = "present"
                    attendance.detection_method = detection_method
                    attendance.detected_confidence = confidence
            else:
                # Create new attendance record
                attendance = Attendance(
                    employee_id=employee_id,
                    pump_id=pump_id,
                    attendance_date=today,
                    check_in_time=now,
                    status="present",
                    detection_method=detection_method,
                    detected_confidence=confidence
                )
                db.session.add(attendance)
        
        elif check_type == "check_out":
            if attendance:
                attendance.check_out_time = now
                # Calculate total hours if both times exist
                if attendance.check_in_time:
                    delta = now - attendance.check_in_time
                    attendance.total_hours = delta.total_seconds() / 3600.0
            else:
                # Create record with check-out only (unusual but possible)
                attendance = Attendance(
                    employee_id=employee_id,
                    pump_id=pump_id,
                    attendance_date=today,
                    check_out_time=now,
                    status="present",
                    detection_method=detection_method
                )
                db.session.add(attendance)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Attendance {check_type} marked successfully for {employee.name}",
            "attendance": {
                "employee_id": employee_id,
                "employee_name": employee.name,
                "date": today.isoformat(),
                "check_in_time": attendance.check_in_time.isoformat() if attendance.check_in_time else None,
                "check_out_time": attendance.check_out_time.isoformat() if attendance.check_out_time else None,
                "status": attendance.status
            }
        })
        
    except Exception as e:
        current_app.logger.exception("Error marking attendance")
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@employee_bp.route("/photos/<filename>")
def serve_employee_photo(filename):
    """Serve employee photos (public access for image display)"""
    from flask import send_from_directory
    import os
    photo_path = os.path.join("uploads", "employee_photos")
    # Security: Only allow image files
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        from flask import abort
        abort(404)
    return send_from_directory(photo_path, filename)


@employee_bp.route("/<int:pump_id>/management")
@login_required
def employee_management(pump_id):
    """Employee management page"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        from flask import redirect, url_for, flash
        flash("Access denied.", "error")
        return redirect(url_for("auth.index"))
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        from flask import redirect, url_for, flash
        flash("Pump not found.", "error")
        return redirect(url_for("pump_dashboard.dashboard"))
    
    from flask import render_template
    return render_template(
        "/Pump-Owner/employee_management.html",
        pump=pump,
        user=owner
    )


@employee_bp.route("/<int:pump_id>/attendance/list", methods=["GET"])
@login_required
def list_attendance(pump_id):
    """Get attendance records for a pump"""
    owner = current_user
    if not isinstance(owner, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    pump = _pump_with_access(owner, pump_id)
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404
    
    try:
        # Get query parameters
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        employee_id = request.args.get("employee_id")
        
        query = Attendance.query.filter_by(pump_id=pump_id)
        
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        
        if start_date:
            query = query.filter(Attendance.attendance_date >= datetime.strptime(start_date, "%Y-%m-%d").date())
        
        if end_date:
            query = query.filter(Attendance.attendance_date <= datetime.strptime(end_date, "%Y-%m-%d").date())
        
        records = query.order_by(Attendance.attendance_date.desc(), Attendance.check_in_time.desc()).limit(100).all()
        
        attendance_list = []
        for record in records:
            employee = Employee.query.get(record.employee_id)
            attendance_list.append({
                "id": record.id,
                "employee_id": record.employee_id,
                "employee_name": employee.name if employee else "Unknown",
                "date": record.attendance_date.isoformat(),
                "check_in_time": record.check_in_time.isoformat() if record.check_in_time else None,
                "check_out_time": record.check_out_time.isoformat() if record.check_out_time else None,
                "status": record.status,
                "total_hours": record.total_hours,
                "detection_method": record.detection_method,
                "confidence": record.detected_confidence
            })
        
        return jsonify({
            "success": True,
            "attendance": attendance_list,
            "count": len(attendance_list)
        })
        
    except Exception as e:
        current_app.logger.exception("Error listing attendance")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

