from io import BytesIO
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader
from apps.clinical.models import Case, Patient
from apps.organizations.models import Facility
from apps.validation.models import Participant, WalkthroughRound, Feedback, Lead


def text_of(response):
    return ' '.join(' '.join((page.extract_text() or '').split()) for page in PdfReader(BytesIO(response.content)).pages)


class EvidenceExportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(username='owner', email='owner@example.test', password='Owner-test-241!')
        now = timezone.now()
        for i, (name, org, role, rating, useful, barriers, comment, intent) in enumerate([
            ('Ada Obi', 'Lagos Breast Clinic', 'Clinician', 5, 'AI', ['Cost', 'Evidence'], 'Very fast and easy to use. The report is clear.', 'Pilot'),
            ('Bola Ade', 'Kano Imaging Centre', 'Imaging', 4, 'Review', ['Integration'], 'Would need integration with our PACS and offline mode for poor internet.', 'Demo'),
            ('Chika Eze', 'Lagos Breast Clinic', 'Nursing', 3, 'Report', ['Training'], '', 'None'),
        ]):
            user = User.objects.create_user(username=f'p{i}', email=f'person{i}@example.test', first_name=name.split()[0], last_name=name.split()[1])
            facility = Facility.objects.create(name=f'F{i}', slug=f'f{i}', is_demo=True)
            participant = Participant.objects.create(user=user, facility=facility, role=role, organisation=org, source='whatsapp' if i else 'idice',
                                                     whatsapp='+2348000000' + str(i), whatsapp_consent=True, research_consent_at=now)
            patient = Patient.objects.create(facility=facility, reference=f'DEMO-{i}', display_name='Sample', is_synthetic=True)
            case = Case.objects.create(patient=patient, status='COMPLETED')
            rnd = WalkthroughRound.objects.create(participant=participant, case=case, assessment_viewed_at=now,
                                                  report_requested_at=now, completed_at=now)
            WalkthroughRound.objects.filter(pk=rnd.pk).update(started_at=now - timedelta(minutes=6 + i))
            Feedback.objects.create(round=rnd, rating=rating, most_useful=useful, barriers=barriers, suggestion=comment,
                                    intent=intent, contact_consent=intent != 'None', completion_at_submission=100)
        Lead.objects.create(name='Dr Funmi Bello', email='funmi@hospital.test', organisation='Abuja Teaching Hospital', role='Leadership',
                            interest='Pilot', message='We would like to pilot this in our radiology unit.', contact_consent_at=now, stage='Contacted',
                            next_action='Send pilot proposal')
        self.client.force_login(self.owner)

    def url(self, kind, **params):
        params.setdefault('days', 'all')
        return reverse('validation-export', args=[kind]) + '?' + '&'.join(f'{k}={v}' for k, v in params.items())

    def test_owner_only(self):
        self.client.force_login(get_user_model().objects.get(username='p0'))
        self.assertEqual(self.client.get(self.url('full')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url('full')).status_code, 302)

    def test_unknown_kind_is_404(self):
        self.assertEqual(self.client.get(self.url('everything')).status_code, 404)

    def test_full_report_is_rich_and_anonymised_by_default(self):
        response = self.client.get(self.url('full'))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('VanaraOncoScan_full_evidence_', response['Content-Disposition'])
        text = text_of(response)
        for expected in ['Validation evidence report', 'KEY FINDINGS', '3 participants registered', 'From first visit to next step',
                         'Walkthrough completion', 'Median time to complete', 'What participants told us', 'Rating distribution'.upper(),
                         'Most useful part of the platform', 'Factors that would most influence adoption', 'Summary of written feedback',
                         'Speed and ease of use', 'Integration with existing systems', 'Very fast and easy to use', 'Participant register',
                         'P-01', 'Interest and pipeline', 'E-01', 'Abuja Teaching Hospital', 'We would like to pilot this',
                         'How these figures were collected', 'Lagos Breast Clinic', 'Anonymised']:
            self.assertIn(expected, text, expected)
        self.assertIn('4.0 out of 5', text)
        for private in ['Ada', 'Obi', 'person0@example.test', '+23480', 'Funmi', 'funmi@hospital.test']:
            self.assertNotIn(private, text, private)

    def test_named_report_includes_contacts_and_internal_warning(self):
        response = self.client.get(self.url('full', identity='named'))
        self.assertIn('_INTERNAL.pdf', response['Content-Disposition'])
        text = text_of(response)
        for expected in ['Ada Obi', 'person0@example.test', 'Dr Funmi Bello', 'funmi@hospital.test', 'INTERNAL']:
            self.assertIn(expected, text, expected)

    def test_section_exports_and_filters(self):
        participants = text_of(self.client.get(self.url('participants')))
        self.assertIn('Participants and engagement', participants); self.assertIn('Participant register', participants)
        self.assertNotIn('Enquiry log', participants)
        feedback = text_of(self.client.get(self.url('feedback')))
        self.assertIn('Survey responses and feedback', feedback); self.assertIn('All written comments', feedback)
        self.assertNotIn('Participant register', feedback)
        interest = text_of(self.client.get(self.url('interest')))
        self.assertIn('Interest and pipeline', interest); self.assertIn('Send pilot proposal', interest)
        idice = text_of(self.client.get(self.url('participants', source='idice')))
        self.assertIn('1 participant registered', idice); self.assertIn('Source idice', idice.replace('SOURCE', 'Source'))

    def test_empty_cohort_still_renders(self):
        text = text_of(self.client.get(self.url('full', source='nobody')))
        self.assertIn('No participant activity has been recorded', text)

    def test_analytics_page_offers_exports(self):
        page = self.client.get(reverse('validation-dashboard') + '?days=all')
        self.assertContains(page, 'Export a validation report')
        self.assertContains(page, reverse('validation-export', args=['interest']))
        self.assertContains(page, 'Export PDF ↓', count=3)
