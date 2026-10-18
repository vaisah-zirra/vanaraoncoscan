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
            messages.success(request, 'Welcome. Your workspace is ready. Start a case to begin your walkthrough.')
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
    from urllib.parse import urlencode
    from .cohort import cohort, PERIODS
    from .dashboard import build
    c = cohort(request.GET)
    data = build(c, request.user)
    stats = {'registrations': data['counts']['registrations'], 'rounds': data['counts']['rounds'],
             'completed': data['counts']['completed'], 'leads': data['counts']['leads']}
    tab = request.GET.get('tab', 'pilot')
    if tab not in {t['key'] for t in data['tabs']}:
        tab = 'pilot'
    base = {'source': c['source'], 'role': c['role']}
    periods = [{'key': k, 'label': {'7': '7 days', '30': '30 days', '90': '90 days', 'all': 'All time'}[k],
                'qs': urlencode(dict(base, days=k)), 'active': k == c['days']} for k in PERIODS]
    return render(request, 'validation/analytics.html', dict(data, stats=stats, tab=tab, days=c['days'], period=c['period'],
        source=c['source'], role=c['role'], periods=periods, roles=ROLES,
        sources=Visit.objects.exclude(source='').values_list('source', flat=True).distinct().order_by('source'),
        export_qs=urlencode({'days': c['days'], 'source': c['source'], 'role': c['role']})))

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


@login_required
@never_cache
@require_GET
def evidence_export(request, kind):
    """Download the validation evidence as a branded PDF (full report or one section)."""
    require_owner(request)
    from django.http import HttpResponse, Http404
    from .cohort import cohort
    from .evidence import build
    from .evidence_pdf import render, KINDS
    if kind not in KINDS:
        raise Http404
    identity = 'named' if request.GET.get('identity') == 'named' else 'anonymised'
    data = build(cohort(request.GET), identity)
    response = HttpResponse(render(data, kind), content_type='application/pdf')
    suffix = '' if identity == 'anonymised' else '_INTERNAL'
    response['Content-Disposition'] = f'attachment; filename="VanaraOncoScan_{kind}_evidence_{data["generated"]:%Y%m%d}{suffix}.pdf"'
    response['Cache-Control'] = 'private, no-store, max-age=0'
    return response
