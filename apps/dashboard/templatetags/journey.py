"""Case journey stepper shown across the top of every case workflow page."""
from django import template
from django.urls import reverse

register = template.Library()

STAGES = [
    ('patient', 'Patient & history'),
    ('image', 'Ultrasound'),
    ('quality', 'Quality check'),
    ('assessment', 'AI assessment'),
    ('care', 'Care plan'),
    ('report', 'Report'),
]


def _round(user, case):
    from apps.validation.models import WalkthroughRound
    return WalkthroughRound.objects.filter(case=case, participant__user=user).select_related('case').first()


@register.inclusion_tag('components/case_journey.html', takes_context=True)
def case_journey(context, case=None, current='auto'):
    on_page = True
    request = context.get('request')
    user = getattr(request, 'user', None)
    done, urls, blocked = {}, {}, set()
    walk = None
    if case is None:
        done = {key: False for key, _ in STAGES}
        current = 'patient'
    else:
        quality = getattr(case, 'qualityassessment', None)
        assessment = getattr(case, 'aiassessment', None)
        failed = quality is not None and not quality.adequate
        rnd = _round(user, case) if user and user.is_authenticated else None
        has_plan = case.clinical_decisions.exists() or hasattr(case, 'referral') or case.followup_set.exists()
        done = {
            'patient': True,
            'image': hasattr(case, 'attachment'),
            'quality': quality is not None and quality.adequate,
            'assessment': assessment is not None and not failed,
            'care': has_plan,
            'report': bool(rnd and rnd.report_requested_at) or (has_plan and case.caseevent_set.filter(kind='CASE_REPORT_ISSUED').exists()),
        }
        if failed:
            blocked = {'quality'}
        editable = case.status in ('DRAFT', 'QUALITY_PENDING')
        urls = {
            'patient': reverse('case-detail', args=[case.pk]),
            'image': reverse('image-upload', args=[case.pk]) if editable else reverse('case-detail', args=[case.pk]),
            'quality': reverse('quality-check', args=[case.pk]) if hasattr(case, 'attachment') else None,
            'assessment': reverse('assessment-result', args=[case.pk]) if assessment and not failed else None,
            'care': reverse('clinician-review', args=[case.pk]) if assessment and not failed else None,
            'report': reverse('case-report-stage', args=[case.pk]) if has_plan else None,
        }
        if rnd:
            from apps.validation.services import round_progress
            walk = round_progress(rnd)['percent']
        if current == 'auto':
            on_page = False
            current = next((key for key, _ in STAGES if not done[key]), 'report')
    keys = [key for key, _ in STAGES]
    index = keys.index(current)
    steps = []
    for i, (key, label) in enumerate(STAGES):
        state = 'blocked' if key in blocked else 'current' if key == current else 'done' if done.get(key) else 'upcoming'
        if not on_page and done.get(key) and key not in blocked:
            state = 'done'  # overview pages: a finished case shows every stage complete
        if state == 'done' and i > index and not done.get(key):
            state = 'upcoming'
        note = {'done': 'Done', 'current': 'You are here', 'blocked': 'Needs a new image', 'upcoming': ''}[state]
        if state == 'current' and done.get(key):
            note = 'Viewing'
        steps.append({'key': key, 'label': label, 'state': state, 'note': note, 'n': i + 1,
                      'url': urls.get(key) if state in ('done', 'blocked') or (key == 'report' and not (state == 'current' and on_page)) else None})
    completed = sum(1 for key in keys if done.get(key))
    return {'steps': steps, 'fill': round(index / (len(STAGES) - 1) * 100), 'completed': completed,
            'total': len(STAGES), 'walk': walk, 'on_page': on_page, 'participant': context.get('validation_participant'), 'case': case}
