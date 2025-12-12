from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from extensions import db
from models import (
    PumpOwner, Pump, Tank, Pipeline, Hydrotest, HydrotestFile, 
    HydrotestNotification, ContractorMaster
)
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
import os
import uuid
import json
from sqlalchemy import or_, and_

hydrotesting_bp = Blueprint('hydrotesting', __name__)

UPLOAD_FOLDER = 'uploads/hydrotest_documents'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_current_pump():
    """Get current pump for logged-in pump owner"""
    if not isinstance(current_user, PumpOwner):
        return None
    
    pump_id = request.args.get('pump_id') or request.form.get('pump_id')
    if pump_id:
        pump = Pump.query.filter_by(id=pump_id, owner_id=current_user.id).first()
        return pump
    
    pumps = Pump.query.filter_by(owner_id=current_user.id).all()
    return pumps[0] if pumps else None


@hydrotesting_bp.route('/dashboard')
@login_required
def dashboard():
    """Main hydrotesting dashboard"""
    if not isinstance(current_user, PumpOwner):
        flash('Access denied. Pump owners only.', 'error')
        return redirect(url_for('pump_dashboard.dashboard'))
    
    pump = get_current_pump()
    if not pump:
        flash('No pump found. Please register a pump first.', 'error')
        return redirect(url_for('pump_dashboard.dashboard'))
    
    tanks = Tank.query.filter_by(pump_id=pump.id, is_active=True).all()
    pipelines = Pipeline.query.filter_by(pump_id=pump.id, is_active=True).all()
    
    all_hydrotests = Hydrotest.query.filter_by(pump_id=pump.id).order_by(Hydrotest.test_date.desc()).all()
    
    compliant_count = 0
    warning_count = 0
    due_soon_count = 0
    expired_count = 0
    
    for test in all_hydrotests:
        status = test.get_compliance_status()
        if status == 'compliant':
            compliant_count += 1
        elif status == 'warning':
            warning_count += 1
        elif status == 'due_soon':
            due_soon_count += 1
        elif status == 'expired':
            expired_count += 1
    
    expiring_soon = [t for t in all_hydrotests if t.get_compliance_status() in ['due_soon', 'warning']]
    overdue_tests = [t for t in all_hydrotests if t.get_compliance_status() == 'expired']
    
    return render_template('Pump-Owner/hydrotesting/dashboard.html',
                         pump=pump,
                         tanks=tanks,
                         pipelines=pipelines,
                         all_hydrotests=all_hydrotests[:10],
                         compliant_count=compliant_count,
                         warning_count=warning_count,
                         due_soon_count=due_soon_count,
                         expired_count=expired_count,
                         expiring_soon=expiring_soon[:5],
                         overdue_tests=overdue_tests[:5])


