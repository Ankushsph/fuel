"""
Hydrotest Variance Integration Module
Integrates hydrotest status with fuel variance detection to identify potential leakage
"""

from datetime import datetime, date
from models import Hydrotest, Tank, Pipeline
from sqlalchemy import and_, or_

def get_equipment_hydrotest_status(equipment_type, equipment_id):
    """
    Get the latest hydrotest status for a tank or pipeline
    
    Args:
        equipment_type: 'tank' or 'pipeline'
        equipment_id: ID of the equipment
    
    Returns:
        dict with status information
    """
    if equipment_type == 'tank':
        latest_test = Hydrotest.query.filter_by(tank_id=equipment_id).order_by(Hydrotest.test_date.desc()).first()
    elif equipment_type == 'pipeline':
        latest_test = Hydrotest.query.filter_by(pipeline_id=equipment_id).order_by(Hydrotest.test_date.desc()).first()
    else:
        return None
    
    if not latest_test:
        return {
            'has_test': False,
            'status': 'no_test',
            'message': 'No hydrotest record found',
            'risk_level': 'high'
        }
    
    compliance_status = latest_test.get_compliance_status()
    days_until_expiry = latest_test.get_days_until_expiry()
    
    return {
        'has_test': True,
        'test_id': latest_test.id,
        'test_date': latest_test.test_date,
        'next_due_date': latest_test.next_due_date,
        'result': latest_test.result,
        'compliance_status': compliance_status,
        'days_until_expiry': days_until_expiry,
        'expired': compliance_status == 'expired',
        'failed': latest_test.result == 'Fail',
        'risk_level': calculate_risk_level(latest_test)
    }

def calculate_risk_level(hydrotest):
    """
    Calculate risk level based on hydrotest status
    
    Returns: 'low', 'medium', 'high', 'critical'
    """
    compliance_status = hydrotest.get_compliance_status()
    
    if hydrotest.result == 'Fail':
        return 'critical'
    
    if compliance_status == 'expired':
        return 'high'
    
    if compliance_status == 'due_soon':
        return 'medium'
    
    return 'low'

def analyze_variance_with_hydrotest(tank_id, daily_variance, variance_threshold=0.5):
    """
    Analyze fuel variance in context of hydrotest status
    
    Args:
        tank_id: Tank ID
        daily_variance: Daily fuel variance (percentage)
        variance_threshold: Threshold for acceptable variance
    
    Returns:
        dict with analysis results and recommendations
    """
    hydrotest_status = get_equipment_hydrotest_status('tank', tank_id)
    
    variance_exceeds_threshold = abs(daily_variance) > variance_threshold
    
    analysis = {
        'tank_id': tank_id,
        'daily_variance': daily_variance,
        'variance_threshold': variance_threshold,
        'variance_exceeds_threshold': variance_exceeds_threshold,
        'hydrotest_status': hydrotest_status,
        'alert_level': 'normal',
        'possible_causes': [],
        'recommendations': []
    }
    
    if not variance_exceeds_threshold:
        analysis['alert_level'] = 'normal'
        analysis['message'] = 'Variance within acceptable limits'
        return analysis
    
    if not hydrotest_status['has_test']:
        analysis['alert_level'] = 'critical'
        analysis['message'] = 'High variance detected with no hydrotest record'
        analysis['possible_causes'].append('Tank leakage (unverified - no hydrotest)')
        analysis['possible_causes'].append('Measurement errors')
        analysis['possible_causes'].append('Theft or unauthorized dispensing')
        analysis['recommendations'].append('Schedule immediate hydrotest')
        analysis['recommendations'].append('Inspect tank visually')
        analysis['recommendations'].append('Check dispensing records')
        return analysis
    
    if hydrotest_status['failed']:
        analysis['alert_level'] = 'critical'
        analysis['message'] = 'High variance with FAILED hydrotest - Likely leakage'
        analysis['possible_causes'].append('Tank leakage (confirmed by failed hydrotest)')
        analysis['possible_causes'].append('Pipeline leakage')
        analysis['possible_causes'].append('Joint or valve failure')
        analysis['recommendations'].append('IMMEDIATE ACTION REQUIRED: Stop tank operations')
        analysis['recommendations'].append('Contact PESO contractor for emergency repair')
        analysis['recommendations'].append('Notify PESO authorities')
        analysis['recommendations'].append('Conduct environmental impact assessment')
        return analysis
    
    if hydrotest_status['expired']:
        analysis['alert_level'] = 'high'
        analysis['message'] = 'High variance with EXPIRED hydrotest - Possible leakage'
        analysis['possible_causes'].append('Possible tank leakage (hydrotest expired)')
        analysis['possible_causes'].append('Tank degradation over time')
        analysis['possible_causes'].append('Measurement errors')
        analysis['recommendations'].append('Schedule urgent hydrotest')
        analysis['recommendations'].append('Increase monitoring frequency')
        analysis['recommendations'].append('Inspect tank and connections')
        return analysis
    
    if hydrotest_status['compliance_status'] in ['due_soon', 'warning']:
        analysis['alert_level'] = 'medium'
        analysis['message'] = 'High variance with hydrotest due soon - Monitor closely'
        analysis['possible_causes'].append('Possible early signs of tank degradation')
        analysis['possible_causes'].append('Temperature-related expansion/contraction')
        analysis['possible_causes'].append('Measurement calibration issues')
        analysis['recommendations'].append('Schedule hydrotest before expiry')
        analysis['recommendations'].append('Monitor variance daily')
        analysis['recommendations'].append('Check gauge calibration')
        return analysis
    
    analysis['alert_level'] = 'low'
    analysis['message'] = 'Variance detected but hydrotest is compliant'
    analysis['possible_causes'].append('Temperature variations')
    analysis['possible_causes'].append('Measurement errors')
    analysis['possible_causes'].append('Evaporation losses')
    analysis['possible_causes'].append('Dispensing discrepancies')
    analysis['recommendations'].append('Continue normal monitoring')
    analysis['recommendations'].append('Verify measurement accuracy')
    analysis['recommendations'].append('Check for temperature compensation')
    
    return analysis

