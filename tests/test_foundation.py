from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Patient, Case
from apps.clinical.services import start_case
from apps.workflow.models import CaseEvent

class FacilityIsolationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='test-only')
        self.own = Facility.objects.create(name='Own', slug='own')
        self.other = Facility.objects.create(name='Other', slug='other')
        self.membership = Membership.objects.create(user=self.user, facility=self.own, role=Membership.Role.FACILITY)
        self.patient = Patient.objects.create(facility=self.own, reference='A', display_name='Own synthetic patient')
        self.foreign = Patient.objects.create(facility=self.other, reference='B', display_name='Foreign synthetic patient')
    def test_start_case_records_event(self):
        case = start_case(user=self.user, patient_id=self.patient.pk)
        self.assertEqual(case.status, Case.Status.DRAFT)
        self.assertEqual(CaseEvent.objects.get(case=case).actor, self.user)
    def test_foreign_patient_rejected_without_writes(self):
        with self.assertRaises(PermissionDenied):
            start_case(user=self.user, patient_id=self.foreign.pk)
        self.assertFalse(Case.objects.exists())
        self.assertFalse(CaseEvent.objects.exists())
    def test_inactive_membership_rejected(self):
        self.membership.is_active = False
        self.membership.save()
        with self.assertRaises(PermissionDenied):
            start_case(user=self.user, patient_id=self.patient.pk)
    def test_reviewer_cannot_create_facility_cases(self):
        self.membership.role = Membership.Role.REVIEWER
        self.membership.save()
        with self.assertRaises(PermissionDenied):
            start_case(user=self.user, patient_id=self.patient.pk)
    def test_dashboard_excludes_other_facility(self):
        Case.objects.create(patient=self.foreign)
        start_case(user=self.user, patient_id=self.patient.pk)
        self.client.force_login(self.user)
        response = self.client.get('/workspace/')
        self.assertContains(response, 'Own synthetic patient')
        self.assertNotContains(response, 'Foreign synthetic patient')
    def test_login_required(self):
        self.assertRedirects(self.client.get('/workspace/'), '/accounts/login/?next=/workspace/')
