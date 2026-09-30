from tempfile import TemporaryDirectory
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Case, Patient, UltrasoundSample, CaseImage, QualityAssessment
from apps.clinical.image_services import attach_image, remove_image
from apps.workflow.models import CaseEvent


class ImageAttachmentTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.temp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = get_user_model().objects.create_user(username='imaging')
        facility = Facility.objects.create(name='Imaging', slug='imaging')
        other = Facility.objects.create(name='Other', slug='other')
        Membership.objects.create(user=self.user, facility=facility, role=Membership.Role.FACILITY)
        self.patient = Patient.objects.create(facility=facility, reference='001', display_name='Patient One')
        self.case = Case.objects.create(patient=self.patient)
        self.foreign = Case.objects.create(patient=Patient.objects.create(facility=other, reference='002', display_name='Other Patient'))
        self.sample = self.make_sample('sample-01')
        self.second = self.make_sample('sample-02')
        self.client.force_login(self.user)

    def make_sample(self, code):
        sample = UltrasoundSample.objects.create(code=code,label=code,filename=code+'.png',byte_size=8,width=1,height=1,
            sha256='0'*64,source_url='https://example.org/dataset',source_filename='original.png',attribution='Test',
            licence_url='https://creativecommons.org/licenses/by/4.0/',licence_verified=True)
        sample.image.save(code+'.png',ContentFile(b'\x89PNG\r\n\x1a\n'))
        return sample

    def test_attach_replace_remove_and_timeline(self):
        attach_image(user=self.user,case_id=self.case.pk,sample_id=self.sample.pk,expected_sample_id='')
        attach_image(user=self.user,case_id=self.case.pk,sample_id=self.sample.pk)
        self.assertEqual(CaseEvent.objects.filter(case=self.case).count(),1)
        attach_image(user=self.user,case_id=self.case.pk,sample_id=self.second.pk,expected_sample_id=str(self.sample.pk))
        self.case.refresh_from_db()
        self.assertEqual(self.case.status,Case.Status.QUALITY_PENDING)
        self.assertEqual(self.case.attachment.sample,self.second)
        remove_image(user=self.user,case_id=self.case.pk,expected_sample_id=str(self.second.pk))
        self.case.refresh_from_db()
        self.assertEqual(self.case.status,Case.Status.DRAFT)
        self.assertEqual(list(CaseEvent.objects.filter(case=self.case).values_list('kind',flat=True)),['IMAGE_ATTACHED','IMAGE_REPLACED','IMAGE_REMOVED'])
        self.assertTrue(self.sample.image.storage.exists(self.sample.image.name))

    def test_cross_facility_read_and_write_denied(self):
        with self.assertRaises(PermissionDenied):
            attach_image(user=self.user,case_id=self.foreign.pk,sample_id=self.sample.pk)
        url=reverse('image-upload',args=[self.foreign.pk])
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.post(url,{'action':'attach','sample':self.sample.pk}).status_code,404)
        self.assertFalse(CaseImage.objects.filter(case=self.foreign).exists())

    def test_unlicensed_and_missing_files_are_rejected(self):
        self.sample.licence_verified=False
        self.sample.save()
        with self.assertRaises(ValidationError):
            attach_image(user=self.user,case_id=self.case.pk,sample_id=self.sample.pk)
        self.second.image.storage.delete(self.second.image.name)
        with self.assertRaises(ValidationError):
            attach_image(user=self.user,case_id=self.case.pk,sample_id=self.second.pk)

    def test_results_and_stale_page_are_protected(self):
        attach_image(user=self.user,case_id=self.case.pk,sample_id=self.sample.pk)
        with self.assertRaises(ValidationError):
            attach_image(user=self.user,case_id=self.case.pk,sample_id=self.second.pk,expected_sample_id='')
        with self.assertRaises(ValidationError):
            remove_image(user=self.user,case_id=self.case.pk,expected_sample_id='')
        QualityAssessment.objects.create(case=self.case,adequate=True,reason='Completed')
        with self.assertRaises(ValidationError):
            remove_image(user=self.user,case_id=self.case.pk)
        self.assertTrue(CaseImage.objects.filter(case=self.case,sample=self.sample).exists())

    def test_upload_page_and_neutral_asset_response(self):
        url=reverse('image-upload',args=[self.case.pk])
        response=self.client.get(url)
        self.assertContains(response,'Choose images')
        response=self.client.post(url,{'action':'attach','sample':self.sample.pk,'expected_sample':''},follow=True)
        self.assertContains(response,'Image attached and saved')
        self.assertContains(response,'Choose another image')
        image=self.client.get(reverse('sample-image',args=[self.sample.pk]))
        self.assertEqual(image.status_code,200)
        self.assertEqual(image['Content-Type'],'image/png')
        image.close()

    def test_anonymous_and_csrf_protection(self):
        self.assertEqual(Client().get(reverse('sample-image',args=[self.sample.pk])).status_code,302)
        secure=Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.post(reverse('image-upload',args=[self.case.pk]),{'action':'attach','sample':self.sample.pk}).status_code,403)

    def test_try_another_keeps_original_records(self):
        self.case.status=Case.Status.ASSESSED
        self.case.save()
        response=self.client.post(reverse('try-another-sample',args=[self.case.pk]))
        self.assertEqual(response.status_code,302)
        self.assertEqual(Case.objects.filter(patient=self.patient).count(),2)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status,Case.Status.ASSESSED)

    def test_inactive_member_cannot_read_library(self):
        Membership.objects.filter(user=self.user).update(is_active=False)
        self.assertEqual(self.client.get(reverse('sample-image',args=[self.sample.pk])).status_code,403)

    def test_previously_selected_survives_replacement(self):
        attach_image(user=self.user,case_id=self.case.pk,sample_id=self.sample.pk)
        attach_image(user=self.user,case_id=self.case.pk,sample_id=self.second.pk)
        response=self.client.get(reverse('image-upload',args=[self.case.pk]))
        self.assertTrue(all(sample['previously_tried'] for sample in response.context['samples']))