@hydrotesting_bp.route('/tanks')
@login_required
def tanks_list():
    """List all tanks"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    pump = get_current_pump()
    if not pump:
        return jsonify({'success': False, 'message': 'No pump found'}), 404
    
    tanks = Tank.query.filter_by(pump_id=pump.id, is_active=True).all()
    
    tanks_data = []
    for tank in tanks:
        latest_test = Hydrotest.query.filter_by(tank_id=tank.id).order_by(Hydrotest.test_date.desc()).first()
        
        tanks_data.append({
            'id': tank.id,
            'tank_id': tank.tank_id,
            'name': tank.name,
            'capacity': tank.capacity,
            'fuel_type': tank.fuel_type,
            'location': tank.location,
            'last_test_date': latest_test.test_date.strftime('%d/%m/%Y') if latest_test else 'Never',
            'next_due_date': latest_test.next_due_date.strftime('%d/%m/%Y') if latest_test else 'N/A',
            'status': latest_test.get_compliance_status() if latest_test else 'no_test',
            'result': latest_test.result if latest_test else 'N/A'
        })
    
    return render_template('Pump-Owner/hydrotesting/tanks.html', pump=pump, tanks=tanks_data)


@hydrotesting_bp.route('/pipelines')
@login_required
def pipelines_list():
    """List all pipelines"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    pump = get_current_pump()
    if not pump:
        return jsonify({'success': False, 'message': 'No pump found'}), 404
    
    pipelines = Pipeline.query.filter_by(pump_id=pump.id, is_active=True).all()
    
    pipelines_data = []
    for pipeline in pipelines:
        latest_test = Hydrotest.query.filter_by(pipeline_id=pipeline.id).order_by(Hydrotest.test_date.desc()).first()
        
        pipelines_data.append({
            'id': pipeline.id,
            'line_id': pipeline.line_id,
            'name': pipeline.name,
            'length': pipeline.length,
            'fuel_type': pipeline.fuel_type,
            'location': pipeline.location,
            'last_test_date': latest_test.test_date.strftime('%d/%m/%Y') if latest_test else 'Never',
            'next_due_date': latest_test.next_due_date.strftime('%d/%m/%Y') if latest_test else 'N/A',
            'status': latest_test.get_compliance_status() if latest_test else 'no_test',
            'result': latest_test.result if latest_test else 'N/A'
        })
    
    return render_template('Pump-Owner/hydrotesting/pipelines.html', pump=pump, pipelines=pipelines_data)


