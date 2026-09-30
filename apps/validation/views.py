from datetime import timedelta
import time
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.db.models import Count, Avg, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from .feedback_choices import factor_counts
from .forms import SignupForm, InterestForm, FeedbackForm, LeadUpdateForm
from .models import Participant, Visit, WalkthroughRound, Feedback, Lead, LeadUpdate, ROLES
from .services import register, attribution, participant_for, round_queryset, round_progress

@never_cache
@require_http_methods(['GET','POST'])
def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = register(request, form.cleaned_data)
        except IntegrityError:
            form.add_error(None, 'Unable to create this account. If you have already registered, please log in.')
        else:
            login(request, user, backend='apps.accounts.backends.EmailBackend')
            messages.success(request, 'Welcome. Your own demo workspace is ready. Start a case to begin your walkthrough.')
            return redirect('dashboard')
    return render(request, 'registration/signup.html', {'form':form})

@never_cache
@require_http_methods(['GET','POST'])
def pilot_interest(request):
    participant = participant_for(request.user)
    initial = {'interest':request.GET.get('interest','Pilot')}
    if participant:
        initial.update(full_name=request.user.get_full_name(), email=request.user.email, role=participant.role, organisation=participant.organisation)
    form = InterestForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        if time.time()-request.session.get('last_pilot_at',0)<60:
            form.add_error(None, 'Please wait a minute before sending another request.')
        else:
            data = form.cleaned_data
            source, campaign = attribution(request)
            lead = Lead.objects.create(participant=participant, name=data['full_name'], email=data['email'], role=data['role'], organisation=data['organisation'],
                interest=data['interest'], message=data['message'], source=source, campaign=campaign, whatsapp=data['whatsapp'],
                whatsapp_consent=data['whatsapp_consent'], contact_consent_at=timezone.now())
            request.session['last_pilot_at']=time.time()
            request.session['pilot_received']=str(lead.reference)
            return redirect('pilot-interest')
    received=request.session.pop('pilot_received',None) if request.method=='GET' else None
    return render(request, 'validation/interest.html', {'form':form,'received':received})

@require_GET
def privacy(request):
    return render(request,'validation/privacy.html')

@login_required
@require_GET
def walkthrough(request):
    participant = get_object_or_404(Participant, user=request.user)
    page=Paginator(round_queryset(participant),10).get_page(request.GET.get('page'))
    return render(request,'validation/walkthrough.html',{'rounds':[round_progress(item) for item in page], 'page':page})

@login_required
@never_cache
@require_GET
def round_status(request,pk):
    item=get_object_or_404(WalkthroughRound,case_id=pk,participant__user=request.user)
    return JsonResponse({'prompt':item.completed_at is not None and not item.prompt_dismissed and not Feedback.objects.filter(round=item).exists(),
        'feedback_url':reverse('round-feedback',args=[item.pk])})

@login_required
@require_http_methods(['GET','POST'])
def feedback(request,pk):
    item=get_object_or_404(WalkthroughRound.objects.select_related('case','participant__user'),pk=pk,participant__user=request.user)
    progress=round_progress(item)
    existing=Feedback.objects.filter(round=item).first()
    form=FeedbackForm(request.POST or None)
    if request.method=='POST' and not existing and form.is_valid():
        with transaction.atomic():
            locked=WalkthroughRound.objects.select_for_update().get(pk=item.pk)
            if not Feedback.objects.filter(round=locked).exists():
                result=Feedback.objects.create(round=locked,completion_at_submission=progress['percent'],**form.cleaned_data)
                if result.intent!='None' and result.contact_consent:
                    participant=item.participant
                    Lead.objects.create(participant=participant,feedback=result,name=request.user.get_full_name(),email=request.user.email,
                        role=participant.role,organisation=participant.organisation,interest=result.intent,message=result.suggestion,
                        source=participant.source,campaign=participant.campaign,whatsapp=participant.whatsapp,whatsapp_consent=participant.whatsapp_consent,contact_consent_at=timezone.now())
        messages.success(request,'Thank you. Your feedback has been recorded.')
        return redirect('walkthrough')
    return render(request,'validation/feedback.html',{'form':form,'progress':progress,'existing':existing})

@login_required
@require_POST
def dismiss_feedback(request,pk):
    item=get_object_or_404(WalkthroughRound,pk=pk,participant__user=request.user)
    WalkthroughRound.objects.filter(pk=item.pk).update(prompt_dismissed=True)
    return redirect('walkthrough')

