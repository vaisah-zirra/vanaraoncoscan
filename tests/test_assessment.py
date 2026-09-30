import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings, Client
from django.conf import settings
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from PIL import Image
from io import BytesIO
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Case, Patient, UltrasoundSample, AIAssessment, QualityAssessment
from apps.clinical.image_services import attach_image
from apps.clinical.assessment_services import run_quality_check, run_assessment
from apps.clinical.assessment_engine import generate_result
from apps.workflow.models import CaseEvent, SpecialistReview

class AssessmentTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_ROOT=self.temp.name); self.override.enable(); self.addCleanup(self.override.disable)
        self.user=get_user_model().objects.create_user(username='assessor')
        self.other=get_user_model().objects.create_user(username='outsider')
        facility=Facility.objects.create(name='Assessment centre',slug='assessment')
        Membership.objects.create(user=self.user,facility=facility,role=Membership.Role.FACILITY)
        self.patient=Patient.objects.create(facility=facility,reference='T-1',display_name='Patient')
        self.case=Case.objects.create(patient=self.patient)
        self.samples={}
        for entry in json.loads((settings.BASE_DIR/'library_assets/manifest.json').read_text()):
            data=(settings.BASE_DIR/'library_assets'/entry['filename']).read_bytes()
            with Image.open(BytesIO(data)) as im: width,height=im.size
            sample=UltrasoundSample.objects.create(code=entry['code'],label=entry['label'],filename=entry['filename'],
                byte_size=len(data),width=width,height=height,sha256=hashlib.sha256(data).hexdigest(),source_url=entry['source_url'],
                source_filename=entry['source_filename'],attribution=entry['attribution'],licence_url=entry['licence_url'],licence_verified=True)
            sample.image.save(entry['filename'],ContentFile(data))
            self.samples[entry['code']]=sample
        self.client.force_login(self.user)

    def attach(self,code):
        sample=self.samples[code]
        attach_image(user=self.user,case_id=self.case.pk,sample_id=sample.pk)
        return sample

    def quality(self,sample):
        return run_quality_check(user=self.user,case_id=self.case.pk,expected_sample_id=sample.pk)

    def assess(self,sample):
        return run_assessment(user=self.user,case_id=self.case.pk,expected_sample_id=sample.pk)

    def test_suspicious_path_has_source_box_and_snapshot(self):
        sample=self.attach('sample-05')
        self.assertTrue(self.quality(sample).adequate)
        result=self.assess(sample)
        self.assertEqual(result.disposition,'SUSPICIOUS')
        self.assertTrue(result.details['boxes'])
        self.assertEqual(result.details['image_sha256'],sample.sha256)
        self.assertEqual(result.details['source_label'],'malignant')
        self.assertFalse(SpecialistReview.objects.filter(case=self.case).exists())
        response=self.client.get(reverse('assessment-result',args=[self.case.pk]))
        self.assertContains(response,'Show annotations')
        self.assertContains(response,'Clinician confirmation required')

    def test_low_resolution_stops_without_ai_result(self):
        sample=self.attach('sample-06')
        quality=self.quality(sample)
        self.assertFalse(quality.adequate)
        with self.assertRaises(ValidationError): self.assess(sample)
        self.assertFalse(AIAssessment.objects.filter(case=self.case).exists())
        self.case.refresh_from_db(); self.assertEqual(self.case.status,'QUALITY_FAILURE')
        self.assertContains(self.client.get(reverse('quality-check',args=[self.case.pk])),'A better image is needed')

    def test_routine_result_does_not_invent_a_box(self):
        sample=self.attach('sample-02'); self.quality(sample)
        result=self.assess(sample)
        self.assertEqual(result.disposition,'NON_SUSPICIOUS')
        self.assertEqual(result.details['boxes'],[])

    def test_uncertain_creates_one_pending_specialist_review(self):
        sample=self.attach('sample-04'); self.quality(sample)
        result=self.assess(sample); self.assess(sample)
        self.assertEqual(result.disposition,'UNCERTAIN')
        self.assertEqual(SpecialistReview.objects.filter(case=self.case,signed_at__isnull=True).count(),1)
        self.case.refresh_from_db(); self.assertEqual(self.case.status,'REVIEW_PENDING')

    def test_repeated_submissions_are_idempotent(self):
        sample=self.attach('sample-01'); self.quality(sample); self.quality(sample); self.assess(sample); self.assess(sample)
        self.assertEqual(QualityAssessment.objects.filter(case=self.case).count(),1)
        self.assertEqual(AIAssessment.objects.filter(case=self.case).count(),1)
        self.assertEqual(CaseEvent.objects.filter(case=self.case,kind='ASSESSMENT_COMPLETED').count(),1)

    def test_no_assessment_without_quality_or_for_stale_attachment(self):
        sample=self.attach('sample-01')
        with self.assertRaises(ValidationError): self.assess(sample)
        with self.assertRaises(ValidationError): run_quality_check(user=self.user,case_id=self.case.pk,expected_sample_id=self.samples['sample-02'].pk)

    def test_changed_bytes_block_processing_after_quality(self):
        sample=self.attach('sample-01'); self.quality(sample)
        Path(sample.image.path).write_bytes(b'changed')
        with self.assertRaises(ValidationError): self.assess(sample)
        self.assertFalse(AIAssessment.objects.filter(case=self.case).exists())

    def test_cross_facility_and_csrf_protection(self):
        sample=self.attach('sample-01')
        with self.assertRaises(PermissionDenied): run_quality_check(user=self.other,case_id=self.case.pk,expected_sample_id=sample.pk)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('quality-check',args=[self.case.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('assessment-result',args=[self.case.pk])).status_code,404)
        secure=Client(enforce_csrf_checks=True); secure.force_login(self.user)
        self.assertEqual(secure.post(reverse('quality-check',args=[self.case.pk]),{'action':'quality','sample':sample.pk}).status_code,403)

    def test_every_source_box_is_inside_its_image(self):
        for code in ('sample-01','sample-02','sample-03','sample-04','sample-05'):
            result=generate_result(self.samples[code])
            for box in result['boxes']:
                self.assertGreaterEqual(box['x'],0); self.assertGreaterEqual(box['y'],0)
                self.assertLessEqual(box['x']+box['width'],result['width'])
                self.assertLessEqual(box['y']+box['height'],result['height'])

    def test_fetch_response_and_no_get_side_effects(self):
        sample=self.attach('sample-01'); url=reverse('quality-check',args=[self.case.pk])
        self.client.get(url)
        self.assertFalse(QualityAssessment.objects.filter(case=self.case).exists())
        response=self.client.post(url,{'action':'quality','sample':sample.pk},HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code,200); self.assertIn('redirect',response.json())