@hydrotesting_bp.route('/add_tank', methods=['GET', 'POST'])
@login_required
def add_tank():
    """Add new tank"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    pump = get_current_pump()
    if not pump:
        flash('No pump found', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    if request.method == 'POST':
        try:
            tank = Tank(
                pump_id=pump.id,
                owner_id=current_user.id,
                tank_id=request.form.get('tank_id'),
                name=request.form.get('name'),
                capacity=float(request.form.get('capacity')),
                fuel_type=request.form.get('fuel_type'),
                location=request.form.get('location'),
                installation_date=datetime.strptime(request.form.get('installation_date'), '%Y-%m-%d').date() if request.form.get('installation_date') else None
            )
            
            db.session.add(tank)
            db.session.commit()
            
            flash('Tank added successfully!', 'success')
            return redirect(url_for('hydrotesting.tanks_list', pump_id=pump.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding tank: {str(e)}', 'error')
    
    return render_template('Pump-Owner/hydrotesting/add_tank.html', pump=pump)


@hydrotesting_bp.route('/add_pipeline', methods=['GET', 'POST'])
@login_required
def add_pipeline():
    """Add new pipeline"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    pump = get_current_pump()
    if not pump:
        flash('No pump found', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    if request.method == 'POST':
        try:
            pipeline = Pipeline(
                pump_id=pump.id,
                owner_id=current_user.id,
                line_id=request.form.get('line_id'),
                name=request.form.get('name'),
                length=float(request.form.get('length')),
                diameter=float(request.form.get('diameter')) if request.form.get('diameter') else None,
                fuel_type=request.form.get('fuel_type'),
                location=request.form.get('location'),
                installation_date=datetime.strptime(request.form.get('installation_date'), '%Y-%m-%d').date() if request.form.get('installation_date') else None
            )
            
            db.session.add(pipeline)
            db.session.commit()
            
            flash('Pipeline added successfully!', 'success')
            return redirect(url_for('hydrotesting.pipelines_list', pump_id=pump.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding pipeline: {str(e)}', 'error')
    
    return render_template('Pump-Owner/hydrotesting/add_pipeline.html', pump=pump)


@hydrotesting_bp.route('/add_test', methods=['GET', 'POST'])
@login_required
def add_test():
    """Add new hydrotest entry"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    pump = get_current_pump()
    if not pump:
        flash('No pump found', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    if request.method == 'POST':
        try:
            test_type = request.form.get('test_type')
            test_date = datetime.strptime(request.form.get('test_date'), '%Y-%m-%d').date()
            validity_years = int(request.form.get('validity_years', 5))
            next_due_date = test_date + timedelta(days=validity_years * 365)
            
            tank_id = request.form.get('tank_id') if test_type in ['tank_hydrotest', 'sump_hydrotest'] else None
            pipeline_id = request.form.get('pipeline_id') if test_type in ['pipeline_hydrotest', 'vent_line_test'] else None
            
            hydrotest = Hydrotest(
                pump_id=pump.id,
                owner_id=current_user.id,
                tank_id=tank_id,
                pipeline_id=pipeline_id,
                test_type=test_type,
                test_date=test_date,
                peso_contractor_name=request.form.get('contractor_name'),
                competent_person_licence=request.form.get('licence_number'),
                test_pressure=float(request.form.get('test_pressure')),
                pressure_unit=request.form.get('pressure_unit', 'bar'),
                hold_duration=int(request.form.get('hold_duration')),
                result=request.form.get('result'),
                remarks=request.form.get('remarks'),
                next_due_date=next_due_date,
                validity_years=validity_years,
                peso_certificate_number=request.form.get('peso_certificate_number'),
                created_by=current_user.email
            )
            
            db.session.add(hydrotest)
            db.session.flush()
            
            uploaded_files = []
            file_types = ['certificate', 'gas_free', 'gauge_calibration', 'photo_before', 'photo_filling', 'photo_gauge', 'photo_after']
            
            for file_type in file_types:
                if file_type in request.files:
                    files = request.files.getlist(file_type)
                    for file in files:
                        if file and file.filename and allowed_file(file.filename):
                            original_filename = secure_filename(file.filename)
                            file_extension = original_filename.rsplit('.', 1)[1].lower()
                            stored_filename = f"{uuid.uuid4()}.{file_extension}"
                            file_path = os.path.join(UPLOAD_FOLDER, stored_filename)
                            
                            file.save(file_path)
                            
                            hydrotest_file = HydrotestFile(
                                hydrotest_id=hydrotest.id,
                                file_type=file_type,
                                original_filename=original_filename,
                                stored_filename=stored_filename,
                                file_url=file_path,
                                file_size=os.path.getsize(file_path),
                                uploaded_by=current_user.email
                            )
                            
                            db.session.add(hydrotest_file)
                            uploaded_files.append(file_type)
            
            create_notifications_for_hydrotest(hydrotest)
            
            db.session.commit()
            
            flash(f'Hydrotest added successfully! {len(uploaded_files)} files uploaded.', 'success')
            return redirect(url_for('hydrotesting.view_test', test_id=hydrotest.id, pump_id=pump.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding hydrotest: {str(e)}', 'error')
    
    tanks = Tank.query.filter_by(pump_id=pump.id, is_active=True).all()
    pipelines = Pipeline.query.filter_by(pump_id=pump.id, is_active=True).all()
    contractors = ContractorMaster.query.filter_by(is_active=True).all()
    
    return render_template('Pump-Owner/hydrotesting/add_test.html', 
                         pump=pump, 
                         tanks=tanks, 
                         pipelines=pipelines,
                         contractors=contractors)


@hydrotesting_bp.route('/view_test/<int:test_id>')
@login_required
def view_test(test_id):
    """View hydrotest details"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    hydrotest = Hydrotest.query.filter_by(id=test_id, owner_id=current_user.id).first()
    if not hydrotest:
        flash('Hydrotest not found', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    files = HydrotestFile.query.filter_by(hydrotest_id=test_id).all()
    
    files_by_type = {}
    for file in files:
        if file.file_type not in files_by_type:
            files_by_type[file.file_type] = []
        files_by_type[file.file_type].append(file)
    
    return render_template('Pump-Owner/hydrotesting/view_test.html', 
                         hydrotest=hydrotest, 
                         files_by_type=files_by_type,
                         pump=hydrotest.pump)


@hydrotesting_bp.route('/history')
@login_required
def history():
    """View all hydrotest history"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    pump = get_current_pump()
    if not pump:
        flash('No pump found', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    equipment_type = request.args.get('equipment_type', 'all')
    equipment_id = request.args.get('equipment_id')
    
    query = Hydrotest.query.filter_by(pump_id=pump.id)
    
    if equipment_type == 'tank' and equipment_id:
        query = query.filter_by(tank_id=equipment_id)
    elif equipment_type == 'pipeline' and equipment_id:
        query = query.filter_by(pipeline_id=equipment_id)
    
    hydrotests = query.order_by(Hydrotest.test_date.desc()).all()
    
    tanks = Tank.query.filter_by(pump_id=pump.id, is_active=True).all()
    pipelines = Pipeline.query.filter_by(pump_id=pump.id, is_active=True).all()
    
    return render_template('Pump-Owner/hydrotesting/history.html', 
                         pump=pump, 
                         hydrotests=hydrotests,
                         tanks=tanks,
                         pipelines=pipelines,
                         selected_type=equipment_type,
                         selected_id=equipment_id)


@hydrotesting_bp.route('/contractors')
@login_required
def contractors():
    """View contractor master data"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    pump = get_current_pump()
    if not pump:
        flash('No pump found', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    contractors = ContractorMaster.query.filter_by(is_active=True).all()
    
    return render_template('Pump-Owner/hydrotesting/contractors.html', 
                         pump=pump, 
                         contractors=contractors)


@hydrotesting_bp.route('/download_file/<int:file_id>')
@login_required
def download_file(file_id):
    """Download hydrotest file"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    file = HydrotestFile.query.get(file_id)
    if not file:
        flash('File not found', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    hydrotest = Hydrotest.query.get(file.hydrotest_id)
    if hydrotest.owner_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    return send_file(file.file_url, as_attachment=True, download_name=file.original_filename)


@hydrotesting_bp.route('/compliance_report')
@login_required
def compliance_report():
    """Generate compliance report"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    pump = get_current_pump()
    if not pump:
        flash('No pump found', 'error')
        return redirect(url_for('hydrotesting.dashboard'))
    
    tanks = Tank.query.filter_by(pump_id=pump.id, is_active=True).all()
    pipelines = Pipeline.query.filter_by(pump_id=pump.id, is_active=True).all()
    
    compliance_data = []
    
    for tank in tanks:
        latest_test = Hydrotest.query.filter_by(tank_id=tank.id).order_by(Hydrotest.test_date.desc()).first()
        compliance_data.append({
            'type': 'Tank',
            'id': tank.tank_id,
            'name': tank.name,
            'last_test': latest_test.test_date if latest_test else None,
            'next_due': latest_test.next_due_date if latest_test else None,
            'status': latest_test.get_compliance_status() if latest_test else 'no_test',
            'days_until_expiry': latest_test.get_days_until_expiry() if latest_test else None,
            'peso_approved': latest_test.peso_approved if latest_test else False
        })
    
    for pipeline in pipelines:
        latest_test = Hydrotest.query.filter_by(pipeline_id=pipeline.id).order_by(Hydrotest.test_date.desc()).first()
        compliance_data.append({
            'type': 'Pipeline',
            'id': pipeline.line_id,
            'name': pipeline.name,
            'last_test': latest_test.test_date if latest_test else None,
            'next_due': latest_test.next_due_date if latest_test else None,
            'status': latest_test.get_compliance_status() if latest_test else 'no_test',
            'days_until_expiry': latest_test.get_days_until_expiry() if latest_test else None,
            'peso_approved': latest_test.peso_approved if latest_test else False
        })
    
    return render_template('Pump-Owner/hydrotesting/compliance_report.html', 
                         pump=pump, 
                         compliance_data=compliance_data)


def create_notifications_for_hydrotest(hydrotest):
    """Create notification reminders for hydrotest expiry"""
    notification_days = [90, 30, 0]
    
    for days in notification_days:
        notification_date = hydrotest.next_due_date - timedelta(days=days)
        
        if notification_date >= date.today():
            notification = HydrotestNotification(
                hydrotest_id=hydrotest.id,
                owner_id=hydrotest.owner_id,
                notification_type='expiry_reminder',
                notification_date=notification_date,
                days_before_expiry=days,
                message=f"Hydrotest for {hydrotest.test_type} will expire in {days} days. Please schedule testing."
            )
            db.session.add(notification)


@hydrotesting_bp.route('/api/check_notifications')
@login_required
def check_notifications():
    """API endpoint to check pending notifications"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    today = date.today()
    
    pending_notifications = HydrotestNotification.query.filter(
        HydrotestNotification.owner_id == current_user.id,
        HydrotestNotification.notification_date <= today,
        HydrotestNotification.sent == False
    ).all()
    
    notifications_data = []
    for notif in pending_notifications:
        hydrotest = Hydrotest.query.get(notif.hydrotest_id)
        notifications_data.append({
            'id': notif.id,
            'message': notif.message,
            'days_before_expiry': notif.days_before_expiry,
            'test_type': hydrotest.test_type if hydrotest else 'Unknown',
            'next_due_date': hydrotest.next_due_date.strftime('%d/%m/%Y') if hydrotest else 'N/A'
        })
    
    return jsonify({
        'success': True,
        'notifications': notifications_data,
        'count': len(notifications_data)
    })


@hydrotesting_bp.route('/api/mark_notification_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    if not isinstance(current_user, PumpOwner):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    notification = HydrotestNotification.query.filter_by(
        id=notification_id, 
        owner_id=current_user.id
    ).first()
    
    if not notification:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404
    
    notification.sent = True
    notification.sent_at = datetime.now()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Notification marked as read'})


# ==================== ANPR Vehicle Compliance Routes ====================

@hydrotesting_bp.route('/anpr/dashboard')
@login_required
def anpr_dashboard():
    """ANPR Vehicle Compliance Dashboard"""
    pump = get_current_pump()
    
    from models import ANPRCamera, VehicleCompliance, VehicleEntryLog
    from anpr_compliance_checker import compliance_checker
    
    # Get cameras
    cameras = ANPRCamera.query.filter_by(pump_id=pump.id).all()
    
    # Get statistics
    stats = compliance_checker.get_entry_statistics(pump.id, days=7)
    
    # Get recent detections
    recent_detections = compliance_checker.get_recent_detections(pump.id, limit=20)
    
    # Get vehicle compliance summary
    total_vehicles = VehicleCompliance.query.filter_by(pump_id=pump.id).count()
    compliant_vehicles = VehicleCompliance.query.filter_by(
        pump_id=pump.id, 
        is_compliant=True
    ).count()
    
    return render_template(
        'Pump-Owner/hydrotesting/anpr_dashboard.html',
        pump=pump,
        cameras=cameras,
        stats=stats,
        recent_detections=recent_detections,
        total_vehicles=total_vehicles,
        compliant_vehicles=compliant_vehicles
    )


@hydrotesting_bp.route('/anpr/vehicles')
@login_required
def anpr_vehicles():
    """Manage vehicle compliance database"""
    pump = get_current_pump()
    
    from models import VehicleCompliance
    
    vehicles = VehicleCompliance.query.filter_by(pump_id=pump.id).all()
    
    # Update compliance status for all vehicles
    for vehicle in vehicles:
        vehicle.get_compliance_status()
    
    db.session.commit()
    
    return render_template(
        'Pump-Owner/hydrotesting/anpr_vehicles.html',
        pump=pump,
        vehicles=vehicles
    )


@hydrotesting_bp.route('/anpr/add_vehicle', methods=['GET', 'POST'])
@login_required
def anpr_add_vehicle():
    """Add vehicle to compliance database"""
    pump = get_current_pump()
    
    if request.method == 'POST':
        from models import VehicleCompliance
        
        try:
            vehicle = VehicleCompliance(
                pump_id=pump.id,
                owner_id=current_user.id,
                vehicle_number=request.form.get('vehicle_number').upper(),
                vehicle_type=request.form.get('vehicle_type'),
                vehicle_make=request.form.get('vehicle_make'),
                vehicle_model=request.form.get('vehicle_model'),
                hydrotest_expiry_date=datetime.strptime(
                    request.form.get('hydrotest_expiry_date'), '%Y-%m-%d'
                ).date(),
                last_hydrotest_date=datetime.strptime(
                    request.form.get('last_hydrotest_date'), '%Y-%m-%d'
                ).date() if request.form.get('last_hydrotest_date') else None,
                hydrotest_certificate_number=request.form.get('hydrotest_certificate_number'),
                owner_name=request.form.get('owner_name'),
                owner_contact=request.form.get('owner_contact'),
                remarks=request.form.get('remarks')
            )
            
            # Handle certificate upload
            if 'certificate_file' in request.files:
                file = request.files['certificate_file']
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                    file.save(filepath)
                    vehicle.hydrotest_certificate_path = filepath
            
            vehicle.get_compliance_status()
            
            db.session.add(vehicle)
            db.session.commit()
            
            flash('Vehicle added successfully', 'success')
            return redirect(url_for('hydrotesting.anpr_vehicles', pump_id=pump.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding vehicle: {str(e)}', 'error')
    
    return render_template(
        'Pump-Owner/hydrotesting/anpr_add_vehicle.html',
        pump=pump
    )


@hydrotesting_bp.route('/anpr/cameras')
@login_required
def anpr_cameras():
    """Manage ANPR cameras"""
    pump = get_current_pump()
    
    from models import ANPRCamera
    
    cameras = ANPRCamera.query.filter_by(pump_id=pump.id).all()
    
    return render_template(
        'Pump-Owner/hydrotesting/anpr_cameras.html',
        pump=pump,
        cameras=cameras
    )


@hydrotesting_bp.route('/anpr/add_camera', methods=['GET', 'POST'])
@login_required
def anpr_add_camera():
    """Add ANPR camera"""
    pump = get_current_pump()
    
    if request.method == 'POST':
        from models import ANPRCamera
        
        try:
            camera = ANPRCamera(
                pump_id=pump.id,
                owner_id=current_user.id,
                camera_name=request.form.get('camera_name'),
                camera_location=request.form.get('camera_location'),
                rtsp_url=request.form.get('rtsp_url'),
                is_active=request.form.get('is_active') == 'on',
                detection_enabled=request.form.get('detection_enabled') == 'on',
                gate_control_enabled=request.form.get('gate_control_enabled') == 'on',
                confidence_threshold=float(request.form.get('confidence_threshold', 0.7)),
                detection_interval_seconds=int(request.form.get('detection_interval_seconds', 2)),
                gate_ip_address=request.form.get('gate_ip_address'),
                gate_control_type=request.form.get('gate_control_type'),
                auto_close_delay_seconds=int(request.form.get('auto_close_delay_seconds', 10))
            )
            
            db.session.add(camera)
            db.session.commit()
            
            flash('Camera added successfully', 'success')
            return redirect(url_for('hydrotesting.anpr_cameras', pump_id=pump.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding camera: {str(e)}', 'error')
    
    return render_template(
        'Pump-Owner/hydrotesting/anpr_add_camera.html',
        pump=pump
    )


@hydrotesting_bp.route('/anpr/start_camera/<int:camera_id>')
@login_required
def anpr_start_camera(camera_id):
    """Start ANPR detection for a camera"""
    pump = get_current_pump()
    
    from models import ANPRCamera
    from anpr_processor import anpr_processor
    from anpr_compliance_checker import compliance_checker
    
    camera = ANPRCamera.query.get_or_404(camera_id)
    
    if camera.pump_id != pump.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('hydrotesting.anpr_cameras', pump_id=pump.id))
    
    def detection_callback(detection_data):
        """Handle detected vehicle"""
        with current_app.app_context():
            # Check compliance
            compliance_result = compliance_checker.check_vehicle_compliance(
                detection_data['vehicle_number'],
                pump.id
            )
            
            # Log entry
            compliance_checker.log_vehicle_entry(detection_data, compliance_result, pump.id)
            
            # Trigger gate control
            if camera.gate_control_enabled:
                compliance_checker.trigger_gate_control(
                    compliance_result['gate_action'],
                    camera
                )
            
            # Send alert if needed
            if compliance_result['alert_level'] in ['warning', 'critical']:
                compliance_checker.send_alert_notification(
                    detection_data['vehicle_number'],
                    compliance_result,
                    current_user.email
                )
            
            print(f"✅ Processed: {detection_data['vehicle_number']} - {compliance_result['compliance_status']}")
    
    success = anpr_processor.start_stream(
        camera_id=camera.id,
        rtsp_url=camera.rtsp_url,
        callback=detection_callback,
        detection_interval=camera.detection_interval_seconds,
        confidence_threshold=camera.confidence_threshold
    )
    
    if success:
        camera.last_active_at = datetime.now()
        db.session.commit()
        flash(f'ANPR detection started for {camera.camera_name}', 'success')
    else:
        flash(f'Failed to start ANPR detection', 'error')
    
    return redirect(url_for('hydrotesting.anpr_cameras', pump_id=pump.id))


@hydrotesting_bp.route('/anpr/stop_camera/<int:camera_id>')
@login_required
def anpr_stop_camera(camera_id):
    """Stop ANPR detection for a camera"""
    pump = get_current_pump()
    
    from models import ANPRCamera
    from anpr_processor import anpr_processor
    
    camera = ANPRCamera.query.get_or_404(camera_id)
    
    if camera.pump_id != pump.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('hydrotesting.anpr_cameras', pump_id=pump.id))
    
    success = anpr_processor.stop_stream(camera.id)
    
    if success:
        flash(f'ANPR detection stopped for {camera.camera_name}', 'success')
    else:
        flash(f'Camera was not running', 'warning')
    
    return redirect(url_for('hydrotesting.anpr_cameras', pump_id=pump.id))


@hydrotesting_bp.route('/anpr/entry_logs')
@login_required
def anpr_entry_logs():
    """View vehicle entry logs"""
    pump = get_current_pump()
    
    from models import VehicleEntryLog
    
    logs = VehicleEntryLog.query.filter_by(
        pump_id=pump.id
    ).order_by(VehicleEntryLog.detected_at.desc()).limit(100).all()
    
    return render_template(
        'Pump-Owner/hydrotesting/anpr_entry_logs.html',
        pump=pump,
        logs=logs
    )


@hydrotesting_bp.route('/anpr/api/live_feed/<int:camera_id>')
@login_required
def anpr_live_feed(camera_id):
    """Get live detection feed (SSE)"""
    from models import ANPRCamera, VehicleEntryLog
    
    pump = get_current_pump()
    camera = ANPRCamera.query.get_or_404(camera_id)
    
    if camera.pump_id != pump.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get latest detections
    latest = VehicleEntryLog.query.filter_by(
        pump_id=pump.id
    ).order_by(VehicleEntryLog.detected_at.desc()).limit(5).all()
    
    detections = []
    for log in latest:
        detections.append({
            'vehicle_number': log.vehicle_number,
            'detected_at': log.detected_at.strftime('%H:%M:%S'),
            'compliance_status': log.compliance_status,
            'is_allowed_entry': log.is_allowed_entry,
            'confidence': log.detection_confidence
        })
    
    return jsonify({'detections': detections})
