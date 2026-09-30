from django.db import transaction
from core.permissions import require_facility_access
from apps.workflow.models import CaseEvent
from .models import Case, Patient

@transaction.atomic
def start_case(*, user, patient_id, presenting_concern=''):
    patient = Patient.objects.get(pk=patient_id)
    require_facility_access(user, patient.facility_id)
    case = Case.objects.create(patient=patient, presenting_concern=presenting_concern)
    CaseEvent.objects.create(case=case, actor=user, kind='ASSESSMENT_STARTED')
    from apps.validation.services import start_round
    start_round(user, case)
    return case
