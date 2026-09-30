from django.core.exceptions import ValidationError
from django.db import transaction
from apps.clinical.models import Case, CaseImage, QualityAssessment, AIAssessment
from apps.clinical.assessment_engine import inspect_image, generate_result, profile_for, ENGINE_VERSION
from apps.workflow.models import CaseEvent, SpecialistReview
from core.permissions import require_facility_access


def locked_case(user, case_id):
    case = Case.objects.select_for_update().select_related('patient').get(pk=case_id)
    require_facility_access(user, case.patient.facility_id)
    return case


def current_attachment(case, expected_sample_id):
    attachment = CaseImage.objects.filter(case=case).select_related('sample').first()
    if not attachment:
        raise ValidationError('Attach an ultrasound image before continuing.')
    if str(attachment.sample_id) != str(expected_sample_id):
        raise ValidationError('The attachment changed. Reload the page before continuing.')
    if not attachment.sample.active or not attachment.sample.licence_verified:
        raise ValidationError('The attached image is no longer available for assessment.')
    return attachment


@transaction.atomic
def run_quality_check(*, user, case_id, expected_sample_id):
    case = locked_case(user, case_id)
    attachment = current_attachment(case, expected_sample_id)
    existing = QualityAssessment.objects.filter(case=case).first()
    if existing:
        if existing.details.get('sample_id') != attachment.sample_id:
            raise ValidationError('Existing quality records belong to another image; start a new assessment.')
        return existing
    if case.status != Case.Status.QUALITY_PENDING or AIAssessment.objects.filter(case=case).exists():
        raise ValidationError('The case is not awaiting image-quality review.')
    profile_for(attachment.sample)
    result = inspect_image(attachment.sample)
    quality = QualityAssessment.objects.create(case=case, adequate=result['adequate'], reason=result['reason'], details=result)
    case.status = Case.Status.QUALITY_PASSED if quality.adequate else Case.Status.QUALITY_FAILURE
    case.save(update_fields=['status','updated_at'])
    CaseEvent.objects.create(case=case, actor=user, kind='QUALITY_CHECK_COMPLETED', details={'adequate':quality.adequate,'sample_id':attachment.sample_id,'policy':result['policy']})
    if not quality.adequate:
        CaseEvent.objects.create(case=case, actor=user, kind='ASSESSMENT_PAUSED', details={'reason':'image_quality'})
    return quality


@transaction.atomic
def run_assessment(*, user, case_id, expected_sample_id):
    case = locked_case(user, case_id)
    attachment = current_attachment(case, expected_sample_id)
    existing = AIAssessment.objects.filter(case=case).first()
    if existing:
        if existing.details.get('sample_id') != attachment.sample_id:
            raise ValidationError('Existing results belong to another image; start a new assessment.')
        return existing
    quality = QualityAssessment.objects.filter(case=case).first()
    if not quality or not quality.adequate or case.status != Case.Status.QUALITY_PASSED:
        raise ValidationError('A successful image-quality check is required before assessment.')
    if quality.details.get('sample_id') != attachment.sample_id:
        raise ValidationError('The quality check does not match the attached image.')
    actual = inspect_image(attachment.sample)
    if not actual['adequate'] or actual['image_sha256'] != quality.details.get('image_sha256'):
        raise ValidationError('The image changed after its quality check. Start a new assessment with a verified image.')
    result = generate_result(attachment.sample)
    finding = '\n'.join(f"{label}: {result[key]}" for label,key in [('Findings','findings'),('Impression','impression'),('Recommended next step','recommendation')])
    assessment = AIAssessment.objects.create(case=case, disposition=result['disposition'], finding=finding, engine=ENGINE_VERSION, details=result)
    review_needed = result['disposition'] in (AIAssessment.Disposition.UNCERTAIN,AIAssessment.Disposition.REVIEW_REQUIRED)
    case.status = Case.Status.REVIEW_PENDING if review_needed else Case.Status.ASSESSED
    case.save(update_fields=['status','updated_at'])
    CaseEvent.objects.create(case=case, actor=user, kind='ASSESSMENT_COMPLETED', details={'sample_id':attachment.sample_id,'engine':ENGINE_VERSION,'disposition':result['disposition']})
    if review_needed:
        SpecialistReview.objects.create(case=case)
        CaseEvent.objects.create(case=case, actor=user, kind='SPECIALIST_REVIEW_REQUESTED', details={'reason':'uncertain_assessment'})
    return assessment
