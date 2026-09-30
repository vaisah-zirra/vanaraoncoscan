from hashlib import sha256
from io import BytesIO
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from PIL import Image
from pypdf import PdfReader
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Patient, Case, QualityAssessment, AIAssessment, UltrasoundSample, CaseImage
from apps.clinical.presentation import assessment_display
from apps.workflow.reporting import report_data,render_report


class ConfidenceDisplayTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_ROOT=self.temp.name); self.override.enable(); self.addCleanup(self.override.disable)
        self.user=get_user_model().objects.create_user(username='display')
        self.facility=Facility.objects.create(name='Demo',slug='display',is_demo=True)
        Membership.objects.create(facility=self.facility,user=self.user,role='FACILITY')
        patient=Patient.objects.create(facility=self.facility,reference='DEMO',display_name='Display patient')
        self.case=Case.objects.create(patient=patient,status='ASSESSED')
        self.quality=QualityAssessment.objects.create(case=self.case,adequate=True,reason='Passed')
        buf=BytesIO(); Image.new('RGB',(200,200),'gray').save(buf,format='PNG'); raw=buf.getvalue()
        self.sample=UltrasoundSample.objects.create(code='sample-05',label='Sample',filename='sample.png',byte_size=len(raw),width=200,height=200,sha256=sha256(raw).hexdigest(),licence_verified=True)
        self.sample.image.save('sample.png',ContentFile(raw))
        CaseImage.objects.create(case=self.case,sample=self.sample,attached_by=self.user)
        self.assessment=AIAssessment.objects.create(case=self.case,disposition='SUSPICIOUS',finding='Example finding',details={'sample_id':self.sample.pk,'image_sha256':self.sample.sha256,'width':200,'height':200})
        self.client.force_login(self.user)

    def fresh(self): return Case.objects.get(pk=self.case.pk)

    def test_matching_demo_has_90_percent_and_ten_percent_gap(self):
        display=assessment_display(self.fresh())
        self.assertEqual(display['score'],90); self.assertEqual(display['remaining'],10)
        self.assertEqual(display['label'],'Highly suggestive of malignancy')
        response=self.client.get(reverse('assessment-result',args=[self.case.pk]))
        self.assertContains(response,'stroke-dasharray="90 10"')
        self.assertContains(response,'Demo score')
        self.assertContains(response,'not confidence thresholds')

    def test_pdf_matches_ui_and_contains_legend(self):
        data=report_data(self.fresh())
        self.assertEqual(data['display'],assessment_display(self.fresh()))
        text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_report(data))).pages)
        for expected in ['90%','Demo score','Highly suggestive of malignancy','Benign-appearing finding','Assessment colours & interpretation','not cancer probabilities']:
            self.assertIn(expected,text)

    def test_failed_quality_and_pending_never_get_scores(self):
        self.quality.adequate=False; self.quality.save()
        self.assertFalse(assessment_display(self.fresh())['has_score'])
        self.assertEqual(assessment_display(self.fresh())['key'],'unavailable')
        self.quality.delete(); self.assessment.delete()
        self.assertEqual(assessment_display(self.fresh())['key'],'pending')

    def test_non_demo_and_mismatched_results_never_get_scores(self):
        self.facility.is_demo=False; self.facility.save()
        self.assertFalse(assessment_display(self.fresh())['has_score'])
        self.facility.is_demo=True; self.facility.save()
        self.assessment.details['image_sha256']='mismatch'; self.assessment.save()
        self.assertFalse(assessment_display(self.fresh())['has_score'])

    def test_non_suspicious_normal_sample_does_not_invent_benign_lesion(self):
        self.sample.code='sample-02'; self.sample.save()
        self.assessment.disposition='NON_SUSPICIOUS'; self.assessment.save()
        self.assertEqual(assessment_display(self.fresh())['label'],'No suspicious finding identified')

    def test_case_review_and_dashboard_include_display(self):
        for route,args in [('case-detail',[self.case.pk]),('clinician-review',[self.case.pk]),('dashboard',[])]:
            response=self.client.get(reverse(route,args=args))
            self.assertContains(response,'Highly suggestive of malignancy')
            self.assertContains(response,'Demo score')
