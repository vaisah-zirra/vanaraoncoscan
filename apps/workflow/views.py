import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_http_methods
from apps.dashboard.views import scoped_cases
from apps.clinical.models import AIAssessment, QualityAssessment
from apps.workflow.forms import ClinicalDecisionForm
from apps.workflow.services import confirm_decision

@login_required
@require_http_methods(['GET','POST'])
def clinician_review(request, pk):
    case = get_object_or_404(scoped_cases(request.user), pk=pk)
    from apps.workflow.teleradiology import resolve_simulated_reviews
    if request.method == 'GET' and resolve_simulated_reviews(case):
        case = get_object_or_404(scoped_cases(request.user), pk=pk)
    assessment = AIAssessment.objects.filter(case=case).first()
    quality = QualityAssessment.objects.filter(case=case).first()
    decisions = case.clinical_decisions.select_related('actor')
    eligible = bool(assessment and quality and quality.adequate and case.status in ('ASSESSED','REVIEW_PENDING','REVIEWED'))
    initial = {'safety_net':'Continue routine care in line with the agreed clinical plan. Arrange reassessment through the usual care team if symptoms persist or change, or if a new breast concern develops.', 'request_id':uuid.uuid4(), 'version':case.updated_at.isoformat(),
        'notes':'Assessment reviewed in the context of the recorded presenting history. The proposed care plan is documented below for clinician confirmation.',
        'reason': 'Please review the recorded breast concern and attached ultrasound, correlate the finding with the full clinical examination, and advise on further assessment and management.',
        'followup_notes':'Review the presenting concern and interval symptoms, reassess the clinical findings, and document whether further investigation or specialist input is required.'}
    form = ClinicalDecisionForm(request.POST if request.method == 'POST' else None, initial=initial)
    routine_available = bool(assessment and assessment.disposition == 'NON_SUSPICIOUS' and not case.specialistreview_set.filter(signed_at__isnull=True).exists())
    if not routine_available:
        form.fields['action'].choices = [choice for choice in form.fields['action'].choices if choice[0] != 'ROUTINE']
    if routine_available:
        suggestion = 'Consider routine-care completion when the history, examination and imaging agree and no unresolved concern remains. Follow-up, specialist review and referral remain available when indicated.'
    elif assessment and assessment.disposition == 'SUSPICIOUS':
        suggestion = 'Consider referral for further assessment. Confirm the destination and urgency after clinical review.'
    else:
        suggestion = 'Consider specialist review to resolve uncertainty before deciding the ongoing care plan.'
    from apps.clinical.report_library import report_for_assessment
    report = report_for_assessment(assessment, getattr(case, 'attachment', None)) if quality and quality.adequate else None
    if report:
        b = report['birads']
        lead = f"AI report: BI-RADS {b['category']}{' (provisional)' if b['provisional'] else ''} – {b['name']}. {report['recommendations'][0]}"
        suggestion = lead + ' ' + suggestion
    if request.method == 'POST' and form.is_valid():
        try:
            confirm_decision(user=request.user, case_id=pk, data=request.POST)
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
        else:
            messages.success(request, 'Clinical decision saved. The care plan and case timeline have been updated.')
            return redirect('clinician-review', pk=pk)
    return render(request, 'clinician_review.html', {'case':case, 'assessment':assessment, 'quality':quality,
        'result':assessment.details if assessment else {}, 'suggestion':suggestion, 'form':form, 'eligible':eligible, 'decisions':decisions,
        'reviews':case.specialistreview_set.select_related('reviewer'), 'followups':case.followup_set.all()})
