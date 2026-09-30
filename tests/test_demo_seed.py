from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.clinical.models import Case, AIAssessment, Patient, Study
from apps.organizations.models import Membership
from apps.workflow.models import Referral, SpecialistReview, FollowUp, CaseEvent


class DemoSeedTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(BASE_DIR=Path(self.temp.name))
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_seed_is_repeatable_and_preserves_passwords_and_case_changes(self):
        call_command('seed_demo', verbosity=0)
        user = get_user_model().objects.get(username='demo.facility')
        password_hash = user.password
        credentials = (Path(self.temp.name) / '.demo-credentials.txt').read_text()
        case = Case.objects.get(study__scenario=Study.Scenario.ROUTINE)
        case.status = Case.Status.COMPLETED
        case.save()
        events = CaseEvent.objects.count()
        call_command('seed_demo', verbosity=0)
        case.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(Case.objects.count(), 4)
        self.assertEqual(Patient.objects.count(), 4)
        self.assertEqual(case.status, Case.Status.COMPLETED)
        self.assertEqual(user.password, password_hash)
        self.assertEqual(CaseEvent.objects.count(), events)
        self.assertEqual((Path(self.temp.name) / '.demo-credentials.txt').read_text(), credentials)

    def test_scenarios_have_consistent_records_and_separate_roles(self):
        call_command('seed_demo', verbosity=0)
        failed = Case.objects.get(status=Case.Status.QUALITY_FAILURE)
        self.assertFalse(failed.qualityassessment.adequate)
        self.assertFalse(AIAssessment.objects.filter(case=failed).exists())
        self.assertEqual(Referral.objects.count(), 1)
        self.assertEqual(SpecialistReview.objects.filter(signed_at__isnull=True).count(), 1)
        self.assertEqual(FollowUp.objects.count(), 1)
        self.assertFalse(Study.objects.exclude(image='').exists())
        reviewer = get_user_model().objects.get(username='demo.reviewer')
        self.assertFalse(reviewer.is_superuser)
        self.assertFalse(reviewer.user_permissions.exists())
        self.assertEqual(Membership.objects.get(user=reviewer).role, Membership.Role.REVIEWER)
        self.client.force_login(reviewer)
        self.assertNotContains(self.client.get('/workspace/'), 'Amina Yusuf')