def get_high_risk_equipment(pump_id):
    """
    Get all high-risk equipment (failed or expired hydrotests) for a pump
    
    Args:
        pump_id: Pump ID
    
    Returns:
        list of high-risk equipment with details
    """
    from models import Tank, Pipeline, Hydrotest
    
    high_risk_items = []
    
    tanks = Tank.query.filter_by(pump_id=pump_id, is_active=True).all()
    for tank in tanks:
        latest_test = Hydrotest.query.filter_by(tank_id=tank.id).order_by(Hydrotest.test_date.desc()).first()
        
        if not latest_test:
            high_risk_items.append({
                'type': 'tank',
                'id': tank.id,
                'name': tank.name,
                'risk_level': 'high',
                'reason': 'No hydrotest record',
                'action': 'Schedule hydrotest immediately'
            })
            continue
        
        if latest_test.result == 'Fail':
            high_risk_items.append({
                'type': 'tank',
                'id': tank.id,
                'name': tank.name,
                'risk_level': 'critical',
                'reason': 'Failed hydrotest',
                'test_date': latest_test.test_date,
                'action': 'STOP OPERATIONS - Emergency repair required'
            })
        elif latest_test.get_compliance_status() == 'expired':
            high_risk_items.append({
                'type': 'tank',
                'id': tank.id,
                'name': tank.name,
                'risk_level': 'high',
                'reason': 'Expired hydrotest',
                'expired_on': latest_test.next_due_date,
                'action': 'Schedule urgent hydrotest'
            })
    
    pipelines = Pipeline.query.filter_by(pump_id=pump_id, is_active=True).all()
    for pipeline in pipelines:
        latest_test = Hydrotest.query.filter_by(pipeline_id=pipeline.id).order_by(Hydrotest.test_date.desc()).first()
        
        if not latest_test:
            high_risk_items.append({
                'type': 'pipeline',
                'id': pipeline.id,
                'name': pipeline.name,
                'risk_level': 'high',
                'reason': 'No hydrotest record',
                'action': 'Schedule hydrotest immediately'
            })
            continue
        
        if latest_test.result == 'Fail':
            high_risk_items.append({
                'type': 'pipeline',
                'id': pipeline.id,
                'name': pipeline.name,
                'risk_level': 'critical',
                'reason': 'Failed hydrotest',
                'test_date': latest_test.test_date,
                'action': 'STOP OPERATIONS - Emergency repair required'
            })
        elif latest_test.get_compliance_status() == 'expired':
            high_risk_items.append({
                'type': 'pipeline',
                'id': pipeline.id,
                'name': pipeline.name,
                'risk_level': 'high',
                'reason': 'Expired hydrotest',
                'expired_on': latest_test.next_due_date,
                'action': 'Schedule urgent hydrotest'
            })
    
    return high_risk_items

def generate_variance_alert_message(analysis):
    """
    Generate user-friendly alert message based on variance analysis
    
    Args:
        analysis: Result from analyze_variance_with_hydrotest
    
    Returns:
        Formatted alert message
    """
    alert_level = analysis['alert_level']
    message = analysis['message']
    
    alert_icons = {
        'critical': '🚨',
        'high': '⚠️',
        'medium': '⚡',
        'low': 'ℹ️',
        'normal': '✅'
    }
    
    icon = alert_icons.get(alert_level, 'ℹ️')
    
    alert_msg = f"{icon} {alert_level.upper()}: {message}\n\n"
    
    if analysis['possible_causes']:
        alert_msg += "Possible Causes:\n"
        for cause in analysis['possible_causes']:
            alert_msg += f"  • {cause}\n"
        alert_msg += "\n"
    
    if analysis['recommendations']:
        alert_msg += "Recommendations:\n"
        for rec in analysis['recommendations']:
            alert_msg += f"  • {rec}\n"
    
    return alert_msg
