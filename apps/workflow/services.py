from django.core.exceptions import ValidationError
from django.db import transaction
from apps.clinical.models import Case, AIAssessment, QualityAssessment
from apps.workflow.models import ClinicalDecision, Referral, FollowUp, SpecialistReview, CaseEvent
from apps.workflow.forms import ClinicalDecisionForm
from core.permissions import require_facility_access

@transaction.atomic
def confirm_decision(*, user, case_id, data):
    case = Case.objects.select_for_update().select_related('patient').get(pk=case_id)
    require_facility_access(user, case.patient.facility_id)
    form = ClinicalDecisionForm(data)
    if not form.is_valid():
        raise ValidationError('Review the decision fields and confirm before saving.')
    values = form.cleaned_data
    action = values['action']
    fields = {'REFERRAL':['destination','urgency','reason'], 'SPECIALIST':['reason'], 'FOLLOW_UP':['due_date','followup_notes'], 'ROUTINE':['safety_net','concordant']}[action]
    details = {key: str(values[key]) for key in fields}
    existing = ClinicalDecision.objects.filter(request_id=values['request_id']).first()
    if existing:
        if existing.case_id == case.pk and existing.actor_id == user.pk and existing.action == action and existing.notes == values['notes'] and existing.details == details:
            return existing
        raise ValidationError('This submission has already been used. Reload the review screen.')
    if case.updated_at.isoformat() != values['version']:
        raise ValidationError('This case changed while you were reviewing it. Reload the page before confirming.')
    assessment = AIAssessment.objects.filter(case=case).first()
    if not assessment or not QualityAssessment.objects.filter(case=case, adequate=True).exists():
        raise ValidationError('A completed assessment and a passed quality check are required.')
    if case.status not in (Case.Status.ASSESSED, Case.Status.REVIEW_PENDING, Case.Status.REVIEWED):
        raise ValidationError('This case is not awaiting a clinical decision. Its existing plan is preserved.')
    if Referral.objects.filter(case=case).exists() or FollowUp.objects.filter(case=case, completed_at__isnull=True).exists():
        raise ValidationError('A care plan is already recorded for this case.')
    if action == 'FOLLOW_UP' and assessment.disposition != 'NON_SUSPICIOUS' and not SpecialistReview.objects.filter(case=case, signed_at__isnull=False).exists():
        raise ValidationError('A signed specialist opinion is required before choosing follow-up for this assessment. Request specialist review or confirm a referral.')
    if action == 'ROUTINE' and assessment.disposition != 'NON_SUSPICIOUS':
        raise ValidationError('Routine-care completion is available only for a non-suspicious assessment. Record a referral, specialist review or an appropriate follow-up plan instead.')
    if action == 'ROUTINE' and SpecialistReview.objects.filter(case=case, signed_at__isnull=True).exists():
        raise ValidationError('Resolve the pending specialist review before completing this assessment.')
    decision = ClinicalDecision.objects.create(case=case, actor=user, request_id=values['request_id'], action=action, notes=values['notes'], details=details)
    if action == 'REFERRAL':
        Referral.objects.create(case=case, destination=values['destination'], urgency=values['urgency'], reason=values['reason'], confirmed_by=user)
        case.status = Case.Status.REFERRAL_CONFIRMED
        event = 'REFERRAL_CONFIRMED'
    elif action == 'ROUTINE':
        case.status = Case.Status.COMPLETED
        event = 'ROUTINE_CARE_CONFIRMED'
    elif action == 'FOLLOW_UP':
        FollowUp.objects.create(case=case, due_date=values['due_date'], notes=values['followup_notes'])
        case.status = Case.Status.FOLLOW_UP
        event = 'FOLLOW_UP_SCHEDULED'
    else:
        if not SpecialistReview.objects.filter(case=case, signed_at__isnull=True).exists():
            SpecialistReview.objects.create(case=case)
        case.status = Case.Status.REVIEW_PENDING
        event = 'CLINICIAN_REVIEW_REQUEST_CONFIRMED'
    case.save(update_fields=['status','updated_at'])
    CaseEvent.objects.create(case=case, actor=user, kind=event,
        details={'decision_id':decision.pk,'summary':decision.get_action_display(), **details})
    return decision
