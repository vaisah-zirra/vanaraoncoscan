from io import BytesIO
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader
from apps.clinical.models import Case
from apps.organizations.models import Facility, Membership
from apps.workflow.models import SpecialistReview, CaseEvent
from tests import test_assessment as base

SIGN = {'concordance': 'PARTIAL', 'birads': '2', 'findings': 'Oval circumscribed lesion in subcutaneous fat.',
        'assessment': 'Subcutaneous lipoma. BI-RADS 2.', 'recommendation': 'Routine care.', 'confirmed': 'on'}


class TeleradiologyTests(TestCase):
    setUp = base.AssessmentTests.setUp
    attach = base.AssessmentTests.attach
    quality = base.AssessmentTests.quality
    assess = base.AssessmentTests.assess

    def uncertain_case(self):
        sample = self.attach('sample-04'); self.quality(sample); self.assess(sample)
        return SpecialistReview.objects.get(case=self.case)

    def test_low_confidence_case_is_queued_and_signing_returns_report(self):
        self.case.patient.facility.is_demo = True; self.case.patient.facility.save()
        review = self.uncertain_case()
        queue = self.client.get(reverse('teleradiology-queue'))
        self.assertContains(queue, self.case.patient.display_name)
        self.assertContains(queue, 'Priority')
        page = self.client.get(reverse('teleradiology-review', args=[review.pk]))
        self.assertContains(page, 'AI confidence below the teleradiology threshold')
        self.assertContains(page, 'Start from AI-drafted wording')
        response = self.client.post(reverse('teleradiology-review', args=[review.pk]), SIGN)
        self.assertEqual(response.status_code, 302)
        review.refresh_from_db(); self.case.refresh_from_db()
        self.assertTrue(review.signed_at); self.assertEqual(review.concordance, 'PARTIAL'); self.assertFalse(review.agrees_with_ai)
        self.assertEqual(review.birads, '2'); self.assertEqual(self.case.status, Case.Status.REVIEWED)
        self.assertTrue(CaseEvent.objects.filter(case=self.case, kind='SPECIALIST_REVIEW_SIGNED').exists())
        detail = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertContains(detail, 'Signed second read'); self.assertContains(detail, 'Final BI-RADS 2')
        text = ''.join(p.extract_text() for p in PdfReader(BytesIO(self.client.get(reverse('case-report', args=[self.case.pk])).content)).pages)
        self.assertIn('Signed teleradiology review', text); self.assertIn('Subcutaneous lipoma', text)
        again = self.client.post(reverse('teleradiology-review', args=[review.pk]), SIGN)
        self.assertEqual(again.status_code, 200)  # already signed: shows the signed report, no second signature
        self.assertEqual(CaseEvent.objects.filter(kind='SPECIALIST_REVIEW_SIGNED').count(), 1)

    def test_pending_review_shows_awaiting_state(self):
        self.case.patient.facility.is_demo = True; self.case.patient.facility.save()
        self.uncertain_case()
        detail = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertContains(detail, 'Awaiting teleradiologist')

    def test_incomplete_form_is_not_signed(self):
        self.case.patient.facility.is_demo = True; self.case.patient.facility.save()
        review = self.uncertain_case()
        data = dict(SIGN); data.pop('confirmed')
        response = self.client.post(reverse('teleradiology-review', args=[review.pk]), data)
        self.assertContains(response, 'The review has not been signed')
        review.refresh_from_db(); self.assertIsNone(review.signed_at)

    def test_facility_user_cannot_review_outside_demo_and_outsider_gets_404(self):
        review = self.uncertain_case()  # facility is not a demo workspace
        self.assertEqual(self.client.get(reverse('teleradiology-review', args=[review.pk])).status_code, 404)
        self.assertRedirects(self.client.get(reverse('teleradiology-queue')), reverse('dashboard'))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('teleradiology-review', args=[review.pk])).status_code, 404)

    def test_specialist_reviewer_can_sign_and_lands_on_queue(self):
        review = self.uncertain_case()
        reviewer = get_user_model().objects.create_user(username='radiologist', first_name='Tunde', last_name='Okafor')
        Membership.objects.create(user=reviewer, facility=self.case.patient.facility, role=Membership.Role.REVIEWER)
        self.client.force_login(reviewer)
        self.assertRedirects(self.client.get(reverse('dashboard')), reverse('teleradiology-queue'))
        self.client.post(reverse('teleradiology-review', args=[review.pk]), SIGN)
        review.refresh_from_db(); self.assertEqual(review.reviewer, reviewer)


from django.test import override_settings
from datetime import timedelta
from django.utils import timezone


class SimulatedTeleradiologyTests(TestCase):
    setUp = base.AssessmentTests.setUp
    attach = base.AssessmentTests.attach
    quality = base.AssessmentTests.quality
    assess = base.AssessmentTests.assess

    def pending(self, demo=True):
        self.case.patient.facility.is_demo = demo; self.case.patient.facility.save()
        sample = self.attach('sample-04'); self.quality(sample); self.assess(sample)
        return SpecialistReview.objects.get(case=self.case)

    @override_settings(SIMULATED_TELERADIOLOGY_DELAY=(30, 30))
    def test_waits_then_signs_predefined_read_as_simulated(self):
        review = self.pending()
        status = self.client.get(reverse('teleradiology-status', args=[review.pk])).json()
        self.assertFalse(status['signed']); self.assertEqual(status['stage'], 'queued')
        self.assertContains(self.client.get(reverse('case-detail', args=[self.case.pk])), 'Awaiting teleradiologist')
        SpecialistReview.objects.filter(pk=review.pk).update(requested_at=timezone.now() - timedelta(seconds=40))
        status = self.client.get(reverse('teleradiology-status', args=[review.pk])).json()
        self.assertTrue(status['signed']); self.assertEqual(status['reviewer'], 'Dr Adaeze Okonkwo')
        review.refresh_from_db(); self.case.refresh_from_db()
        self.assertTrue(review.simulated); self.assertEqual(review.concordance, 'PARTIAL'); self.assertEqual(review.birads, '3')
        self.assertIn('lipoma', review.assessment.lower())
        self.assertEqual(self.case.status, Case.Status.REVIEWED)
        self.assertFalse(review.reviewer.is_active)
        self.assertTrue(CaseEvent.objects.filter(kind='SPECIALIST_REVIEW_SIGNED', details__simulated=True).exists())
        detail = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertContains(detail, 'Signed second read'); self.assertContains(detail, 'Dr Adaeze Okonkwo')
        self.assertNotContains(detail, 'simulated')

    @override_settings(SIMULATED_TELERADIOLOGY_DELAY=(0, 0))
    def test_case_page_resolves_due_review_on_load(self):
        self.pending()
        detail = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertContains(detail, 'Specialist reviewed')
        self.assertContains(detail, 'Signed second read')

    @override_settings(SIMULATED_TELERADIOLOGY_DELAY=(0, 0))
    def test_never_simulates_outside_demo_or_when_disabled(self):
        review = self.pending(demo=False)
        self.client.get(reverse('case-detail', args=[self.case.pk]))
        review.refresh_from_db(); self.assertIsNone(review.signed_at)
        self.case.patient.facility.is_demo = True; self.case.patient.facility.save()
        with self.settings(SIMULATED_TELERADIOLOGY=False):
            self.client.get(reverse('case-detail', args=[self.case.pk]))
        review.refresh_from_db(); self.assertIsNone(review.signed_at)

    def test_status_endpoint_is_facility_scoped(self):
        review = self.pending()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('teleradiology-status', args=[review.pk])).status_code, 404)
