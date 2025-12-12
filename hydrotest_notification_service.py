"""
Hydrotest Notification Service
Sends email and SMS notifications for expiring hydrotests
"""

from datetime import datetime, timedelta, date
from extensions import db, mail
from models import Hydrotest, HydrotestNotification, PumpOwner
from flask_mail import Message
import threading
import time

def send_email_notification(owner_email, subject, body):
    """Send email notification"""
    try:
        msg = Message(
            subject=subject,
            recipients=[owner_email],
            body=body
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email to {owner_email}: {e}")
        return False

def check_and_send_notifications(app):
    """Check for pending notifications and send them"""
    with app.app_context():
        today = date.today()
        
        pending_notifications = HydrotestNotification.query.filter(
            HydrotestNotification.notification_date <= today,
            HydrotestNotification.sent == False
        ).all()
        
        for notification in pending_notifications:
            try:
                hydrotest = Hydrotest.query.get(notification.hydrotest_id)
                owner = PumpOwner.query.get(notification.owner_id)
                
                if not hydrotest or not owner:
                    continue
                
                equipment_name = ""
                if hydrotest.tank:
                    equipment_name = f"Tank: {hydrotest.tank.name}"
                elif hydrotest.pipeline:
                    equipment_name = f"Pipeline: {hydrotest.pipeline.name}"
                
                subject = f"Hydrotest Expiry Alert - {equipment_name}"
                body = f"""
Dear {owner.full_name},

This is an automated reminder regarding your hydrotest compliance.

Equipment: {equipment_name}
Test Type: {hydrotest.test_type.replace('_', ' ').title()}
Last Test Date: {hydrotest.test_date.strftime('%d/%m/%Y')}
Next Due Date: {hydrotest.next_due_date.strftime('%d/%m/%Y')}
Days Until Expiry: {notification.days_before_expiry}

{notification.message}

Please schedule a hydrotest as soon as possible to maintain PESO compliance.

For more details, please login to your FuelFlux dashboard.

Best regards,
FuelFlux Team
                """
                
                email_sent = send_email_notification(owner.email, subject, body)
                
                if email_sent:
                    notification.sent = True
                    notification.sent_at = datetime.now()
                    notification.email_sent = True
                    db.session.commit()
                    print(f"✅ Notification sent to {owner.email} for hydrotest ID {hydrotest.id}")
                
            except Exception as e:
                print(f"Error processing notification {notification.id}: {e}")
                db.session.rollback()

def create_pending_notifications(app):
    """Create notifications for hydrotests that are approaching expiry"""
    with app.app_context():
        today = date.today()
        
        all_hydrotests = Hydrotest.query.all()
        
        for hydrotest in all_hydrotests:
            days_until_expiry = (hydrotest.next_due_date - today).days
            
            notification_thresholds = [90, 30, 0]
            
            for threshold in notification_thresholds:
                if days_until_expiry == threshold:
                    existing = HydrotestNotification.query.filter_by(
                        hydrotest_id=hydrotest.id,
                        days_before_expiry=threshold
                    ).first()
                    
                    if not existing:
                        notification = HydrotestNotification(
                            hydrotest_id=hydrotest.id,
                            owner_id=hydrotest.owner_id,
                            notification_type='expiry_reminder',
                            notification_date=today,
                            days_before_expiry=threshold,
                            message=f"Hydrotest will expire in {threshold} days. Please schedule testing."
                        )
                        db.session.add(notification)
        
        try:
            db.session.commit()
            print("✅ Pending notifications created")
        except Exception as e:
            print(f"Error creating notifications: {e}")
            db.session.rollback()

def notification_scheduler(app):
    """Background scheduler that runs every 24 hours"""
    while True:
        try:
            print("🔔 Running hydrotest notification check...")
            create_pending_notifications(app)
            check_and_send_notifications(app)
            time.sleep(86400)
        except Exception as e:
            print(f"Error in notification scheduler: {e}")
            time.sleep(3600)

def start_notification_service(app):
    """Start the notification service in a background thread"""
    thread = threading.Thread(target=notification_scheduler, args=(app,), daemon=True)
    thread.start()
    print("✅ Hydrotest notification service started")
