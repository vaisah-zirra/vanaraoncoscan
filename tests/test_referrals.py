import uuid
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from django.utils import timezone
from apps.organizations.models import Facility, Membership
from apps.clinical.models import Case, Patient, AIAssessment, QualityAssessment
from apps.workflow.models import Referral, ReferralUpdate, SpecialistReview, CaseEvent
from apps.workflow.referrals import update_referral
from apps.workflow.specialist_content import specialist_content
from apps.workflow.reporting import report_data, render_report
from io import BytesIO
from pypdf import PdfReader

class ReferralTests(TestCase):
 def setUp(self):
  self.user=get_user_model().objects.create_user(username='coordinator')
  self.other=get_user_model().objects.create_user(username='outsider')
  facility=Facility.objects.create(name='Care centre',slug='care',is_demo=True)
  Membership.objects.create(user=self.user,facility=facility,role='FACILITY')
  patient=Patient.objects.create(facility=facility,reference='DEMO-R',display_name='Referral patient',is_synthetic=True)
  self.case=Case.objects.create(patient=patient,status='REFERRAL_CONFIRMED')
  self.item=Referral.objects.create(case=self.case,reason='Specialist evaluation requested.',destination='Breast assessment clinic',confirmed_by=self.user,urgency='PRIORITY')
  self.client.force_login(self.user)
  self.url=reverse('referral-detail',args=[self.item.pk])
 def payload(self,status='ACCEPTED'):
  self.item.refresh_from_db()
  return {'request_id':str(uuid.uuid4()),'version':self.item.version,'status':status,'notes':'Receiving service acknowledged the referral.','confirmed':'on','appointment_date':str(timezone.localdate()+timedelta(days=7))}
 def save(self,data): return update_referral(user=self.user,referral_id=self.item.pk,data=data)
 def test_lifecycle_idempotency_and_report(self):
  data=self.payload(); first=self.save(data);self.assertEqual(first.pk,self.save(data).pk)
  self.save(self.payload('SCHEDULED'));self.save(self.payload('COMPLETED'))
  self.item.refresh_from_db();self.assertEqual(self.item.status,'COMPLETED')
  self.assertEqual(ReferralUpdate.objects.count(),3);self.assertEqual(CaseEvent.objects.count(),3)
  pdf=render_report(report_data(self.case));text=' '.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
  self.assertIn('Receiving service acknowledged',text);self.assertIn('REFERRAL STAGE',text)
  self.assertContains(self.client.get(self.url),'Referral record closed')
  with self.assertRaises(ValidationError):self.save(self.payload('ACCEPTED'))
 def test_stale_invalid_transition_and_dates(self):
  stale=self.payload('CANCELLED');self.save(self.payload())
  with self.assertRaises(ValidationError):self.save(stale)
  with self.assertRaises(ValidationError):self.save(self.payload('PENDING'))
  bad=self.payload('SCHEDULED');bad['appointment_date']=''
  with self.assertRaises(ValidationError):self.save(bad)
  bad['appointment_date']=str(timezone.localdate()-timedelta(days=1))
  with self.assertRaises(ValidationError):self.save(bad)
 def test_authorization_csrf_confirmation(self):
  with self.assertRaises(PermissionDenied):update_referral(user=self.other,referral_id=self.item.pk,data=self.payload())
  data=self.payload();data.pop('confirmed');self.assertContains(self.client.post(self.url,data),'This field is required')
  secure=Client(enforce_csrf_checks=True);secure.force_login(self.user);self.assertEqual(secure.post(self.url,self.payload()).status_code,403)
  self.client.force_login(self.other);self.assertEqual(self.client.get(self.url).status_code,404)
  self.assertNotContains(self.client.get(reverse('referral-list')),'Referral patient')
 def test_filters_and_read_only_pages(self):
  url=reverse('referral-list')
  self.assertContains(self.client.get(url,{'q':'Breast','urgency':'PRIORITY'}),'Referral patient')
  self.assertNotContains(self.client.get(url,{'status':'COMPLETED'}),'Referral patient')
  self.assertEqual(self.client.get(self.url).status_code,200)
  self.assertFalse(ReferralUpdate.objects.exists())
 def test_specialist_consistency_and_signed_precedence(self):
  AIAssessment.objects.create(case=self.case,disposition='SUSPICIOUS',finding='Focal finding.')
  shared=specialist_content(self.case)
  self.assertEqual(shared['response'],report_data(self.case)['response'])
  response=self.client.get(reverse('case-detail',args=[self.case.pk]))
  self.assertContains(response,shared['response'][0][1])
  SpecialistReview.objects.create(case=self.case,reviewer=self.user,signed_at=timezone.now(),assessment='Recorded signed opinion',recommendation='Recorded plan')
  response=self.client.get(reverse('case-detail',args=[self.case.pk]))
  self.assertContains(response,'Recorded signed opinion');self.assertNotContains(response,'Automatic response')
 def test_no_automatic_response_for_non_demo_or_pending(self):
  self.assertFalse(specialist_content(self.case)['response'])
  AIAssessment.objects.create(case=self.case,disposition='SUSPICIOUS',finding='Focal finding.')
  self.case.patient.is_synthetic=False;self.case.patient.save()
  self.assertFalse(specialist_content(self.case)['response'])
