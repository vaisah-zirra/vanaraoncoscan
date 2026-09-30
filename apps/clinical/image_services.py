from django.core.exceptions import ValidationError
from django.db import transaction
from apps.clinical.models import Case, CaseImage, UltrasoundSample
from apps.workflow.models import CaseEvent
from core.permissions import require_facility_access


def ensure_editable(case):
    if case.status not in (Case.Status.DRAFT, Case.Status.QUALITY_PENDING):
        raise ValidationError('This case has progressed beyond image selection. Start another assessment to try a different image.')
    # Guard records as well as status, so an inconsistent state cannot erase provenance.
    if hasattr(case, 'qualityassessment') or hasattr(case, 'aiassessment') or case.specialistreview_set.exists() or hasattr(case, 'referral'):
        raise ValidationError('Recorded assessment results must be preserved. Start a new assessment to select another image.')


@transaction.atomic
def attach_image(*, user, case_id, sample_id, expected_sample_id=None):
    case = Case.objects.select_for_update().select_related('patient').get(pk=case_id)
    require_facility_access(user, case.patient.facility_id)
    ensure_editable(case)
    current = CaseImage.objects.filter(case=case).first()
    actual = str(current.sample_id) if current else ''
    if expected_sample_id is not None and actual != str(expected_sample_id):
        raise ValidationError('The attachment changed in another window. Reload this page before continuing.')
    sample = UltrasoundSample.objects.filter(pk=sample_id, active=True, licence_verified=True).first()
    if not sample or not sample.image or not sample.image.storage.exists(sample.image.name):
        raise ValidationError('This image is unavailable. Please select another sample.')
    if current and current.sample_id == sample.pk:
        return current
    previous = current.sample_id if current else None
    attachment, _ = CaseImage.objects.update_or_create(case=case, defaults={'sample': sample, 'attached_by': user})
    case.status = Case.Status.QUALITY_PENDING
    case.save(update_fields=['status', 'updated_at'])
    CaseEvent.objects.create(case=case, actor=user, kind='IMAGE_REPLACED' if previous else 'IMAGE_ATTACHED',
        details={'sample_id': sample.pk, 'previous_sample_id': previous, 'sha256': sample.sha256})
    return attachment


@transaction.atomic
def remove_image(*, user, case_id, expected_sample_id=None):
    case = Case.objects.select_for_update().select_related('patient').get(pk=case_id)
    require_facility_access(user, case.patient.facility_id)
    ensure_editable(case)
    attachment = CaseImage.objects.filter(case=case).first()
    actual = str(attachment.sample_id) if attachment else ''
    if expected_sample_id is not None and actual != str(expected_sample_id):
        raise ValidationError('The attachment changed in another window. Reload this page before continuing.')
    if not attachment:
        return
    previous = attachment.sample_id
    attachment.delete()  # Removes the case association, never the library image or audit trail.
    case.status = Case.Status.DRAFT
    case.save(update_fields=['status', 'updated_at'])
    CaseEvent.objects.create(case=case, actor=user, kind='IMAGE_REMOVED', details={'sample_id': previous})
