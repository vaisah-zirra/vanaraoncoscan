from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.clinical.models import Patient
from apps.validation.models import Participant, Visit

CODE = 'idice-test-7Kq2xP9mLw'
ACCESS = {'idice': {'label': 'iDICE', 'code': CODE, 'expires': ''}}


@override_settings(GUEST_ACCESS=ACCESS)
class GuestAccessTests(TestCase):
    def open_link(self):
        response = self.client.get(f'/access/{CODE}/')
        self.assertEqual(response.status_code, 302)
        return self.client.get(response['Location'])

    def test_normal_visitors_see_the_usual_landing(self):
        page = self.client.get(reverse('landing'))
        self.assertNotContains(page, 'guest-ribbon')
        self.assertContains(page, 'Try the workspace')
        self.assertNotContains(page, 'Enter as iDICE')

    def test_wrong_code_is_404_and_enter_needs_the_link(self):
        self.assertEqual(self.client.get('/access/not-the-code/').status_code, 404)
        self.assertRedirects(self.client.get(reverse('guest-enter', args=['idice'])), reverse('landing'))
        self.assertRedirects(self.client.post(reverse('guest-enter', args=['idice'])), reverse('landing'))
        self.assertFalse(Participant.objects.exists())

    def test_link_shows_landing_with_enter_and_one_click_creates_own_workspace(self):
        page = self.open_link()
        self.assertContains(page, 'Welcome, iDICE reviewers.')
        self.assertContains(page, 'Enter as iDICE', count=4)
        self.assertContains(page, 'A clearer picture.')  # the full landing page is still there
        self.assertContains(page, 'data-guest-form')
        self.assertEqual(Visit.objects.get().source, 'idice')
        # GET is a harmless confirmation page (link previews never create accounts)
        self.assertContains(self.client.get(reverse('guest-enter', args=['idice'])), 'No sign-up or password is needed')
        self.assertFalse(Participant.objects.exists())
        response = self.client.post(reverse('guest-enter', args=['idice']))
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)
        participant = Participant.objects.get()
        self.assertEqual((participant.source, participant.campaign, participant.organisation), ('idice', 'guest-link', 'iDICE'))
        self.assertFalse(participant.user.has_usable_password())
        self.assertEqual(Patient.objects.filter(facility=participant.facility, is_synthetic=True).count(), 4)
        self.assertTrue(participant.facility.is_demo)
        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard, 'iDICE reviewer')
        self.assertContains(dashboard, 'Welcome, iDICE reviewer.')
        # back on the landing page while signed in
        self.assertContains(self.client.get(reverse('landing')), 'Open your workspace')

    def test_same_browser_returns_to_same_workspace_new_browser_gets_new_one(self):
        self.open_link(); self.client.post(reverse('guest-enter', args=['idice']))
        first = Participant.objects.get().user
        self.client.post(reverse('logout'))
        self.open_link(); self.client.post(reverse('guest-enter', args=['idice']))
        self.assertEqual(Participant.objects.count(), 1)
        self.assertEqual(int(self.client.session['_auth_user_id']), first.pk)
        other = self.client_class()
        link = other.get(f'/access/{CODE}/'); other.get(link['Location'])
        other.post(reverse('guest-enter', args=['idice']))
        self.assertEqual(Participant.objects.count(), 2)
        self.assertEqual(Participant.objects.order_by('created_at').last().user.last_name, 'Reviewer 2')

    def test_expired_link_and_capacity(self):
        expired = {'idice': dict(ACCESS['idice'], expires=str(date.today() - timedelta(days=1)))}
        with self.settings(GUEST_ACCESS=expired):
            self.assertContains(self.client.get(f'/access/{CODE}/'), 'has expired', status_code=410)
        with self.settings(GUEST_ACCESS_MAX_WORKSPACES=0):
            self.open_link()
            self.assertRedirects(self.client.post(reverse('guest-enter', args=['idice'])), reverse('landing'), fetch_redirect_response=False)
            self.assertFalse(Participant.objects.exists())

    def test_disabled_when_no_code_configured(self):
        with self.settings(GUEST_ACCESS={}):
            self.assertEqual(self.client.get(f'/access/{CODE}/').status_code, 404)

    def test_robots_hides_access_links(self):
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /access/')
