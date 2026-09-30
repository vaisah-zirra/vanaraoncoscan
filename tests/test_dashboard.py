from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Patient, Case

class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='facility')
        f = Facility.objects.create(name='Test facility', slug='test')
        other = Facility.objects.create(name='Other', slug='other')
        Membership.objects.create(user=self.user, facility=f, role=Membership.Role.FACILITY)
        self.patient = Patient.objects.create(facility=f, reference='DEMO-A', display_name='Amina Demo')
        self.foreign = Patient.objects.create(facility=other, reference='PRIVATE', display_name='Hidden Patient')
        self.case = Case.objects.create(patient=self.patient, status=Case.Status.REVIEW_PENDING)
        self.hidden = Case.objects.create(patient=self.foreign)
        self.client.force_login(self.user)
    def test_search_status_and_tenant_isolation(self):
        response = self.client.get('/workspace/', {'q': 'Amina', 'status': 'REVIEW_PENDING'})
        self.assertContains(response, 'Amina Demo')
        self.assertNotContains(response, 'Hidden Patient')
        self.assertEqual(response.context['counts']['total'], 1)
        self.assertEqual(self.client.get('/workspace/', {'q': 'Hidden'}).context['page'].paginator.count, 0)
        self.assertEqual(self.client.get('/workspace/', {'status': 'COMPLETED'}).context['page'].paginator.count, 0)
    def test_foreign_case_detail_is_not_disclosed(self):
        self.assertEqual(self.client.get(reverse('case-detail', args=[self.hidden.pk])).status_code, 404)
    def test_cannot_create_case_for_foreign_patient(self):
        response = self.client.post(reverse('new-assessment'), {'patient': self.foreign.pk})
        self.assertContains(response, 'Select a patient')
        self.assertEqual(Case.objects.count(), 2)
    def test_create_draft_and_open_detail(self):
        response = self.client.post(reverse('new-assessment'), {'patient': self.patient.pk, 'concern': 'Synthetic context'})
        case = Case.objects.get(presenting_concern='Synthetic context')
        self.assertRedirects(response, reverse('image-upload', args=[case.pk]))
        self.assertEqual(case.status, Case.Status.DRAFT)
    def test_pagination_and_invalid_sort(self):
        Case.objects.bulk_create([Case(patient=self.patient) for _ in range(9)])
        response = self.client.get('/workspace/', {'page': 2, 'sort': 'invalid'})
        self.assertEqual(len(response.context['page']), 2)
        self.assertEqual(response.context['sort'], 'recent')
