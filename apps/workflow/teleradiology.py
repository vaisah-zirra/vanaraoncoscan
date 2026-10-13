"""Teleradiology second-read: queue, structured review and signature."""
import json
import re
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_GET

from apps.clinical.models import Case, AIAssessment, QualityAssessment
from apps.clinical.presentation import assessment_display
from apps.clinical.report_library import report_for_assessment, BIRADS
from apps.workflow.models import SpecialistReview, CaseEvent, ClinicalDecision
from core.permissions import reviewer_facility_ids, require_reviewer_access

BIRADS_CHOICES = [('', 'Select category')] + [(code, f'BI-RADS {code} – {name}') for code, (name, _, _) in BIRADS.items()]


class ReviewForm(forms.Form):
    concordance = forms.ChoiceField(label='Concordance with the AI assessment', choices=SpecialistReview.Concordance.choices, widget=forms.RadioSelect)
    birads = forms.ChoiceField(label='Final BI-RADS category', choices=BIRADS_CHOICES)
    findings = forms.CharField(label='Findings', max_length=4000, widget=forms.Textarea(attrs={'rows': 4}))
    assessment = forms.CharField(label='Impression', max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))
    recommendation = forms.CharField(label='Recommendation', max_length=4000, widget=forms.Textarea(attrs={'rows': 4}))
    confirmed = forms.BooleanField(label='I have reviewed the image and AI report and sign this second-read report.')


def reviews_for(user):
    return (SpecialistReview.objects.filter(case__patient__facility_id__in=reviewer_facility_ids(user))
            .select_related('case__patient__facility', 'case__attachment__sample', 'case__aiassessment', 'case__qualityassessment', 'reviewer'))


def priority_for(case, report):
    category = (report or {}).get('birads', {}).get('category', '')
    if category in ('4B', '4C', '5'):
        return ('urgent', 'Urgent')
    if category in ('0', '4A'):
        return ('priority', 'Priority')
    return ('routine', 'Routine')


def ai_draft(report):
    """Turn the AI report's specialist wording into editable form values."""
    if not report or not report.get('specialist'):
        return {}
    parts = dict(report['specialist'])
    concordance = parts.get('Concordance with AI', '')
    match = re.search(r'BI-RADS (\d[ABC]?)', parts.get('Specialist impression', ''))
    recommendation = parts.get('Recommendation', '')
    if parts.get('Handover'):
        recommendation += '\n\nCommunication: ' + parts['Handover']
    return {'concordance': 'PARTIAL' if concordance.startswith('Partially') else 'DISAGREE' if concordance.startswith('Disagree') else 'AGREE',
            'birads': match.group(1) if match else report['birads']['category'],
            'findings': parts.get('Specialist findings', '') + ('\n\nComment on AI assessment: ' + concordance if concordance else ''),
            'assessment': parts.get('Specialist impression', ''),
            'recommendation': recommendation}


@transaction.atomic
def sign_review(*, user, review_id, data):
    review = SpecialistReview.objects.select_for_update().select_related('case__patient').get(pk=review_id)
    case = Case.objects.select_for_update().get(pk=review.case_id)
    require_reviewer_access(user, case.patient.facility_id)
    if review.signed_at:
        raise ValidationError('This review has already been signed.')
    if not AIAssessment.objects.filter(case=case).exists() or not QualityAssessment.objects.filter(case=case, adequate=True).exists():
        raise ValidationError('A completed assessment with a passed quality check is required before signing.')
    form = ReviewForm(data)
    if not form.is_valid():
        raise ValidationError('Complete every field and confirm before signing.')
    return _apply_signature(review, case, user, form.cleaned_data, simulated=False)


def _apply_signature(review, case, user, v, *, simulated):
    review.reviewer = user
    review.simulated = simulated
    review.concordance = v['concordance']
    review.agrees_with_ai = v['concordance'] == SpecialistReview.Concordance.AGREE
    review.birads = v['birads']
    review.findings = v['findings']
    review.assessment = v['assessment']
    review.recommendation = v['recommendation']
    review.signed_at = timezone.now()
    review.save()
    if case.status == Case.Status.REVIEW_PENDING and not SpecialistReview.objects.filter(case=case, signed_at__isnull=True).exists():
        case.status = Case.Status.REVIEWED
        case.save(update_fields=['status', 'updated_at'])
    CaseEvent.objects.create(case=case, actor=user, kind='SPECIALIST_REVIEW_SIGNED',
                             details={'review_id': review.pk, 'concordance': review.concordance, 'birads': review.birads, 'simulated': simulated})
    return review


# ---- Pilot: simulated teleradiologist -------------------------------------------------
SIM_USERNAME = 'vanara.teleradiology'
STAGES = [(0.0, 'queued', 'Queued for teleradiology'), (0.2, 'assigned', 'Radiologist assigned · Dr Adaeze Okonkwo'),
          (0.45, 'reading', 'Reading in progress'), (0.85, 'reporting', 'Finalising report')]


def simulated_reader():
    from django.contrib.auth import get_user_model
    user, created = get_user_model().objects.get_or_create(username=SIM_USERNAME, defaults={
        'first_name': 'Dr Adaeze', 'last_name': 'Okonkwo', 'email': 'teleradiology@vanara.invalid', 'is_active': False})
    if created:
        user.set_unusable_password(); user.save(update_fields=['password'])
    return user


def simulated_delay(review):
    from django.conf import settings
    low, high = settings.SIMULATED_TELERADIOLOGY_DELAY
    delay = low + (review.pk * 7919) % (max(high - low, 0) + 1)
    # Reviews routed automatically at assessment time start their clock once the result is on screen
    # (the processing animation takes ~7 s); clinician-requested reviews start immediately.
    if low and not ClinicalDecision.objects.filter(case_id=review.case_id, action='SPECIALIST').exists():
        delay += 7
    return delay


