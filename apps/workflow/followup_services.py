from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.clinical.models import Case
from apps.workflow.models import FollowUp, FollowUpUpdate, CaseEvent
from apps.workflow.followup_forms import FollowUpUpdateForm
from core.permissions import require_facility_access

@transaction.atomic
def update_followup(*,user,followup_id,data):
    case_id=FollowUp.objects.values_list('case_id',flat=True).get(pk=followup_id)
    case=Case.objects.select_for_update().select_related('patient').get(pk=case_id)
    require_facility_access(user,case.patient.facility_id)
    item=FollowUp.objects.select_for_update().get(pk=followup_id)
    form=FollowUpUpdateForm(data)
    if not form.is_valid(): raise ValidationError('Review the form fields and confirm the change.')
    values=form.cleaned_data
    details={'notes':values['notes'],'due_date':str(values['due_date']) if values['action']=='RESCHEDULE' else ''}
    existing=FollowUpUpdate.objects.filter(request_id=values['request_id']).first()
    if existing:
        if existing.followup_id==item.pk and existing.actor_id==user.pk and existing.action==values['action'] and existing.details==details:
            return existing
        raise ValidationError('This submission was already used. Reload the page before continuing.')
    if item.completed_at: raise ValidationError('This follow-up is already completed. Its outcome is preserved.')
    if item.version!=values['version']: raise ValidationError('This follow-up changed while you were viewing it. Reload the page before saving.')
    if values['action']=='RESCHEDULE':
        if values['due_date']==item.due_date: raise ValidationError('Choose a different date to reschedule this review.')
        previous=str(item.due_date);item.due_date=values['due_date']
        kind='FOLLOW_UP_RESCHEDULED'
    else:
        previous=str(item.due_date);item.completed_at=timezone.now();item.completed_by=user;item.outcome=values['notes']
        kind='FOLLOW_UP_COMPLETED'
    item.version+=1;item.save()
    update=FollowUpUpdate.objects.create(followup=item,actor=user,request_id=values['request_id'],action=values['action'],details=details)
    if item.completed_at and case.status==Case.Status.FOLLOW_UP and not FollowUp.objects.filter(case=case,completed_at__isnull=True).exists():
        case.status=Case.Status.COMPLETED
    case.save(update_fields=['status','updated_at'])
    CaseEvent.objects.create(case=case,actor=user,kind=kind,details={'followup_id':item.pk,'previous_due_date':previous,**details})
    return update
