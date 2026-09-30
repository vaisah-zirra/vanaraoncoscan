import uuid
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from django.utils import timezone
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Case, Patient, AIAssessment, QualityAssessment
from apps.workflow.models import ClinicalDecision, Referral, FollowUp, SpecialistReview, CaseEvent
from apps.workflow.services import confirm_decision


class ClinicalReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='clinician')
        self.other = get_user_model().objects.create_user(username='outsider')
        self.facility = Facility.objects.create(name='Clinic', slug='clinic')
        Membership.objects.create(user=self.user, facility=self.facility, role='FACILITY')
        patient = Patient.objects.create(facility=self.facility, reference='P1', display_name='Test patient')
        self.case = Case.objects.create(patient=patient, status='ASSESSED')
        self.quality = QualityAssessment.objects.create(case=self.case, adequate=True, reason='Passed')
        self.assessment = AIAssessment.objects.create(case=self.case, disposition='SUSPICIOUS', finding='Finding for review')
        self.url = reverse('clinician-review', args=[self.case.pk])
        self.client.force_login(self.user)

    def payload(self, action='REFERRAL'):
        self.case.refresh_from_db()
        return {'request_id':str(uuid.uuid4()), 'version':self.case.updated_at.isoformat(),
            'action':action, 'notes':'History and findings reviewed.', 'destination':'Breast assessment clinic',
            'urgency':'PRIORITY','reason':'Review the focal finding alongside the presenting symptoms.',
            'due_date':str(timezone.localdate()+timedelta(days=14)),
            'followup_notes':'Reassess symptoms and document the clinical findings.', 'confirmed':'on'}

    def save(self, data):
        return confirm_decision(user=self.user, case_id=self.case.pk, data=data)

    def test_referral_persists_actor_details_and_one_event(self):
        data = self.payload()
        decision = self.save(data)
        self.assertEqual(self.save(data).pk, decision.pk)
        referral = Referral.objects.get(case=self.case)
        self.assertEqual(referral.urgency, 'PRIORITY')
        self.assertEqual(referral.confirmed_by, self.user)
        self.assertEqual(CaseEvent.objects.filter(case=self.case, kind='REFERRAL_CONFIRMED').count(), 1)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, 'REFERRAL_CONFIRMED')
        self.assertContains(self.client.get(self.url), 'Recorded in this workspace')

    def test_existing_plan_cannot_be_overwritten(self):
        self.save(self.payload())
        with self.assertRaises(ValidationError):
            self.save(self.payload())
        self.assertEqual(Referral.objects.count(), 1)

    def test_stale_submission_rejected_without_partial_writes(self):
        data = self.payload()
        Case.objects.filter(pk=self.case.pk).update(updated_at=self.case.updated_at + timedelta(seconds=1))
        with self.assertRaises(ValidationError): self.save(data)
        self.assertFalse(ClinicalDecision.objects.exists())
        self.assertFalse(Referral.objects.exists())

    def test_routine_followup_and_past_date_validation(self):
        self.assessment.disposition = 'NON_SUSPICIOUS'; self.assessment.save()
        data = self.payload('FOLLOW_UP'); data['due_date'] = str(timezone.localdate()-timedelta(days=1))
        self.assertContains(self.client.post(self.url, data), 'Choose today or a future date')
        self.assertFalse(FollowUp.objects.exists())
        self.save(self.payload('FOLLOW_UP'))
        self.assertEqual(FollowUp.objects.count(), 1)
        self.case.refresh_from_db(); self.assertEqual(self.case.status, 'FOLLOW_UP')

    def test_nonroutine_followup_requires_signed_opinion(self):
        with self.assertRaises(ValidationError): self.save(self.payload('FOLLOW_UP'))
        SpecialistReview.objects.create(case=self.case, reviewer=self.user, signed_at=timezone.now())
        self.save(self.payload('FOLLOW_UP'))
        self.assertTrue(FollowUp.objects.exists())

    def test_specialist_request_reuses_pending_review(self):
        SpecialistReview.objects.create(case=self.case)
        self.save(self.payload('SPECIALIST'))
        self.assertEqual(SpecialistReview.objects.count(), 1)
        self.case.refresh_from_db(); self.assertEqual(self.case.status, 'REVIEW_PENDING')
        self.assertIsNone(SpecialistReview.objects.get().signed_at)

    def test_cross_facility_and_inactive_membership(self):
        with self.assertRaises(PermissionDenied):
            confirm_decision(user=self.other, case_id=self.case.pk, data=self.payload())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 404)
        Membership.objects.filter(user=self.user).update(is_active=False)
        with self.assertRaises(PermissionDenied): self.save(self.payload())

    def test_confirmation_fields_csrf_and_read_only_get(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(ClinicalDecision.objects.exists())
        data = self.payload(); data.pop('confirmed'); data['destination']=''
        response = self.client.post(self.url, data)
        self.assertContains(response, 'The decision has not been saved')
        self.assertFalse(Referral.objects.exists())
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.user)
        self.assertEqual(secure.post(self.url, self.payload()).status_code, 403)

    def test_failed_quality_and_missing_assessment_block_decision(self):
        self.quality.adequate=False; self.quality.save()
        with self.assertRaises(ValidationError): self.save(self.payload())
        self.quality.adequate=True; self.quality.save()
        self.assessment.delete()
        with self.assertRaises(ValidationError): self.save(self.payload())

    def test_reused_submission_with_different_content_rejected(self):
        data=self.payload(); self.save(data)
        data['notes']='Changed notes'
        with self.assertRaises(ValidationError): self.save(data)

    def test_required_pathway_fields_and_invalid_urgency(self):
        for field in ('destination','urgency','reason'):
            data=self.payload(); data[field]=''
            with self.assertRaises(ValidationError): self.save(data)
        data=self.payload(); data['urgency']='INVALID'
        with self.assertRaises(ValidationError): self.save(data)
        self.assertFalse(ClinicalDecision.objects.exists())

    def test_result_shows_current_confirmed_plan(self):
        self.assessment.details = {'filename':'example.png', 'width':100,'height':100,'sample_id':1}
        self.assessment.save()
        self.save(self.payload())
        response = self.client.get(reverse('assessment-result', args=[self.case.pk]))
        self.assertContains(response, 'View confirmed care plan')
        self.assertNotContains(response, 'Clinician confirmation required')


    def routine_payload(self):
        self.assessment.disposition='NON_SUSPICIOUS';self.assessment.save()
        data=self.payload('ROUTINE')
        data.update(safety_net='Return to routine care. Seek reassessment for persistent or changing symptoms using the agreed care contact.',concordant='on')
        return data

    def test_routine_completion_is_idempotent_without_appointment_and_in_pdf(self):
        from io import BytesIO
        from pypdf import PdfReader
        data=self.routine_payload()
        decision=self.save(data)
        self.assertEqual(self.save(data).pk,decision.pk)
        self.case.refresh_from_db();self.assertEqual(self.case.status,'COMPLETED')
        self.assertFalse(Referral.objects.exists());self.assertFalse(FollowUp.objects.exists())
        self.assertEqual(CaseEvent.objects.filter(case=self.case,kind='ROUTINE_CARE_CONFIRMED').count(),1)
        self.assertContains(self.client.get(self.url),data['safety_net'])
        self.assertNotContains(self.client.get(self.url),'Clinical review is not available yet')
        self.assertContains(self.client.get(reverse('case-detail',args=[self.case.pk])),data['safety_net'])
        response=self.client.get(reverse('case-report',args=[self.case.pk]))
        text=' '.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
        self.assertIn('routine-care plan and return advice',text.lower())
        self.assertNotIn('No referral or follow-up plan has been confirmed',text)
        with self.assertRaises(ValidationError): self.save(self.routine_payload())

    def test_routine_requires_concordance_plan_and_clear_assessment(self):
        data=self.routine_payload()
        for field in ['concordant','safety_net','confirmed']:
            invalid=dict(data);invalid[field]=''
            with self.assertRaises(ValidationError): self.save(invalid)
        for disposition in ['SUSPICIOUS','UNCERTAIN','REVIEW_REQUIRED']:
            self.assessment.disposition=disposition;self.assessment.save()
            with self.assertRaises(ValidationError): self.save(data)
            self.assertNotIn('ROUTINE',dict(self.client.get(self.url).context['form'].fields['action'].choices))
        self.assertFalse(ClinicalDecision.objects.exists())

    def test_routine_not_available_with_pending_specialist_review(self):
        data=self.routine_payload()
        SpecialistReview.objects.create(case=self.case)
        with self.assertRaises(ValidationError): self.save(data)
        self.assertNotIn('ROUTINE',dict(self.client.get(self.url).context['form'].fields['action'].choices))
