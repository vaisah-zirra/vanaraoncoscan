from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import ContactEnquiry

class LandingTests(TestCase):
 def payload(self):
  return {'name':'Website QA','email':'qa@example.test','organisation':'QA organisation','interest':'Clinic','message':'Please tell me about clinic access.','consent':'on'}
 def test_public_home_and_protected_workspace(self):
  response=self.client.get(reverse('landing'))
  self.assertEqual(response.status_code,200)
  for text in ['A clearer picture.','Subscription','Practice','Clinic','Network','Send enquiry']:
   self.assertContains(response,text)
  self.assertRedirects(self.client.get(reverse('dashboard')), '/accounts/login/?next=/workspace/')
  self.assertIn('no-store',response['Cache-Control'])
 def test_enquiry_saved_with_consent_and_success_once(self):
  response=self.client.post(reverse('landing'),self.payload())
  self.assertEqual(response.status_code,302)
  item=ContactEnquiry.objects.get();self.assertEqual(item.interest,'Clinic');self.assertTrue(item.consent)
  self.assertContains(self.client.get(reverse('landing')),'Thank you for reaching out.')
  self.assertNotContains(self.client.get(reverse('landing')),'Thank you for reaching out.')
  self.client.post(reverse('landing'),self.payload());self.assertEqual(ContactEnquiry.objects.count(),1)
 def test_validation_honeypot_and_csrf(self):
  data=self.payload();data.pop('consent');self.client.post(reverse('landing'),data)
  self.assertFalse(ContactEnquiry.objects.exists())
  data=self.payload();data['email']='not-an-email';self.client.post(reverse('landing'),data)
  self.assertFalse(ContactEnquiry.objects.exists())
  data=self.payload();data['website']='spam';self.client.post(reverse('landing'),data)
  self.assertFalse(ContactEnquiry.objects.exists())
  self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('landing'),self.payload()).status_code,403)
 def test_category_prefill_and_private_inbox(self):
  response=self.client.get(reverse('landing'),{'interest':'Network'})
  self.assertEqual(response.context['contact_form'].initial['interest'],'Network')
  user=get_user_model().objects.create_user(username='demo-visitor')
  self.client.force_login(user)
  response=self.client.get('/admin/accounts/contactenquiry/')
  self.assertEqual(response.status_code,302)
