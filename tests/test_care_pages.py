from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.workflow.models import SpecialistReview, Referral, FollowUp
from tests import test_assessment as base


class CarePagesTests(TestCase):
    setUp = base.AssessmentTests.setUp
    attach = base.AssessmentTests.attach
    quality = base.AssessmentTests.quality
    assess = base.AssessmentTests.assess

    def pending(self, demo=True):
        self.case.patient.facility.is_demo = demo; self.case.patient.facility.save()
        sample = self.attach('sample-04'); self.quality(sample); self.assess(sample)
        return SpecialistReview.objects.get(case=self.case)

    @override_settings(SIMULATED_TELERADIOLOGY_DELAY=(60, 60))
    def test_specialist_reviews_lists_pending_and_is_scoped(self):
        review = self.pending()
        page = self.client.get(reverse('specialist-reviews'))
        self.assertContains(page, 'Specialist reviews')
        self.assertContains(page, self.case.patient.display_name)
        self.assertContains(page, 'Awaiting radiologist')
        self.assertContains(page, reverse('teleradiology-status', args=[review.pk]))
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('specialist-reviews') + '?status=all'), self.case.patient.display_name)

    @override_settings(SIMULATED_TELERADIOLOGY_DELAY=(0, 0))
    def test_due_simulated_read_is_signed_on_load_and_shown(self):
        self.pending()
        page = self.client.get(reverse('specialist-reviews') + '?status=signed')
        self.assertContains(page, 'Signed')
        self.assertContains(page, 'BI-RADS 3')
        self.assertContains(page, 'Partially agree')
        self.assertEqual(page.context['kpis']['signed'], 1)

    def test_sidebar_links_to_specialist_reviews(self):
        self.assertContains(self.client.get(reverse('dashboard')), reverse('specialist-reviews'))

    def test_referral_and_followup_pages_render_new_layout(self):
        Referral.objects.create(case=self.case, reason='Assess focal lesion', destination='Breast clinic', confirmed_by=self.user, urgency='URGENT')
        FollowUp.objects.create(case=self.case, due_date=timezone.localdate() + timedelta(days=2), notes='Repeat scan')
        refs = self.client.get(reverse('referral-list'))
        self.assertContains(refs, 'Referral register'); self.assertContains(refs, '1 urgent / priority')
        detail = self.client.get(reverse('referral-detail', args=[Referral.objects.get().pk]))
        self.assertContains(detail, 'aria-current="step"'); self.assertContains(detail, 'Update progress')
        fus = self.client.get(reverse('followup-list'))
        self.assertContains(fus, 'The week ahead'); self.assertContains(fus, 'In 2 days')
        fd = self.client.get(reverse('followup-detail', args=[FollowUp.objects.get().pk]))
        self.assertContains(fd, 'days to go')
