from io import BytesIO
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Patient, Case, QualityAssessment, AIAssessment
from apps.workflow.models import SpecialistReview, CaseEvent
from apps.workflow.reporting import report_data, render_report
from tempfile import TemporaryDirectory
from pathlib import Path
from hashlib import sha256
from PIL import Image
from django.test import override_settings
from django.core.files.base import ContentFile
from apps.clinical.models import UltrasoundSample, CaseImage


class CaseReportTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='reporter')
        self.other=get_user_model().objects.create_user(username='other')
        self.facility=Facility.objects.create(name='Demo clinic',slug='report-demo',is_demo=True)
        Membership.objects.create(user=self.user,facility=self.facility,role='FACILITY')
        patient=Patient.objects.create(facility=self.facility,reference='DEMO-R',display_name='Report patient')
        self.case=Case.objects.create(patient=patient,status='ASSESSED',presenting_concern='Recorded presenting history & clinical question <unchanged>.')
        self.quality=QualityAssessment.objects.create(case=self.case,adequate=True,reason='Technical quality passed.')
        self.assessment=AIAssessment.objects.create(case=self.case,disposition='SUSPICIOUS',finding='Recorded focal finding.')
        self.client.force_login(self.user)
        self.url=reverse('case-report',args=[self.case.pk])

    def parsed(self):
        reader=PdfReader(BytesIO(render_report(report_data(self.case))))
        return reader, '\n'.join(page.extract_text() for page in reader.pages)

    def test_pdf_download_is_private_and_does_not_mutate_case(self):
        before=self.case.updated_at
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertIn('attachment;',response['Content-Disposition'])
        self.assertIn('no-store',response['Cache-Control'])
        self.case.refresh_from_db(); self.assertEqual(before,self.case.updated_at)
        self.assertFalse(SpecialistReview.objects.exists()); self.assertFalse(CaseEvent.objects.exists())
        self.assertEqual(self.client.post(self.url).status_code,405)

    def test_every_page_has_notice_identity_and_page_number(self):
        reader,text=self.parsed()
        self.assertGreaterEqual(len(reader.pages),4)
        for index,page in enumerate(reader.pages,1):
            content=page.extract_text()
            self.assertIn('Not for clinical diagnosis',content)
            self.assertIn('DEMO-R',content)
            self.assertIn(f'Page {index} of {len(reader.pages)}',content)
        self.assertIn('Recorded presenting history & clinical question <unchanged>.',text)
        self.assertIn('Predefined specialist opinion',text)
        self.assertIn('No referral or follow-up plan has been confirmed',text)

    def test_failed_quality_suppresses_diagnostic_result(self):
        self.quality.adequate=False; self.quality.save()
        reader,text=self.parsed()
        self.assertIn('Assessment withheld',text)
        self.assertNotIn('Recorded focal finding.',text)
        self.assertIn('Diagnostic interpretation is withheld',text)

    def test_signed_review_takes_precedence(self):
        SpecialistReview.objects.create(case=self.case,reviewer=self.user,signed_at=timezone.now(),assessment='Recorded signed opinion.',recommendation='Recorded signed recommendation.')
        reader,text=self.parsed()
        self.assertIn('Recorded signed opinion.',text)
        self.assertNotIn('Predefined specialist opinion',text)

    def test_templates_never_apply_to_non_demo_facility(self):
        self.facility.is_demo=False; self.facility.save()
        self.case=Case.objects.select_related('patient__facility').get(pk=self.case.pk)
        self.assertEqual(report_data(self.case)['response'],[])

    def test_draft_reports_are_explicit_about_missing_assessment(self):
        self.assessment.delete(); self.quality.delete()
        reader,text=self.parsed()
        self.assertIn('Assessment not yet completed',text)
        self.assertIn('No image is attached',text)
        self.assertNotIn('Predefined specialist opinion',text)

    def test_cross_facility_and_anonymous_access(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.client.logout(); self.assertEqual(self.client.get(self.url).status_code,302)

    def test_revision_stable_until_content_changes(self):
        original=report_data(self.case)['revision']
        self.assertEqual(report_data(self.case)['revision'],original)
        self.case.presenting_concern='Updated history'
        self.assertNotEqual(report_data(self.case)['revision'],original)

    def test_long_notes_paginate_without_losing_content(self):
        self.case.presenting_concern=('Detailed history and previous assessment. '*300)+'END OF LONG HISTORY'
        reader,text=self.parsed()
        self.assertIn('END OF LONG HISTORY',text)
        self.assertIn('Report provenance',text)

    def test_verified_image_and_matching_annotation_only(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            buf=BytesIO(); Image.new('RGB',(200,200),'gray').save(buf,format='PNG'); raw=buf.getvalue()
            sample=UltrasoundSample.objects.create(code='report-image',label='Example',filename='example.png',byte_size=len(raw),width=200,height=200,sha256=sha256(raw).hexdigest(),licence_verified=True)
            sample.image.save('example.png',ContentFile(raw))
            CaseImage.objects.create(case=self.case,sample=sample,attached_by=self.user)
            self.assessment.details={'sample_id':sample.pk,'image_sha256':sample.sha256,'boxes':[{'x':10,'y':10,'width':40,'height':40}]}
            self.assessment.save()
            data=report_data(self.case)
            self.assertEqual(len(data['boxes']),1)
            self.assertEqual(data['image_bytes'],raw)
            reader=PdfReader(BytesIO(render_report(data)))
            self.assertTrue(any(len(page.images)>0 for page in reader.pages))
            self.assessment.details['sample_id']=sample.pk+1; self.assessment.save()
            self.assertEqual(report_data(self.case)['boxes'],[])
            Path(sample.image.path).write_bytes(b'changed')
            bad=report_data(self.case)
            self.assertIsNone(bad['image_bytes']); self.assertFalse(bad['boxes'])
            self.assertIn('Image unavailable',bad['image_note'])
