"""Private organisation access links.

/access/<code>/  -> marks this browser as invited (e.g. iDICE) and opens the landing page,
                    which then offers a one-click "Enter as iDICE".
/access/<org>/enter/ -> GET shows a confirmation page (safe for link previews);
                    POST signs the reviewer into their own guest workspace.
A signed cookie lets the same browser return to the same workspace later.
"""
import hmac
import uuid
from datetime import date
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.core import signing
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.organizations.models import Facility, Membership
from .models import Participant, Visit
from .services import seed_sample_patients

SESSION_KEY = 'guest_access'
COOKIE = 'vos_guest'
COOKIE_SALT = 'vanara.guest-access'
COOKIE_AGE = 60 * 60 * 24 * 60  # 60 days


def _config(org):
    cfg = getattr(settings, 'GUEST_ACCESS', {}).get(org)
    return dict(cfg, key=org) if cfg and cfg.get('code') else None


def _expired(cfg):
    try:
        return bool(cfg.get('expires')) and date.today() > date.fromisoformat(cfg['expires'])
    except ValueError:
        return False


def invited_org(request):
    """The organisation this browser was invited through, if the link is still active."""
    cfg = _config(request.session.get(SESSION_KEY, ''))
    return cfg if cfg and not _expired(cfg) else None


def landing_context(request):
    cfg = invited_org(request)
    if not cfg:
        from django.urls import reverse
        return {'workspace_url': reverse('signup'), 'workspace_label': 'Try the workspace', 'guest': None}
    from django.urls import reverse
    if request.user.is_authenticated:
        return {'workspace_url': reverse('dashboard'), 'workspace_label': 'Open your workspace', 'guest': cfg, 'guest_signed_in': True}
    return {'workspace_url': reverse('guest-enter', args=[cfg['key']]), 'workspace_label': f"Enter as {cfg['label']}", 'guest': cfg}


@never_cache
def access_link(request, code):
    for org, cfg in getattr(settings, 'GUEST_ACCESS', {}).items():
        if cfg.get('code') and hmac.compare_digest(str(code), str(cfg['code'])):
            cfg = dict(cfg, key=org)
            if _expired(cfg):
                return render(request, 'validation/guest_expired.html', {'guest': cfg}, status=410)
            request.session[SESSION_KEY] = org
            from django.urls import reverse
            return redirect(reverse('landing') + f'?utm_source={org}&utm_campaign=guest-link')
    raise Http404


def _returning_user(request, org):
    try:
        value = request.get_signed_cookie(COOKIE, salt=COOKIE_SALT, max_age=COOKIE_AGE)
        cookie_org, user_id = value.split(':', 1)
    except (KeyError, ValueError, signing.BadSignature):
        return None
    if cookie_org != org:
        return None
    return get_user_model().objects.filter(pk=user_id, is_active=True, participant__source=org,
                                           participant__campaign='guest-link').first()


@transaction.atomic
def _create_guest(request, cfg):
    number = Participant.objects.filter(source=cfg['key'], campaign='guest-link').count() + 1
    token = uuid.uuid4().hex
    user = get_user_model().objects.create_user(username=f"guest_{cfg['key']}_{token[:12]}", first_name=cfg['label'],
                                                last_name=f'Reviewer {number}', email='')
    user.set_unusable_password()
    user.save(update_fields=['password'])
    facility = Facility.objects.create(name=f"{cfg['label']} review workspace {number}", slug=f"guest-{cfg['key']}-{token}", is_demo=True)
    Membership.objects.create(user=user, facility=facility, role=Membership.Role.FACILITY)
    participant = Participant.objects.create(user=user, facility=facility, role='Other', organisation=cfg['label'], source=cfg['key'],
                                             campaign='guest-link', research_consent_at=timezone.now())
    seed_sample_patients(facility)
    Visit.objects.filter(pk=request.session.get('validation_visit')).update(participant=participant)
    return user


@never_cache
@require_http_methods(['GET', 'POST'])
def enter(request, org):
    cfg = invited_org(request)
    if not cfg or cfg['key'] != org:
        return redirect('landing')
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'GET':
        return render(request, 'validation/guest_enter.html', {'guest': cfg})
    user = _returning_user(request, org)
    welcome = f"Welcome back. Your {cfg['label']} review workspace is just as you left it."
    if not user:
        if Participant.objects.filter(campaign='guest-link').count() >= settings.GUEST_ACCESS_MAX_WORKSPACES:
            messages.error(request, 'Review access is temporarily full. Please contact info@vanaraoncoscan.cyou.')
            return redirect('landing')
        user = _create_guest(request, cfg)
        welcome = f"Welcome, {cfg['label']} reviewer. Your workspace is ready, with sample patients to try."
    login(request, user, backend='apps.accounts.backends.EmailBackend')
    request.session[SESSION_KEY] = org
    messages.success(request, welcome)
    response = redirect('dashboard')
    response.set_signed_cookie(COOKIE, f'{org}:{user.pk}', salt=COOKIE_SALT, max_age=COOKIE_AGE,
                               secure=request.is_secure(), httponly=True, samesite='Lax')
    return response
