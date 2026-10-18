import uuid
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from apps.clinical.models import Case
from apps.workflow.models import Referral, ReferralUpdate, CaseEvent
from core.permissions import facility_ids_for, require_facility_access

class ReferralForm(forms.Form):
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    status = forms.ChoiceField(label='Next referral stage', choices=[('', 'Choose a stage'), *Referral.Status.choices])
    notes = forms.CharField(label='Update notes', max_length=4000, widget=forms.Textarea(attrs={'rows':5, 'placeholder':'Record the receiving service response, appointment details or outcome.'}))
    appointment_date = forms.DateField(label='Appointment date', required=False, widget=forms.DateInput(attrs={'type':'date'}))
    confirmed = forms.BooleanField(label='I confirm this update reflects the information received.')
    def clean(self):
        data = super().clean()
        if data.get('status') == 'SCHEDULED':
            if not data.get('appointment_date'): self.add_error('appointment_date','Choose the appointment date.')
            elif data['appointment_date'] < timezone.localdate(): self.add_error('appointment_date','Choose today or a future date.')
        else: data['appointment_date'] = None
        return data

def scoped_referrals(user):
    return Referral.objects.filter(case__patient__facility_id__in=facility_ids_for(user)).select_related('case__patient','confirmed_by')

@transaction.atomic
def update_referral(*, user, referral_id, data):
    case_id = Referral.objects.values_list('case_id',flat=True).get(pk=referral_id)
    case = Case.objects.select_for_update().select_related('patient').get(pk=case_id)
    require_facility_access(user,case.patient.facility_id)
    item = Referral.objects.select_for_update().get(pk=referral_id)
    form = ReferralForm(data)
    if not form.is_valid(): raise ValidationError('Review the fields and confirm the update.')
    v = form.cleaned_data
    existing = ReferralUpdate.objects.filter(request_id=v['request_id']).first()
    if existing:
        if (existing.referral_id,existing.actor_id,existing.status,existing.notes,existing.appointment_date) == (item.pk,user.pk,v['status'],v['notes'],v['appointment_date']): return existing
        raise ValidationError('This submission has already been used. Reload the page.')
    if item.version != v['version']: raise ValidationError('This referral changed. Reload the page before saving.')
    transitions = {'PENDING':{'ACCEPTED','SCHEDULED','COMPLETED','CANCELLED'},'ACCEPTED':{'SCHEDULED','COMPLETED','CANCELLED'},'SCHEDULED':{'SCHEDULED','COMPLETED','CANCELLED'}}
    if v['status'] not in transitions.get(item.status,set()): raise ValidationError('This stage change is not available for the current referral.')
    if item.status == v['status'] and item.appointment_date == v['appointment_date']: raise ValidationError('Choose a different appointment date to reschedule.')
    old = item.status
    item.status = v['status']
    if item.status == 'SCHEDULED': item.appointment_date = v['appointment_date']
    item.version += 1
    item.save()
    update = ReferralUpdate.objects.create(referral=item,actor=user,request_id=v['request_id'],status=item.status,notes=v['notes'],appointment_date=v['appointment_date'])
    CaseEvent.objects.create(case=case,actor=user,kind='REFERRAL_UPDATED',details={'referral_id':item.pk,'previous_status':old,'status':item.status,'notes':v['notes'],'appointment_date':str(item.appointment_date or '')})
    case.save(update_fields=['updated_at'])
    return update

