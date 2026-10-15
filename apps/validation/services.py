import hashlib
import re
import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Patient
from .models import Participant, Visit, WalkthroughRound, Lead

def participant_for(user):
    if not user.is_authenticated:
        return None
    return Participant.objects.filter(user=user).select_related('user').first()

def attribution(request):
    return request.session.get('validation_source', 'direct'), request.session.get('validation_campaign', '')

def record_visit(request):
    """A visit is a first-party session with a 30-minute inactivity boundary."""
    now = timezone.now()
    visitor = request.session.get('validation_visitor')
    if not visitor:
        visitor = str(uuid.uuid4())
        request.session['validation_visitor'] = visitor
    visit = Visit.objects.filter(pk=request.session.get('validation_visit'), visitor=visitor, last_seen__gte=now-timedelta(minutes=30)).first()
    if not visit:
        source = re.sub(r'[^a-z0-9_-]', '', request.GET.get('utm_source', '').lower())[:80] or 'direct'
        campaign = re.sub(r'[^a-zA-Z0-9 _-]', '', request.GET.get('utm_campaign', ''))[:100]
        request.session['validation_source'] = source
        request.session['validation_campaign'] = campaign
        visit = Visit.objects.create(visitor=visitor, source=source, campaign=campaign)
        request.session['validation_visit'] = visit.pk
    participant = participant_for(request.user)
    Visit.objects.filter(pk=visit.pk).update(last_seen=now, participant=participant, landing_seen=visit.landing_seen or request.path=='/')
    if participant:
        Participant.objects.filter(pk=participant.pk).update(last_seen=now)

@transaction.atomic
def register(request, data):
    email = data['email'].strip().lower()
    name = data['full_name'].split(' ', 1)
    user = get_user_model().objects.create_user(username='mvp_'+hashlib.sha256(email.encode()).hexdigest(), email=email,
        password=data['password1'], first_name=name[0], last_name=name[1] if len(name)>1 else '')
    facility = Facility.objects.create(name=f"{data['organisation'][:145]} · Pilot workspace", slug='mvp-'+uuid.uuid4().hex, is_demo=True)
    Membership.objects.create(user=user, facility=facility, role=Membership.Role.FACILITY)
    source, campaign = attribution(request)
    participant = Participant.objects.create(user=user, facility=facility, role=data['role'], organisation=data['organisation'], source=source,
        campaign=campaign, whatsapp=data['whatsapp'], whatsapp_consent=data['whatsapp_consent'], research_consent_at=timezone.now())
    for code, name in [('A','Amina Yusuf'),('B','Ngozi Eze'),('C','Grace Adeyemi'),('D','Fatima Ibrahim')]:
        Patient.objects.create(facility=facility, reference='DEMO-'+code, display_name=name, is_synthetic=True)
    Visit.objects.filter(pk=request.session.get('validation_visit')).update(participant=participant)
    return user

def start_round(user, case):
    participant = participant_for(user)
    if participant and participant.facility_id == case.patient.facility_id:
        WalkthroughRound.objects.get_or_create(case=case, defaults={'participant':participant})

def round_progress(item):
    case = item.case
    quality = getattr(case, 'qualityassessment', None)
    attachment = getattr(case, 'attachment', None)
    assessment = getattr(case, 'aiassessment', None)
    failed = quality is not None and not quality.adequate
    steps = [('Start a case', True, 'case-detail'), ('Attach an ultrasound image', attachment is not None, 'image-upload'),
             ('Complete the quality check', quality is not None, 'quality-check')]
    if not failed:
        steps += [('Open the assessment and annotations', assessment is not None and item.assessment_viewed_at is not None, 'assessment-result'),
                  ('Record a care decision', case.clinical_decisions.exists(), 'clinician-review')]
    before_report = all(step[1] for step in steps)
    steps.append(('Download the quality report' if failed else 'Download the case report', before_report and item.report_requested_at is not None, 'case-report' if failed else 'case-report-stage'))
    done = sum(bool(step[1]) for step in steps)
    next_step = next((step for step in steps if not step[1]), None)
    return {'round':item, 'steps':[{'label':label, 'done':bool(complete)} for label,complete,_ in steps],
        'percent':round(done/len(steps)*100), 'done':done, 'total':len(steps), 'failed_quality':failed,
        'complete':done==len(steps), 'ready_for_report':before_report,
        'next_label':next_step[0] if next_step else 'Share your feedback',
        'next_url':reverse(next_step[2], args=[case.pk]) if next_step else reverse('round-feedback',args=[item.pk])}

def record_view(user, case, kind):
    item = WalkthroughRound.objects.filter(case=case, participant__user=user).select_related('case').first()
    if not item:
        return
    now = timezone.now()
    if kind == 'assessment' and not item.assessment_viewed_at:
        WalkthroughRound.objects.filter(pk=item.pk, assessment_viewed_at__isnull=True).update(assessment_viewed_at=now)
    elif kind == 'report' and round_progress(item)['ready_for_report']:
        WalkthroughRound.objects.filter(pk=item.pk, report_requested_at__isnull=True).update(report_requested_at=now, completed_at=now)

def lead_from_enquiry(request, enquiry):
    source, campaign = attribution(request)
    Lead.objects.get_or_create(enquiry=enquiry, defaults={'participant':participant_for(request.user), 'name':enquiry.name, 'email':enquiry.email,
        'organisation':enquiry.organisation, 'interest':enquiry.interest, 'message':enquiry.message, 'source':source, 'campaign':campaign, 'contact_consent_at':timezone.now()})

def round_queryset(participant):
    return WalkthroughRound.objects.filter(participant=participant).select_related('case__patient', 'case__attachment', 'case__qualityassessment', 'case__aiassessment', 'feedback').prefetch_related('case__clinical_decisions')