def require_owner(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied

@login_required
@never_cache
@require_GET
def analytics(request):
    require_owner(request)
    days=request.GET.get('days','30')
    if days not in ('7','30','90','all'): days='30'
    since=timezone.now()-timedelta(days=int(days)) if days!='all' else None
    participants=Participant.objects.select_related('user')
    visits=Visit.objects.all()
    leads=Lead.objects.select_related('participant','feedback')
    if since:
        participants=participants.filter(created_at__gte=since)
        visits=visits.filter(started_at__gte=since)
        leads=leads.filter(created_at__gte=since)
    source=request.GET.get('source','')[:80]
    role=request.GET.get('role','')
    if source:
        participants=participants.filter(source=source);visits=visits.filter(source=source);leads=leads.filter(source=source)
    if role in dict(ROLES):
        participants=participants.filter(role=role);leads=leads.filter(role=role)
    else: role=''
    # Completion is a registration cohort: returning later still counts for the same participant.
    rounds=WalkthroughRound.objects.filter(participant__in=participants).select_related('case__patient','case__attachment','case__qualityassessment','case__aiassessment','participant__user').prefetch_related('case__clinical_decisions')
    completed=rounds.filter(completed_at__isnull=False)
    responses=Feedback.objects.filter(round__in=rounds)
    stats={'visits':visits.count(),'landing':visits.filter(landing_seen=True).count(),'registrations':participants.count(),
        'started':rounds.values('participant_id').distinct().count(),'rounds':rounds.count(),'completed':completed.count(),
        'finishers':completed.values('participant_id').distinct().count(),'feedback':responses.count(),'rating':responses.aggregate(value=Avg('rating'))['value'],
        'leads':leads.count(),'demos':leads.filter(interest='Demo').count(),'pilots':leads.filter(interest__in=['Pilot','Waitlist']).count(),
        'commercial':leads.filter(interest__in=['Pricing','Deployment']).count(),
        'returners':visits.filter(participant__isnull=False).values('participant_id').annotate(n=Count('pk')).filter(n__gt=1).count()}
    stats['completion_rate']=round(stats['completed']/stats['rounds']*100) if stats['rounds'] else 0
    progress=[round_progress(item) for item in rounds]
    latest={}
    for item in progress:
        latest.setdefault(item['round'].participant_id,item)
    participant_q=request.GET.get('participant_q','').strip()[:120]
    participant_list=participants.annotate(round_count=Count('rounds',distinct=True),completed_count=Count('rounds',filter=Q(rounds__completed_at__isnull=False),distinct=True))
    if participant_q:
        participant_list=participant_list.filter(Q(user__first_name__icontains=participant_q)|Q(user__last_name__icontains=participant_q)|Q(user__email__icontains=participant_q)|Q(organisation__icontains=participant_q))
    participant_page=Paginator(participant_list.order_by('-created_at','-pk'),15).get_page(request.GET.get('participant_page'))
    participant_rows=[{'participant':person,'latest':latest.get(person.pk)} for person in participant_page]
    stops={}
    for item in progress:
        if not item['complete']:
            stops[item['next_label']]=stops.get(item['next_label'],0)+1
    q=request.GET.get('q','').strip()[:120]
    stage=request.GET.get('stage','')
    filtered=leads
    if q: filtered=filtered.filter(Q(name__icontains=q)|Q(email__icontains=q)|Q(organisation__icontains=q))
    if stage in dict(Lead.STAGES): filtered=filtered.filter(stage=stage)
    else: stage=''
    page=Paginator(filtered,15).get_page(request.GET.get('page'))
    params=request.GET.copy();params.pop('page',None)
    participant_params=request.GET.copy();participant_params.pop('participant_page',None)
    return render(request,'validation/analytics.html',{'stats':stats,'leads':page,'page':page,'querystring':params.urlencode(),
        'days':days,'source':source,'role':role,'roles':ROLES,'q':q,'stage':stage,'stages':Lead.STAGES,
        'participant_q':participant_q,'participant_rows':participant_rows,'participant_page':participant_page,'participant_querystring':participant_params.urlencode(),
        'sources':Visit.objects.values_list('source',flat=True).distinct().order_by('source'),
        'source_rows':visits.values('source').annotate(n=Count('pk')).order_by('-n'),
        'dropoffs':stops.items(),'barriers':factor_counts(responses),
        'recent_feedback':responses.select_related('round__participant__user').order_by('-created_at')[:10],
        'recent_rounds':progress[:20]})

@login_required
@never_cache
@require_http_methods(['GET','POST'])
def lead_detail(request,pk):
    require_owner(request)
    lead=get_object_or_404(Lead,pk=pk)
    form=LeadUpdateForm(request.POST or None,instance=lead,initial={'version':lead.version})
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            locked=Lead.objects.select_for_update().get(pk=pk)
            if locked.version!=form.cleaned_data['version']:
                form.add_error(None,'This enquiry changed in another session. Reload before saving.')
            else:
                for field in ('stage','next_action','next_action_date'):
                    setattr(locked,field,form.cleaned_data[field])
                locked.version+=1;locked.save()
                LeadUpdate.objects.create(lead=locked,actor=request.user,stage=locked.stage,next_action=locked.next_action,next_action_date=locked.next_action_date)
                messages.success(request,'Enquiry updated.')
                return redirect('validation-lead',pk=pk)
    return render(request,'validation/lead.html',{'lead':lead,'form':form,'updates':lead.updates.select_related('actor').order_by('-created_at')})
