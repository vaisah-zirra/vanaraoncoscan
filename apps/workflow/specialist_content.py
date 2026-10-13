from apps.clinical.models import AIAssessment, QualityAssessment
from apps.workflow.report_content import RESPONSES

def specialist_content(case):
    from apps.workflow.teleradiology import resolve_simulated_reviews
    resolve_simulated_reviews(case)
    quality = QualityAssessment.objects.filter(case=case).first()
    assessment = AIAssessment.objects.filter(case=case).first()
    outcome = 'QUALITY_FAILURE' if quality and not quality.adequate else assessment.disposition if assessment else 'PENDING'
    reviews = list(case.specialistreview_set.select_related('reviewer').order_by('requested_at', 'pk'))
    signed = [review for review in reviews if review.signed_at]
    response = RESPONSES.get(outcome, []) if case.patient.is_synthetic and case.patient.facility.is_demo else []
    attachment = getattr(case, 'attachment', None)
    if response and outcome != 'QUALITY_FAILURE':
        from apps.clinical.report_library import report_for_assessment
        report = report_for_assessment(assessment, attachment)
        if report and report.get('specialist'):
            response = list(report['specialist'])
    if not attachment:
        response = [(label, text.replace('The highlighted region provides a location for review; it does not establish the nature of the tissue or confirm malignancy.', 'The source image is not attached to this record; review the original examination before confirming the care plan.').replace('The highlighted region is retained for specialist review, but the workflow does not provide sufficient information to select a definitive care pathway.', 'The source image is not attached to this record, and the available information does not establish a definitive care pathway.')) for label, text in response]
    pending = next((review for review in reviews if not review.signed_at), None)
    return {'outcome': outcome, 'reviews': reviews, 'signed': signed, 'pending': pending, 'response': response}
