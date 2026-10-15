from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from apps.dashboard.views import scoped_cases
from apps.workflow.reporting import report_data, render_report


@login_required
@require_GET
@never_cache
def case_report(request, pk):
    case=get_object_or_404(scoped_cases(request.user).select_related('patient__facility'),pk=pk)
    data=report_data(case)
    response=HttpResponse(render_report(data),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="VanaraOncoScan_{case.pk}_{data["revision"]}.pdf"'
    response['X-Content-Type-Options']='nosniff'
    response['Cache-Control']='private, no-store, max-age=0'
    from apps.validation.services import record_view
    record_view(request.user, case, 'report')
    from apps.workflow.models import CaseEvent
    if case.clinical_decisions.exists() and not CaseEvent.objects.filter(case=case, kind='CASE_REPORT_ISSUED').exists():
        CaseEvent.objects.create(case=case, actor=request.user, kind='CASE_REPORT_ISSUED', details={'revision': data['revision']})
    return response


@login_required
@require_GET
def report_stage(request, pk):
    """Final journey stage: the confirmed care plan summarised with the case report ready to download."""
    from django.shortcuts import redirect, render
    from apps.clinical.models import AIAssessment
    from apps.clinical.report_library import BIRADS, report_for_assessment
    from apps.workflow.teleradiology import resolve_simulated_reviews
    case = get_object_or_404(scoped_cases(request.user).select_related('patient__facility'), pk=pk)
    resolve_simulated_reviews(case)
    decision = case.clinical_decisions.select_related('actor').order_by('-created_at').first()
    if not decision:
        return redirect('clinician-review', pk=pk)
    assessment = AIAssessment.objects.filter(case=case).first()
    signed = case.specialistreview_set.filter(signed_at__isnull=False).select_related('reviewer').order_by('-signed_at').first()
    pending = case.specialistreview_set.filter(signed_at__isnull=True).exists()
    report = report_for_assessment(assessment, getattr(case, 'attachment', None)) if assessment else None
    if signed and signed.birads:
        birads = {'category': signed.birads, 'name': BIRADS.get(signed.birads, ('',))[0], 'source': 'Specialist second read'}
    elif report:
        birads = {'category': report['birads']['category'], 'name': report['birads']['name'],
                  'source': 'AI assessment' + (' (provisional)' if report['birads']['provisional'] else '')}
    else:
        birads = None
    plan = {
        'ROUTINE': ('Returned to routine care', 'Assessment completed with routine-care and return advice recorded.', 'routine'),
        'REFERRAL': ('Referral confirmed', 'Referral recorded for onward assessment.', 'referral'),
        'FOLLOW_UP': ('Follow-up scheduled', 'Interval reassessment booked in the follow-up list.', 'followup'),
        'SPECIALIST': ('Specialist review requested', 'A teleradiology second read has been requested. The report updates once it is signed.', 'specialist'),
    }[decision.action]
    followup = case.followup_set.order_by('due_date').first()
    from apps.validation.models import WalkthroughRound
    rnd = WalkthroughRound.objects.filter(case=case, participant__user=request.user).first()
    issued = case.caseevent_set.filter(kind='CASE_REPORT_ISSUED').exists()
    from apps.validation.models import Feedback
    feedback_round = rnd if rnd and not rnd.prompt_dismissed and not Feedback.objects.filter(round=rnd).exists() else None
    return render(request, 'case_report_ready.html', {
        'case': case, 'decision': decision, 'plan': plan, 'birads': birads, 'signed': signed, 'pending': pending,
        'referral': getattr(case, 'referral', None), 'followup': followup,
        'downloaded': bool(issued or (rnd and rnd.report_requested_at)), 'feedback_round': feedback_round,
    })
