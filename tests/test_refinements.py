from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.clinical.models import Case, Patient
from apps.clinical.case_content import CASE_CONTENT

class RefinementTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with override_settings(BASE_DIR=Path(self.temp.name)):
            call_command('seed_demo', verbosity=0)
        self.client.force_login(get_user_model().objects.get(username='demo.facility'))

    def test_history_is_available_and_falls_back_on_post(self):
        patient = Patient.objects.get(reference='DEMO-C')
        response = self.client.get(reverse('new-assessment'))
        self.assertEqual(response.context['patient_contexts'][str(patient.pk)], CASE_CONTENT['C']['context'])
        response = self.client.post(reverse('new-assessment'), {'patient': patient.pk, 'concern':''})
        self.assertEqual(response.status_code,302)
        self.assertEqual(Case.objects.filter(patient=patient).latest('created_at').presenting_concern, CASE_CONTENT['C']['context'])

    def test_current_step_and_pending_review_are_truthful(self):
        case = Case.objects.get(patient__reference='DEMO-C')
        response = self.client.get(reverse('case-detail',args=[case.pk]))
        self.assertContains(response,'aria-current="step"',count=1)
        self.assertContains(response,'No specialist opinion has been signed')
        self.assertContains(response,'Investigational AI · Not for clinical diagnosis')
        self.assertNotContains(response,'Synthetic scenario')
        self.assertNotContains(response,'Illustrative demo event')

    def test_refresh_preserves_user_edits(self):
        case = Case.objects.get(patient__reference='DEMO-A')
        case.presenting_concern = 'User-edited history'
        case.save()
        call_command('refresh_case_content', verbosity=0)
        case.refresh_from_db()
        self.assertEqual(case.presenting_concern,'User-edited history')

    def test_invalid_form_preserves_selected_patient(self):
        patient = Patient.objects.get(reference='DEMO-A')
        response = self.client.post(reverse('new-assessment'), {'patient':patient.pk,'concern':'x'*2001})
        self.assertEqual(response.context['selected_patient'], str(patient.pk))
