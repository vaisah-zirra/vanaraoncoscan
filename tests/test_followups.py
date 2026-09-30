import uuid
from datetime import timedelta
from io import BytesIO
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader
from apps.organizations.models import Facility,Membership
from apps.clinical.models import Case,Patient
from apps.workflow.models import FollowUp,FollowUpUpdate,CaseEvent
from apps.workflow.followup_services import update_followup
from apps.workflow.reporting import report_data,render_report

class FollowUpTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='coordinator')
        self.other=get_user_model().objects.create_user(username='other')
        facility=Facility.objects.create(name='Care centre',slug='care',is_demo=True)
        Membership.objects.create(user=self.user,facility=facility,role='FACILITY')
        patient=Patient.objects.create(facility=facility,reference='DEMO-F',display_name='Review patient')
        self.case=Case.objects.create(patient=patient,status='FOLLOW_UP')
        self.item=FollowUp.objects.create(case=self.case,due_date=timezone.localdate()-timedelta(days=2),notes='Original review plan.')
        self.client.force_login(self.user)
        self.url=reverse('followup-detail',args=[self.item.pk])
    def payload(self,action='COMPLETE'):
        self.item.refresh_from_db()
        return {'request_id':str(uuid.uuid4()),'version':self.item.version,'action':action,'notes':'Review completed and outcome recorded.','due_date':str(timezone.localdate()+timedelta(days=7)),'confirmed':'on'}
    def save(self,data):return update_followup(user=self.user,followup_id=self.item.pk,data=data)
    def test_complete_is_idempotent_and_records_actor(self):
        data=self.payload(); first=self.save(data); self.assertEqual(first.pk,self.save(data).pk)
        self.item.refresh_from_db();self.case.refresh_from_db()
        self.assertEqual(self.item.completed_by,self.user);self.assertEqual(self.item.notes,'Original review plan.')
        self.assertEqual(self.case.status,'COMPLETED');self.assertEqual(FollowUpUpdate.objects.count(),1)
        self.assertEqual(CaseEvent.objects.filter(kind='FOLLOW_UP_COMPLETED').count(),1)
        with self.assertRaises(ValidationError):self.save(self.payload())
    def test_reschedule_preserves_plan_and_history(self):
        old=self.item.due_date;self.save(self.payload('RESCHEDULE'));self.item.refresh_from_db()
        self.assertNotEqual(self.item.due_date,old);self.assertIsNone(self.item.completed_at)
        self.assertEqual(CaseEvent.objects.get().details['previous_due_date'],str(old))
        self.assertContains(self.client.get(self.url),'Review rescheduled')
    def test_stale_page_and_bad_dates_rejected(self):
        stale=self.payload();self.save(self.payload('RESCHEDULE'))
        with self.assertRaises(ValidationError):self.save(stale)
        data=self.payload('RESCHEDULE');data['due_date']=str(timezone.localdate()-timedelta(days=1))
        with self.assertRaises(ValidationError):self.save(data)
    def test_other_open_review_keeps_case_open(self):
        FollowUp.objects.create(case=self.case,due_date=timezone.localdate(),notes='Another review')
        self.save(self.payload());self.case.refresh_from_db();self.assertEqual(self.case.status,'FOLLOW_UP')
    def test_other_case_status_is_not_overwritten(self):
        self.case.status='REFERRAL_CONFIRMED';self.case.save()
        self.save(self.payload());self.case.refresh_from_db();self.assertEqual(self.case.status,'REFERRAL_CONFIRMED')
    def test_access_confirmation_and_csrf(self):
        with self.assertRaises(PermissionDenied):update_followup(user=self.other,followup_id=self.item.pk,data=self.payload())
        data=self.payload();data.pop('confirmed');self.assertContains(self.client.post(self.url,data),'The update was not saved')
        self.assertFalse(FollowUpUpdate.objects.exists())
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.user)
        self.assertEqual(secure.post(self.url,self.payload()).status_code,403)
        self.client.force_login(self.other);self.assertEqual(self.client.get(self.url).status_code,404)
        self.assertNotContains(self.client.get(reverse('followup-list')),'Review patient')
    def test_filters_counts_and_get_does_not_mutate(self):
        response=self.client.get(reverse('followup-list'),{'status':'overdue','q':'Review patient'})
        self.assertContains(response,'Review patient');self.assertEqual(response.context['counts']['overdue'],1)
        self.assertNotContains(self.client.get(reverse('followup-list'),{'status':'completed'}),'Review patient')
        self.client.get(self.url);self.assertFalse(FollowUpUpdate.objects.exists())
    def test_completion_appears_in_pdf(self):
        self.save(self.payload())
        text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_report(report_data(Case.objects.get(pk=self.case.pk))))).pages)
        self.assertIn('Review completed and outcome recorded.',text)
        self.assertIn('coordinator',text)
    def test_completed_form_hidden_and_duplicate_token_content_rejected(self):
        data=self.payload();self.save(data)
        self.assertNotContains(self.client.get(self.url),'Save follow-up update')
        data['notes']='Changed outcome'
        with self.assertRaises(ValidationError):self.save(data)