def simulation_applies(review):
    from django.conf import settings
    case = review.case
    return bool(settings.SIMULATED_TELERADIOLOGY and not review.signed_at and case.patient.facility.is_demo
                and QualityAssessment.objects.filter(case=case, adequate=True).exists())


def simulated_status(review):
    """Progress of a pending simulated read: (stage key, label, seconds remaining)."""
    delay = simulated_delay(review)
    elapsed = (timezone.now() - review.requested_at).total_seconds()
    fraction = min(1.0, elapsed / delay) if delay else 1.0
    key, label = next((k, l) for f, k, l in reversed(STAGES) if fraction >= f)
    return key, label, max(0, round(delay - elapsed))


def resolve_simulated_reviews(case):
    """Sign any due simulated second reads for this case; returns the number signed."""
    from django.conf import settings
    if not settings.SIMULATED_TELERADIOLOGY or not case.patient.facility.is_demo:
        return 0
    signed = 0
    for review in SpecialistReview.objects.filter(case=case, signed_at__isnull=True).select_related('case__patient__facility'):
        if not simulation_applies(review) or simulated_status(review)[2] > 0:
            continue
        assessment = AIAssessment.objects.filter(case=case).first()
        draft = ai_draft(report_for_assessment(assessment, getattr(case, 'attachment', None)) if assessment else None)
        if not draft:
            continue
        with transaction.atomic():
            locked = SpecialistReview.objects.select_for_update().get(pk=review.pk)
            if locked.signed_at:
                continue
            locked_case = Case.objects.select_for_update().get(pk=case.pk)
            _apply_signature(locked, locked_case, simulated_reader(), draft, simulated=True)
            signed += 1
    if signed:
        case.refresh_from_db()
    return signed


@login_required
@require_GET
def review_status(request, pk):
    from django.http import JsonResponse, Http404
    from core.permissions import facility_ids_for
    allowed = set(facility_ids_for(request.user)) | set(reviewer_facility_ids(request.user))
    review = SpecialistReview.objects.select_related('case__patient__facility', 'reviewer').filter(pk=pk, case__patient__facility_id__in=allowed).first()
    if not review:
        raise Http404
    resolve_simulated_reviews(review.case)
    review.refresh_from_db()
    if review.signed_at:
        return JsonResponse({'signed': True, 'reviewer': review.reviewer.get_full_name() if review.reviewer else '', 'birads': review.birads})
    if simulation_applies(review):
        key, label, remaining = simulated_status(review)
        return JsonResponse({'signed': False, 'stage': key, 'label': label, 'remaining': remaining})
    return JsonResponse({'signed': False, 'stage': 'queued', 'label': 'Queued for teleradiology', 'remaining': None})


@login_required
@require_GET
def review_queue(request):
    if not reviewer_facility_ids(request.user):
        return redirect('dashboard')
    tab = 'signed' if request.GET.get('tab') == 'signed' else 'pending'
    base = reviews_for(request.user)
    for case in {r.case for r in base.filter(signed_at__isnull=True)}:
        resolve_simulated_reviews(case)
    pending = base.filter(signed_at__isnull=True)
    signed = base.filter(signed_at__isnull=False)
    rows = []
    for review in (signed.order_by('-signed_at') if tab == 'signed' else pending.order_by('requested_at'))[:100]:
        case = review.case
        assessment = getattr(case, 'aiassessment', None)
        report = report_for_assessment(assessment, getattr(case, 'attachment', None)) if assessment else None
        rows.append({'review': review, 'case': case, 'display': assessment_display(case), 'report': report,
                     'priority': priority_for(case, report)})
    if tab == 'pending':
        order = {'urgent': 0, 'priority': 1, 'routine': 2}
        rows.sort(key=lambda r: order[r['priority'][0]])
    return render(request, 'teleradiology/queue.html', {'rows': rows, 'tab': tab,
        'pending_count': pending.count(), 'signed_count': signed.count()})


@login_required
@require_http_methods(['GET', 'POST'])
def review_detail(request, pk):
    review = get_object_or_404(reviews_for(request.user), pk=pk)
    if request.method == 'GET' and resolve_simulated_reviews(review.case):
        review.refresh_from_db()
    case = review.case
    assessment = getattr(case, 'aiassessment', None)
    attachment = getattr(case, 'attachment', None)
    report = report_for_assessment(assessment, attachment) if assessment else None
    draft = ai_draft(report)
    form = ReviewForm(request.POST or None, initial={'birads': (report or {}).get('birads', {}).get('category', '')})
    if request.method == 'POST':
        if form.is_valid():
            try:
                sign_review(user=request.user, review_id=review.pk, data=request.POST)
            except ValidationError as exc:
                form.add_error(None, exc.messages[0])
            else:
                messages.success(request, 'Second-read report signed. The referring facility can now see your review.')
                return redirect('teleradiology-review', pk=review.pk)
    question = ClinicalDecision.objects.filter(case=case, action='SPECIALIST').order_by('-created_at').values_list('details', flat=True).first()
    return render(request, 'teleradiology/review.html', {
        'review': review, 'case': case, 'assessment': assessment, 'result': assessment.details if assessment else {},
        'report': report, 'display': assessment_display(case), 'form': form, 'draft_json': json.dumps(draft),
        'has_draft': bool(draft), 'question': (question or {}).get('reason', ''), 'priority': priority_for(case, report),
        'reason': 'AI confidence below the teleradiology threshold' if assessment and assessment.disposition in ('UNCERTAIN', 'REVIEW_REQUIRED') and not question else 'Second read requested by the referring clinician'})