@login_required
@require_GET
def referral_list(request):
    all_items = scoped_referrals(request.user)
    counts = all_items.aggregate(open=Count('pk',filter=~Q(status__in=['COMPLETED','CANCELLED'])),pending=Count('pk',filter=Q(status='PENDING')),accepted=Count('pk',filter=Q(status='ACCEPTED')),scheduled=Count('pk',filter=Q(status='SCHEDULED')),completed=Count('pk',filter=Q(status='COMPLETED')),cancelled=Count('pk',filter=Q(status='CANCELLED')),all=Count('pk'),urgent=Count('pk',filter=Q(urgency__in=['URGENT','PRIORITY'])&~Q(status__in=['COMPLETED','CANCELLED'])))
    q=request.GET.get('q','').strip()[:120];status=request.GET.get('status','open');urgency=request.GET.get('urgency','')
    items=all_items
    if status == 'open': items=items.exclude(status__in=['COMPLETED','CANCELLED'])
    elif status in Referral.Status.values: items=items.filter(status=status)
    else: status='all'
    if urgency in ['ROUTINE','PRIORITY','URGENT']: items=items.filter(urgency=urgency)
    else: urgency=''
    if q: items=items.filter(Q(case__patient__display_name__icontains=q)|Q(case__patient__reference__icontains=q)|Q(destination__icontains=q)|Q(reason__icontains=q))
    page=Paginator(items.order_by('-confirmed_at','-pk'),10).get_page(request.GET.get('page'))
    params=request.GET.copy();params.pop('page',None)
    today=timezone.localdate()
    for item in page:
        name=[w for w in item.case.patient.display_name.split() if w[:1].isalpha()]
        item.initials=((name[0][0]+(name[-1][0] if len(name)>1 else '')) if name else '?').upper()
        item.days_open=(today-timezone.localtime(item.confirmed_at).date()).days
        item.appt_in=(item.appointment_date-today).days if item.appointment_date else None
    tabs=[('open','Open',counts['open']),('PENDING','Awaiting acknowledgement',counts['pending']),('ACCEPTED','Accepted',counts['accepted']),('SCHEDULED','Scheduled',counts['scheduled']),('COMPLETED','Completed',counts['completed']),('CANCELLED','Cancelled',counts['cancelled']),('all','All',counts['all'])]
    tab_qs={'q':q,'urgency':urgency}
    from urllib.parse import urlencode
    tab_qs=urlencode({k:v for k,v in tab_qs.items() if v})
    return render(request,'referrals.html',{'page':page,'counts':counts,'q':q,'status':status,'urgency':urgency,'stages':Referral.Status.choices,'querystring':params.urlencode(),'tabs':tabs,'tab_qs':tab_qs})

@login_required
@require_http_methods(['GET','POST'])
def referral_detail(request,pk):
    item=get_object_or_404(scoped_referrals(request.user),pk=pk)
    form=ReferralForm(request.POST if request.method=='POST' else None,initial={'request_id':uuid.uuid4(),'version':item.version})
    allowed = {'PENDING':['ACCEPTED','SCHEDULED','COMPLETED','CANCELLED'],'ACCEPTED':['SCHEDULED','COMPLETED','CANCELLED'],'SCHEDULED':['SCHEDULED','COMPLETED','CANCELLED']}.get(item.status,[])
    form.fields['status'].choices = [('', 'Choose a stage')] + [(value,label) for value,label in Referral.Status.choices if value in allowed]
    if request.method=='POST' and form.is_valid():
        try: update_referral(user=request.user,referral_id=pk,data=request.POST)
        except ValidationError as exc: form.add_error(None,exc.messages[0])
        else:
            messages.success(request,'Referral updated. The case timeline and report reflect this record.')
            return redirect('referral-detail',pk=pk)
    order=['PENDING','ACCEPTED','SCHEDULED','COMPLETED']
    reached=order.index(item.status) if item.status in order else -1
    if item.status=='CANCELLED':
        seen={u.status for u in item.updates.all()}
        reached=max([order.index(x) for x in seen if x in order]+[0])
    labels={'PENDING':'Referred','ACCEPTED':'Accepted','SCHEDULED':'Appointment','COMPLETED':'Completed'}
    steps=[{'label':labels[k],'state':('done' if i<reached or (i==reached and item.status=='COMPLETED') else 'current' if i==reached and item.status!='CANCELLED' else 'done' if i==reached else 'todo')} for i,k in enumerate(order)]
    name=[w for w in item.case.patient.display_name.split() if w[:1].isalpha()]
    initials=((name[0][0]+(name[-1][0] if len(name)>1 else '')) if name else '?').upper()
    return render(request,'referral_detail.html',{'item':item,'form':form,'closed':item.status in ['COMPLETED','CANCELLED'],'updates':item.updates.select_related('actor').order_by('-created_at','-pk'),'steps':steps,'initials':initials,'days_open':(timezone.localdate()-timezone.localtime(item.confirmed_at).date()).days})
