"""
PESO Compliance Validator
Validates hydrotest records against PESO regulations
"""

from datetime import datetime, timedelta, date
from models import Hydrotest, Tank, Pipeline, ContractorMaster

class PESOComplianceValidator:
    """Validator for PESO compliance requirements"""
    
    # PESO Regulations
    TANK_HYDROTEST_VALIDITY_YEARS = 5
    PIPELINE_HYDROTEST_VALIDITY_YEARS = 5
    SUMP_HYDROTEST_VALIDITY_YEARS = 3
    VENT_LINE_VALIDITY_YEARS = 3
    
    MIN_TEST_PRESSURE_BAR = 1.5
    MIN_HOLD_DURATION_MINUTES = 30
    
    REQUIRED_DOCUMENTS = [
        'certificate',
        'gas_free',
        'gauge_calibration'
    ]
    
    @staticmethod
    def validate_hydrotest_record(hydrotest, files_by_type):
        """
        Validate a hydrotest record against PESO requirements
        
        Args:
            hydrotest: Hydrotest model instance
            files_by_type: Dictionary of uploaded files by type
        
        Returns:
            dict with validation results
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'compliance_score': 100
        }
        
        # Validate test pressure
        if hydrotest.test_pressure < PESOComplianceValidator.MIN_TEST_PRESSURE_BAR:
            validation_result['errors'].append(
                f"Test pressure ({hydrotest.test_pressure} {hydrotest.pressure_unit}) "
                f"is below PESO minimum ({PESOComplianceValidator.MIN_TEST_PRESSURE_BAR} bar)"
            )
            validation_result['is_valid'] = False
            validation_result['compliance_score'] -= 20
        
        # Validate hold duration
        if hydrotest.hold_duration < PESOComplianceValidator.MIN_HOLD_DURATION_MINUTES:
            validation_result['errors'].append(
                f"Hold duration ({hydrotest.hold_duration} minutes) "
                f"is below PESO minimum ({PESOComplianceValidator.MIN_HOLD_DURATION_MINUTES} minutes)"
            )
            validation_result['is_valid'] = False
            validation_result['compliance_score'] -= 20
        
        # Validate contractor licence
        if not hydrotest.competent_person_licence:
            validation_result['errors'].append("Competent person licence number is required")
            validation_result['is_valid'] = False
            validation_result['compliance_score'] -= 15
        
        # Validate PESO certificate number
        if not hydrotest.peso_certificate_number:
            validation_result['warnings'].append("PESO certificate number not provided")
            validation_result['compliance_score'] -= 5
        
        # Validate required documents
        for doc_type in PESOComplianceValidator.REQUIRED_DOCUMENTS:
            if doc_type not in files_by_type or not files_by_type[doc_type]:
                validation_result['warnings'].append(f"Missing {doc_type.replace('_', ' ')} document")
                validation_result['compliance_score'] -= 10
        
        # Validate test result
        if hydrotest.result == 'Fail':
            validation_result['warnings'].append(
                "Failed hydrotest - Equipment requires immediate repair and re-testing"
            )
            validation_result['compliance_score'] -= 30
        
        # Validate validity period
        expected_validity = PESOComplianceValidator.get_expected_validity(hydrotest.test_type)
        if hydrotest.validity_years != expected_validity:
            validation_result['warnings'].append(
                f"Validity period ({hydrotest.validity_years} years) "
                f"differs from PESO standard ({expected_validity} years)"
            )
        
        # Ensure compliance score doesn't go negative
        validation_result['compliance_score'] = max(0, validation_result['compliance_score'])
        
        return validation_result
    
    @staticmethod
    def get_expected_validity(test_type):
        """Get expected validity period for test type"""
        validity_map = {
            'tank_hydrotest': PESOComplianceValidator.TANK_HYDROTEST_VALIDITY_YEARS,
            'pipeline_hydrotest': PESOComplianceValidator.PIPELINE_HYDROTEST_VALIDITY_YEARS,
            'sump_hydrotest': PESOComplianceValidator.SUMP_HYDROTEST_VALIDITY_YEARS,
            'vent_line_test': PESOComplianceValidator.VENT_LINE_VALIDITY_YEARS
        }
        return validity_map.get(test_type, 5)
    
    @staticmethod
    def validate_contractor(contractor_name, licence_number):
        """
        Validate contractor against PESO database
        
        Args:
            contractor_name: Contractor name
            licence_number: Licence number
        
        Returns:
            dict with validation results
        """
        contractor = ContractorMaster.query.filter_by(
            licence_number=licence_number
        ).first()
        
        if not contractor:
            return {
                'is_valid': False,
                'message': 'Contractor not found in PESO database',
                'warning': 'Please verify contractor credentials manually'
            }
        
        if not contractor.is_active:
            return {
                'is_valid': False,
                'message': 'Contractor is inactive',
                'warning': 'Do not proceed with this contractor'
            }
        
        if contractor.licence_valid_until:
            if contractor.licence_valid_until < date.today():
                return {
                    'is_valid': False,
                    'message': 'Contractor licence has expired',
                    'expired_on': contractor.licence_valid_until,
                    'warning': 'Do not proceed with this contractor'
                }
        
        if not contractor.is_peso_verified:
            return {
                'is_valid': True,
                'message': 'Contractor found but not PESO verified',
                'warning': 'Verify PESO credentials before proceeding'
            }
        
        return {
            'is_valid': True,
            'message': 'Contractor is PESO verified and active',
            'contractor': contractor
        }
    
    @staticmethod
    def generate_compliance_certificate(hydrotest):
        """
        Generate compliance certificate data for a hydrotest
        
        Args:
            hydrotest: Hydrotest model instance
        
        Returns:
            dict with certificate data
        """
        validation = PESOComplianceValidator.validate_hydrotest_record(hydrotest, {})
        
        certificate_data = {
            'certificate_number': f"PESO-HT-{hydrotest.id}-{datetime.now().year}",
            'test_id': hydrotest.id,
            'equipment_type': 'Tank' if hydrotest.tank else 'Pipeline',
            'equipment_name': hydrotest.tank.name if hydrotest.tank else hydrotest.pipeline.name,
            'test_type': hydrotest.test_type.replace('_', ' ').title(),
            'test_date': hydrotest.test_date.strftime('%d/%m/%Y'),
            'test_pressure': f"{hydrotest.test_pressure} {hydrotest.pressure_unit}",
            'hold_duration': f"{hydrotest.hold_duration} minutes",
            'result': hydrotest.result,
            'contractor_name': hydrotest.peso_contractor_name,
            'contractor_licence': hydrotest.competent_person_licence,
            'next_due_date': hydrotest.next_due_date.strftime('%d/%m/%Y'),
            'validity_period': f"{hydrotest.validity_years} years",
            'compliance_status': hydrotest.get_compliance_status(),
            'compliance_score': validation['compliance_score'],
            'peso_approved': hydrotest.peso_approved,
            'generated_on': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        }
        
        return certificate_data
    
    @staticmethod
    def check_pump_compliance(pump_id):
        """
        Check overall PESO compliance for a pump
        
        Args:
            pump_id: Pump ID
        
        Returns:
            dict with compliance summary
        """
        from models import Tank, Pipeline
        
        tanks = Tank.query.filter_by(pump_id=pump_id, is_active=True).all()
        pipelines = Pipeline.query.filter_by(pump_id=pump_id, is_active=True).all()
        
        total_equipment = len(tanks) + len(pipelines)
        compliant_count = 0
        non_compliant_count = 0
        no_test_count = 0
        
        issues = []
        
        for tank in tanks:
            latest_test = Hydrotest.query.filter_by(tank_id=tank.id).order_by(
                Hydrotest.test_date.desc()
            ).first()
            
            if not latest_test:
                no_test_count += 1
                issues.append(f"Tank {tank.name}: No hydrotest record")
            elif latest_test.get_compliance_status() in ['expired', 'due_soon']:
                non_compliant_count += 1
                issues.append(f"Tank {tank.name}: Hydrotest {latest_test.get_compliance_status()}")
            elif latest_test.result == 'Fail':
                non_compliant_count += 1
                issues.append(f"Tank {tank.name}: Failed hydrotest")
            else:
                compliant_count += 1
        
        for pipeline in pipelines:
            latest_test = Hydrotest.query.filter_by(pipeline_id=pipeline.id).order_by(
                Hydrotest.test_date.desc()
            ).first()
            
            if not latest_test:
                no_test_count += 1
                issues.append(f"Pipeline {pipeline.name}: No hydrotest record")
            elif latest_test.get_compliance_status() in ['expired', 'due_soon']:
                non_compliant_count += 1
                issues.append(f"Pipeline {pipeline.name}: Hydrotest {latest_test.get_compliance_status()}")
            elif latest_test.result == 'Fail':
                non_compliant_count += 1
                issues.append(f"Pipeline {pipeline.name}: Failed hydrotest")
            else:
                compliant_count += 1
        
        compliance_percentage = (compliant_count / total_equipment * 100) if total_equipment > 0 else 0
        
        return {
            'total_equipment': total_equipment,
            'compliant_count': compliant_count,
            'non_compliant_count': non_compliant_count,
            'no_test_count': no_test_count,
            'compliance_percentage': round(compliance_percentage, 2),
            'is_fully_compliant': non_compliant_count == 0 and no_test_count == 0,
            'issues': issues,
            'peso_status': 'COMPLIANT' if compliance_percentage == 100 else 'NON-COMPLIANT'
        }
