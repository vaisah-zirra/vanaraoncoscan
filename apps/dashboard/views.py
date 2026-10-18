from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from apps.clinical.models import Case, Patient, Study
from apps.clinical.services import start_case
from apps.organizations.models import Facility
from apps.workflow.models import CaseEvent, FollowUp
from core.permissions import facility_ids_for


def scoped_cases(user):
    return Case.objects.filter(patient__facility_id__in=facility_ids_for(user)).select_related('patient__facility', 'study', 'attachment__sample', 'aiassessment', 'qualityassessment')


@login_required
def dashboard(request):
    from core.permissions import reviewer_facility_ids
    if not facility_ids_for(request.user).exists() and reviewer_facility_ids(request.user).exists():
        return redirect('teleradiology-queue')
    all_cases = scoped_cases(request.user)
    counts = all_cases.aggregate(total=Count('pk'), review=Count('pk', filter=Q(status=Case.Status.REVIEW_PENDING)), referrals=Count('pk', filter=Q(status=Case.Status.REFERRAL_CONFIRMED)), followup=Count('pk', filter=Q(status=Case.Status.FOLLOW_UP)))
    q = request.GET.get('q', '').strip()[:120]
    status = request.GET.get('status', '')
    period = request.GET.get('period', '')
    sort = request.GET.get('sort', 'recent')
    cases = all_cases
    if q:
        cases = cases.filter(Q(patient__display_name__icontains=q) | Q(patient__reference__icontains=q) | Q(study__title__icontains=q))
    if status in Case.Status.values:
        cases = cases.filter(status=status)
    else:
        status = ''
    if period in ('7', '30', '90'):
        cases = cases.filter(created_at__gte=timezone.now()-timedelta(days=int(period)))
    else:
        period = ''
    ordering = {'recent': '-created_at', 'oldest': 'created_at', 'patient': 'patient__display_name'}
    if sort not in ordering:
        sort = 'recent'
    page = Paginator(cases.order_by(ordering[sort], 'pk'), 8).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'dashboard.html', {'counts': counts, 'case_count': counts['total'], 'cases': page,
        'first_run': counts['total'] == 0 and not (q or status or period),
        'page': page, 'querystring': params.urlencode(), 'q': q, 'status': status, 'period': period, 'sort': sort,
        'statuses': Case.Status.choices, 'facilities': Facility.objects.filter(pk__in=facility_ids_for(request.user)),
        'followups': FollowUp.objects.filter(case__in=all_cases, completed_at__isnull=True).select_related('case__patient').order_by('due_date')[:3],
        'events': CaseEvent.objects.filter(case__in=all_cases).select_related('case__patient').order_by('-created_at', '-pk')[:4]})


@login_required
def case_detail(request, pk):
    case = get_object_or_404(scoped_cases(request.user), pk=pk)
    from apps.workflow.teleradiology import resolve_simulated_reviews
    if resolve_simulated_reviews(case):
        case = get_object_or_404(scoped_cases(request.user), pk=pk)
    return render(request, 'case_detail.html', {'case': case, 'events': case.caseevent_set.all(), 'reviews': case.specialistreview_set.select_related('reviewer').all(), 'followups': case.followup_set.all(), 'can_edit_image': case.status in ('DRAFT', 'QUALITY_PENDING')})


@login_required
@require_http_methods(['GET', 'POST'])
def new_assessment(request):
    patients = Patient.objects.filter(facility_id__in=facility_ids_for(request.user), is_synthetic=True).order_by('display_name')
    from apps.clinical.case_content import CASE_CONTENT
    patient_contexts = {str(patient.pk): CASE_CONTENT.get(patient.reference.removeprefix('DEMO-'), {}).get('context', '') if patient.facility.is_demo else '' for patient in patients.select_related('facility')}
    error = ''
    if request.method == 'POST':
        patient = patients.filter(pk=request.POST.get('patient')).first() if request.POST.get('patient', '').isdigit() else None
        concern = request.POST.get('concern', '').strip()
        if not patient:
            error = 'Select a patient from your facility to continue.'
        elif len(concern) > 2000:
            error = 'Please keep the clinical context under 2,000 characters.'
        else:
            concern = concern or patient_contexts.get(str(patient.pk), '')
            case = start_case(user=request.user, patient_id=patient.pk, presenting_concern=concern)
            return redirect('image-upload', pk=case.pk)
    return render(request, 'new_assessment.html', {'patients': patients, 'error': error, 'concern': request.POST.get('concern', ''), 'patient_contexts': patient_contexts, 'facilities': Facility.objects.filter(pk__in=facility_ids_for(request.user)), 'selected_patient': request.POST.get('patient', '')})
