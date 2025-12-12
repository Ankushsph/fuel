"""
ANPR Compliance Checker
Checks vehicle compliance against hydrotest database
"""

from datetime import datetime, date
from models import VehicleCompliance, VehicleEntryLog, ANPRCamera, db
from extensions import mail
from flask_mail import Message

class ComplianceChecker:
    """Check vehicle compliance and trigger gate control"""
    
    @staticmethod
    def check_vehicle_compliance(vehicle_number, pump_id):
        """
        Check if vehicle is compliant with hydrotest requirements
        
        Returns:
            dict with compliance status and details
        """
        vehicle = VehicleCompliance.query.filter_by(
            vehicle_number=vehicle_number,
            pump_id=pump_id
        ).first()
        
        if not vehicle:
            return {
                'found': False,
                'vehicle_number': vehicle_number,
                'compliance_status': 'unknown',
                'is_allowed_entry': False,
                'gate_action': 'close',
                'alert_level': 'warning',
                'message': f'Vehicle {vehicle_number} not found in database',
                'display_message': f'❌ VEHICLE NOT REGISTERED\n\n{vehicle_number}\n\nPlease register vehicle before entry',
                'color': 'orange'
            }
        
        # Update compliance status
        status = vehicle.get_compliance_status()
        days_until_expiry = vehicle.get_days_until_expiry()
        
        # Check if blacklisted
        if vehicle.is_blacklisted:
            return {
                'found': True,
                'vehicle_number': vehicle_number,
                'vehicle_type': vehicle.vehicle_type,
                'compliance_status': 'blacklisted',
                'is_allowed_entry': False,
                'gate_action': 'close',
                'alert_level': 'critical',
                'message': f'Vehicle {vehicle_number} is BLACKLISTED',
                'display_message': f'🚫 VEHICLE BLACKLISTED\n\n{vehicle_number}\n\nReason: {vehicle.blacklist_reason or "Access denied"}',
                'blacklist_reason': vehicle.blacklist_reason,
                'color': 'red'
            }
        
        # Check if hydrotest expired
        if status == 'expired':
            return {
                'found': True,
                'vehicle_number': vehicle_number,
                'vehicle_type': vehicle.vehicle_type,
                'compliance_status': 'expired',
                'is_allowed_entry': False,
                'gate_action': 'close',
                'alert_level': 'critical',
                'message': f'Hydrotest EXPIRED for {vehicle_number}',
                'display_message': f'❌ HYDROTEST EXPIRED\n\n{vehicle_number}\n\nExpired on: {vehicle.hydrotest_expiry_date.strftime("%d-%b-%Y")}\nDays overdue: {abs(days_until_expiry)}',
                'hydrotest_expiry_date': vehicle.hydrotest_expiry_date,
                'days_overdue': abs(days_until_expiry),
                'color': 'red'
            }
        
        # Check if expiring soon
        if status == 'expiring_soon':
            return {
                'found': True,
                'vehicle_number': vehicle_number,
                'vehicle_type': vehicle.vehicle_type,
                'compliance_status': 'expiring_soon',
                'is_allowed_entry': True,
                'gate_action': 'open',
                'alert_level': 'warning',
                'message': f'Hydrotest expiring soon for {vehicle_number}',
                'display_message': f'⚠️ HYDROTEST EXPIRING SOON\n\n{vehicle_number}\n\nValid till: {vehicle.hydrotest_expiry_date.strftime("%d-%b-%Y")}\nDays remaining: {days_until_expiry}\n\n✓ Entry Allowed',
                'hydrotest_expiry_date': vehicle.hydrotest_expiry_date,
                'days_until_expiry': days_until_expiry,
                'color': 'yellow'
            }
        
        # Compliant
        return {
            'found': True,
            'vehicle_number': vehicle_number,
            'vehicle_type': vehicle.vehicle_type,
            'compliance_status': 'compliant',
            'is_allowed_entry': True,
            'gate_action': 'open',
            'alert_level': 'normal',
            'message': f'Vehicle {vehicle_number} is COMPLIANT',
            'display_message': f'✔ COMPLIANT\n\n{vehicle_number}\n\nHydrotest valid till: {vehicle.hydrotest_expiry_date.strftime("%d-%b-%Y")}\nDays remaining: {days_until_expiry}\n\n✓ Entry Allowed',
            'hydrotest_expiry_date': vehicle.hydrotest_expiry_date,
            'days_until_expiry': days_until_expiry,
            'color': 'green'
        }
    
    @staticmethod
    def log_vehicle_entry(detection_data, compliance_result, pump_id):
        """Log vehicle entry with compliance check result"""
        try:
            # Find vehicle compliance record
            vehicle_compliance = VehicleCompliance.query.filter_by(
                vehicle_number=detection_data['vehicle_number'],
                pump_id=pump_id
            ).first()
            
            # Create entry log
            entry_log = VehicleEntryLog(
                pump_id=pump_id,
                vehicle_compliance_id=vehicle_compliance.id if vehicle_compliance else None,
                vehicle_number=detection_data['vehicle_number'],
                detected_at=detection_data['detected_at'],
                detection_confidence=detection_data['confidence'],
                image_path=detection_data.get('frame_path'),
                plate_image_path=detection_data.get('plate_path'),
                compliance_status=compliance_result['compliance_status'],
                is_allowed_entry=compliance_result['is_allowed_entry'],
                gate_action=compliance_result['gate_action'],
                alert_triggered=compliance_result['alert_level'] in ['warning', 'critical'],
                alert_message=compliance_result['message']
            )
            
            db.session.add(entry_log)
            db.session.commit()
            
            return entry_log
            
        except Exception as e:
            print(f"Error logging vehicle entry: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def trigger_gate_control(gate_action, camera):
        """Trigger gate control based on compliance result"""
        if not camera.gate_control_enabled:
            return {'success': False, 'message': 'Gate control not enabled'}
        
        try:
            # This is a placeholder for actual gate control integration
            # You would integrate with your specific gate controller here
            
            if camera.gate_control_type == 'http':
                # HTTP-based gate control
                import requests
                if gate_action == 'open':
                    url = f"http://{camera.gate_ip_address}/open"
                else:
                    url = f"http://{camera.gate_ip_address}/close"
                
                # response = requests.get(url, timeout=5)
                # return {'success': response.ok, 'message': 'Gate control triggered'}
                
            elif camera.gate_control_type == 'relay':
                # GPIO relay control (for Raspberry Pi)
                # import RPi.GPIO as GPIO
                # GPIO.setmode(GPIO.BCM)
                # GPIO.setup(relay_pin, GPIO.OUT)
                # GPIO.output(relay_pin, GPIO.HIGH if gate_action == 'open' else GPIO.LOW)
                pass
            
            print(f"🚪 Gate {gate_action.upper()} triggered for camera {camera.id}")
            return {'success': True, 'message': f'Gate {gate_action} command sent'}
            
        except Exception as e:
            print(f"Error triggering gate control: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def send_alert_notification(vehicle_number, compliance_result, owner_email):
        """Send email alert for non-compliant vehicles"""
        if compliance_result['alert_level'] not in ['warning', 'critical']:
            return
        
        try:
            subject = f"ANPR Alert: {compliance_result['compliance_status'].upper()} - {vehicle_number}"
            
            body = f"""
ANPR Compliance Alert

Vehicle Number: {vehicle_number}
Status: {compliance_result['compliance_status'].upper()}
Alert Level: {compliance_result['alert_level'].upper()}
Time: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}

{compliance_result['message']}

Gate Action: {compliance_result['gate_action'].upper()}
Entry Allowed: {'Yes' if compliance_result['is_allowed_entry'] else 'No'}

Please take appropriate action.

---
FuelFlux ANPR System
            """
            
            msg = Message(
                subject=subject,
                recipients=[owner_email],
                body=body
            )
            
            mail.send(msg)
            print(f"📧 Alert email sent to {owner_email}")
            
        except Exception as e:
            print(f"Error sending alert email: {e}")
    
    @staticmethod
    def get_entry_statistics(pump_id, days=7):
        """Get entry statistics for dashboard"""
        from datetime import timedelta
        
        start_date = datetime.now() - timedelta(days=days)
        
        logs = VehicleEntryLog.query.filter(
            VehicleEntryLog.pump_id == pump_id,
            VehicleEntryLog.detected_at >= start_date
        ).all()
        
        stats = {
            'total_entries': len(logs),
            'compliant': sum(1 for log in logs if log.compliance_status == 'compliant'),
            'expired': sum(1 for log in logs if log.compliance_status == 'expired'),
            'expiring_soon': sum(1 for log in logs if log.compliance_status == 'expiring_soon'),
            'unknown': sum(1 for log in logs if log.compliance_status == 'unknown'),
            'blacklisted': sum(1 for log in logs if log.compliance_status == 'blacklisted'),
            'allowed': sum(1 for log in logs if log.is_allowed_entry),
            'denied': sum(1 for log in logs if not log.is_allowed_entry),
            'alerts_triggered': sum(1 for log in logs if log.alert_triggered)
        }
        
        return stats
    
    @staticmethod
    def get_recent_detections(pump_id, limit=10):
        """Get recent vehicle detections"""
        logs = VehicleEntryLog.query.filter_by(
            pump_id=pump_id
        ).order_by(VehicleEntryLog.detected_at.desc()).limit(limit).all()
        
        return logs


# Global compliance checker instance
compliance_checker = ComplianceChecker()
