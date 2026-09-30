import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from apps.validation.models import Participant, Visit, WalkthroughRound, Feedback, Lead, LeadUpdate
from apps.validation.services import round_progress, record_view
from apps.clinical.models import Case, Patient, CaseImage, UltrasoundSample, QualityAssessment, AIAssessment
from apps.clinical.services import start_case
from apps.organizations.models import Membership
from apps.workflow.models import ClinicalDecision, CaseEvent

class ValidationTests(TestCase):
    def payload(self,email='clinician@example.test'):
        return {'full_name':'Ada Okafor','email':email,'role':'Clinician','organisation':'Evaluation Clinic',
            'password1':'Research-Workflow-742!','password2':'Research-Workflow-742!','consent':'on'}
    def signup(self,email='clinician@example.test',client=None):
        client=client or self.client
        response=client.post(reverse('signup'),self.payload(email))
        self.assertEqual(response.status_code,302)
        return Participant.objects.get(user__email=email.lower())
    def case(self,participant=None):
        participant=participant or self.signup()
        patient=Patient.objects.filter(facility=participant.facility).first()
        case=start_case(user=participant.user,patient_id=patient.pk)
        return WalkthroughRound.objects.get(case=case)
    def prepare(self,item,adequate=True,decision=True):
        sample=UltrasoundSample.objects.create(code='test-'+str(item.pk),label='Sample',filename='sample.png',licence_verified=True,byte_size=100,width=100,height=100,sha256='0'*64)
        CaseImage.objects.create(case=item.case,sample=sample,attached_by=item.participant.user)
        QualityAssessment.objects.create(case=item.case,adequate=adequate,reason='Quality review')
        if adequate:
            AIAssessment.objects.create(case=item.case,disposition='NON_SUSPICIOUS',finding='Finding',details={'label':'Test'})
            if decision:
                ClinicalDecision.objects.create(case=item.case,actor=item.participant.user,request_id=uuid.uuid4(),action='FOLLOW_UP',notes='Reviewed')
        item.refresh_from_db()

    def test_signup_auto_login_isolated_patients_no_precompleted_rounds(self):
        first=self.signup()
        other=Client();second=self.signup('other@example.test',other)
        self.assertNotEqual(first.facility_id,second.facility_id)
        self.assertEqual(Patient.objects.filter(facility=first.facility).count(),4)
        self.assertFalse(first.user.is_staff)
        self.assertFalse(Case.objects.exists())
        self.assertContains(self.client.get('/workspace/'),'Ready for your first case?')
        case=start_case(user=second.user,patient_id=Patient.objects.filter(facility=second.facility).first().pk)
        self.assertEqual(self.client.get(reverse('case-detail',args=[case.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('round-feedback',args=[case.walkthrough_round.pk])).status_code,404)

    def test_email_case_insensitive_login_and_duplicate_rejected(self):
        self.signup();self.client.logout()
        data=self.payload('CLINICIAN@example.test')
        self.assertEqual(self.client.post(reverse('signup'),data).status_code,200)
        self.assertEqual(Participant.objects.count(),1)
        response=self.client.post(reverse('login'),{'username':'CLINICIAN@example.test','password':data['password1']})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get('/workspace/'),'Evaluation Clinic')

    def test_signup_rejects_missing_consent_weak_password_mismatch_and_honeypot(self):
        for change in [{'consent':''},{'password1':'password','password2':'password'},{'password2':'different'}, {'website':'bot'}, {'role':''},{'whatsapp':'+2348000000000'}]:
            data=self.payload();data.update(change)
            self.assertEqual(self.client.post(reverse('signup'),data).status_code,200)
            self.assertFalse(Participant.objects.exists())
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('signup'),self.payload()).status_code,403)

    def test_auth_layout_has_no_workspace_sidebar_or_prefilled_password(self):
        response=self.client.get(reverse('login'))
        self.assertNotContains(response,'prefilled')
        self.assertNotContains(response,'class="sidebar"')
        self.assertNotContains(response,'value="Research-Workflow')
        self.signup()
        self.assertNotContains(self.client.get(reverse('login')),'class="sidebar"')
        self.assertEqual(self.client.get(reverse('signup')).status_code,302)

    def test_public_entry_points_are_not_duplicated(self):
        response=self.client.get('/')
        self.assertContains(response,'>Log in</a>',count=1)
        self.assertContains(response,'class="tracking-note"',count=1)
        self.assertContains(response,'Request a demonstration')

    def test_initial_context_is_available_for_new_demo_facility(self):
        self.signup()
        response=self.client.get(reverse('new-assessment'))
        self.assertTrue(any(response.context['patient_contexts'].values()))

    def test_per_case_progress_does_not_combine_actions(self):
        participant=self.signup();one=self.case(participant);two=self.case(participant)
        self.prepare(one,decision=False);self.prepare(two)
        record_view(participant.user,one.case,'assessment')
        record_view(participant.user,one.case,'report')
        record_view(participant.user,two.case,'report')
        self.assertFalse(WalkthroughRound.objects.filter(completed_at__isnull=False).exists())
        two.refresh_from_db();self.assertEqual(round_progress(two)['percent'],67)

    def test_early_report_does_not_count_and_completed_report_is_idempotent(self):
        item=self.case();self.prepare(item,decision=False)
        record_view(item.participant.user,item.case,'assessment')
        record_view(item.participant.user,item.case,'report')
        item.refresh_from_db();self.assertIsNone(item.report_requested_at)
        ClinicalDecision.objects.create(case=item.case,actor=item.participant.user,request_id=uuid.uuid4(),action='FOLLOW_UP',notes='Reviewed')
        record_view(item.participant.user,item.case,'report')
        item.refresh_from_db();stamp=item.completed_at
        record_view(item.participant.user,item.case,'report')
        item.refresh_from_db();self.assertEqual(item.completed_at,stamp)
        self.assertEqual(round_progress(item)['percent'],100)
        self.assertContains(self.client.get(reverse('walkthrough')),'data-feedback-prompt')

    def test_quality_failure_has_four_step_completion_without_ai(self):
        item=self.case();self.prepare(item,adequate=False)
        self.assertEqual(round_progress(item)['total'],4)
        self.assertEqual(round_progress(item)['percent'],75)
        record_view(item.participant.user,item.case,'report')
        item.refresh_from_db();self.assertEqual(round_progress(item)['percent'],100)
        self.assertFalse(AIAssessment.objects.exists())

    def test_report_success_tracking_preserves_clinical_audit_and_failure_does_not_complete(self):
        item=self.case();self.prepare(item,adequate=False)
        original=CaseEvent.objects.count()
        with patch('apps.workflow.report_views.report_data',return_value={'revision':'test'}),patch('apps.workflow.report_views.render_report',return_value=b'%PDF-test'):
            response=self.client.get(reverse('case-report',args=[item.case_id]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(CaseEvent.objects.count(),original)
        item.refresh_from_db();self.assertIsNotNone(item.completed_at)
        second=self.case(item.participant);self.prepare(second,adequate=False)
        with patch('apps.workflow.report_views.render_report',side_effect=RuntimeError('PDF failed')):
            with self.assertRaises(RuntimeError): self.client.get(reverse('case-report',args=[second.case_id]))
        second.refresh_from_db();self.assertIsNone(second.completed_at)

    def test_no_tracking_round_for_existing_seed_users(self):
        participant=self.signup()
        user=get_user_model().objects.create_user(username='seed')
        Membership.objects.create(user=user,facility=participant.facility,role='FACILITY')
        case=start_case(user=user,patient_id=Patient.objects.filter(facility=participant.facility).first().pk)
        self.assertFalse(WalkthroughRound.objects.filter(case=case).exists())

    def test_feedback_early_once_rating_and_contact_validation(self):
        item=self.case();url=reverse('round-feedback',args=[item.pk])
        data={'rating':6,'most_useful':'Report','barriers':['Evidence'],'suggestion':'Clearer labels','intent':'Pilot'}
        self.client.post(url,data);self.assertFalse(Feedback.objects.exists())
        data.update(rating=5);self.client.post(url,data);self.assertFalse(Feedback.objects.exists())
        data['contact_consent']='on';data['barriers']=['Evidence','Cost','Privacy'];self.client.post(url,data);self.client.post(url,data)
        self.assertEqual(Feedback.objects.count(),1);self.assertEqual(Lead.objects.count(),1)
        self.assertEqual(Feedback.objects.get().completion_at_submission,17)
        self.assertEqual(Feedback.objects.get().barriers,['Evidence','Cost','Privacy'])
        self.assertEqual(Lead.objects.get().interest,'Pilot')
        self.assertContains(self.client.get(url),'Thank you for your feedback.')

    def test_dismiss_and_status_are_owned_and_csrf_protected(self):
        item=self.case();self.prepare(item,adequate=False);record_view(item.participant.user,item.case,'report')
        url=reverse('round-status',args=[item.case_id])
        self.assertTrue(self.client.get(url).json()['prompt'])
        dismiss=reverse('dismiss-feedback',args=[item.pk])
        self.assertEqual(self.client.get(dismiss).status_code,405)
        secure=Client(enforce_csrf_checks=True);secure.force_login(item.participant.user)
        self.assertEqual(secure.post(dismiss).status_code,403)
        self.client.post(dismiss)
        self.assertFalse(self.client.get(url).json()['prompt'])
        other=Client();self.signup('other@example.test',other)
        self.assertEqual(other.get(url).status_code,404)

    def test_visit_session_deduplication_sources_and_return_session(self):
        self.client.get('/',{'utm_source':'instagram','utm_campaign':'sept_launch'})
        self.client.get('/');self.client.get('/accounts/signup/')
        self.assertEqual(Visit.objects.count(),1)
        participant=self.signup();self.assertEqual(participant.source,'instagram')
        self.client.get('/workspace/');self.assertEqual(Visit.objects.get().participant,participant)
        Visit.objects.update(last_seen=timezone.now()-timedelta(minutes=31))
        self.client.get('/workspace/');self.assertEqual(Visit.objects.count(),2)
        self.assertEqual(Visit.objects.values('visitor').distinct().count(),1)

    def test_pilot_without_account_and_website_contact_feed_inbox(self):
        data={key:value for key,value in self.payload().items() if not key.startswith('password')}
        data.update(interest='Pilot',message='Discuss evaluation.')
        self.assertEqual(self.client.post(reverse('pilot-interest'),data).status_code,302)
        self.assertFalse(Participant.objects.exists())
        self.assertEqual(Lead.objects.get().interest,'Pilot')
        self.client.post(reverse('pilot-interest'),data);self.assertEqual(Lead.objects.count(),1)
        self.assertContains(self.client.get(reverse('pilot-interest')),'INTEREST RECEIVED')
        self.client.post('/',{'name':'Clinic manager','email':'manager@example.test','organisation':'Clinic','interest':'Demo','message':'Show our team','consent':'on'})
        self.assertEqual(Lead.objects.count(),2)

    def test_admin_authorization_filters_and_lead_stale_update(self):
        participant=self.signup();item=self.case(participant)
        url=reverse('validation-dashboard')
        self.assertEqual(self.client.get(url).status_code,403)
        participant.user.is_staff=True;participant.user.save()
        self.assertEqual(self.client.get(url).status_code,403)
        owner=get_user_model().objects.create_superuser(username='owner',email='owner@example.test',password='Owner-test-241!')
        self.client.force_login(owner)
        before=Visit.objects.count();self.client.get('/');self.assertEqual(Visit.objects.count(),before)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertEqual(response.context['stats']['registrations'],1)
        self.assertEqual(response.context['stats']['rounds'],1)
        self.assertEqual(response.context['participant_page'].paginator.count,1)
        self.assertContains(response,'Search participants')
        self.assertEqual(self.client.get(url,{'participant_q':'absent'}).context['participant_page'].paginator.count,0)
        self.assertEqual(self.client.get(url,{'role':'Leadership'}).context['stats']['registrations'],0)
        lead=Lead.objects.create(name='Pilot contact',email='pilot@example.test',interest='Pilot',contact_consent_at=timezone.now())
        target=reverse('validation-lead',args=[lead.pk])
        data={'version':0,'stage':'Contacted','next_action':'Arrange demo','next_action_date':''}
        self.assertEqual(self.client.post(target,data).status_code,302)
        self.assertEqual(LeadUpdate.objects.count(),1)
        self.assertContains(self.client.post(target,data),'changed in another session')
        self.assertEqual(LeadUpdate.objects.count(),1)
        self.assertIn('no-store',response['Cache-Control'])


from django.test import SimpleTestCase
from types import SimpleNamespace
from apps.validation.forms import FeedbackForm
from apps.validation.feedback_choices import factor_counts

class FeedbackChoiceTests(SimpleTestCase):
    def form(self, factors):
        return FeedbackForm({'rating':'5','most_useful':'AI','barriers':factors,'intent':'None'})

    def test_new_options_and_three_factor_limit(self):
        self.assertTrue(self.form(['Evidence','Cost','Privacy']).is_valid())
        form=self.form(['Evidence','Cost','Privacy','Support'])
        self.assertFalse(form.is_valid())
        self.assertIn('barriers',form.errors)
        self.assertFalse(self.form([]).is_valid())
        self.assertFalse(self.form(['made-up']).is_valid())

    def test_unsure_is_exclusive_and_other_is_available(self):
        self.assertTrue(self.form(['Unsure']).is_valid())
        self.assertFalse(self.form(['Unsure','Cost']).is_valid())
        form=self.form(['Other']);form.data['most_useful']='Other'
        self.assertTrue(form.is_valid())

    def test_counts_include_legacy_without_reinterpreting_it(self):
        result=factor_counts([SimpleNamespace(barriers=['Evidence','Cost'],barrier=''),SimpleNamespace(barriers=[],barrier='Evidence'),SimpleNamespace(barriers=[],barrier='Governance'),SimpleNamespace(barriers=['Cost','Cost'],barrier='')])
        counts={row['barrier']:row['n'] for row in result}
        self.assertEqual(counts['Clinical accuracy and supporting evidence'],2)
        self.assertEqual(counts['Cost and affordability'],2)
        self.assertEqual(counts['Data governance and approvals (earlier response)'],1)
