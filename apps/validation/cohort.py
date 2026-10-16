"""One definition of the analytics cohort, shared by the analytics page and the PDF exports."""
from datetime import timedelta
from django.utils import timezone
from .models import Participant, Visit, WalkthroughRound, Feedback, Lead, ROLES

PERIODS = {'7': 'Last 7 days', '30': 'Last 30 days', '90': 'Last 90 days', 'all': 'All time'}


def cohort(params):
    days = params.get('days', '30')
    if days not in PERIODS:
        days = '30'
    since = timezone.now() - timedelta(days=int(days)) if days != 'all' else None
    participants = Participant.objects.select_related('user')
    visits = Visit.objects.all()
    leads = Lead.objects.select_related('participant', 'feedback')
    if since:
        participants = participants.filter(created_at__gte=since)
        visits = visits.filter(started_at__gte=since)
        leads = leads.filter(created_at__gte=since)
    source = params.get('source', '')[:80]
    role = params.get('role', '')
    if source:
        participants = participants.filter(source=source); visits = visits.filter(source=source); leads = leads.filter(source=source)
    if role in dict(ROLES):
        participants = participants.filter(role=role); leads = leads.filter(role=role)
    else:
        role = ''
    # Completion is a registration cohort: returning later still counts for the same participant.
    rounds = WalkthroughRound.objects.filter(participant__in=participants).select_related(
        'case__patient', 'case__attachment', 'case__qualityassessment', 'case__aiassessment', 'participant__user'
    ).prefetch_related('case__clinical_decisions')
    responses = Feedback.objects.filter(round__in=rounds)
    return {'days': days, 'since': since, 'period': PERIODS[days], 'source': source, 'role': role,
            'role_label': dict(ROLES).get(role, ''), 'participants': participants, 'visits': visits, 'leads': leads,
            'rounds': rounds, 'responses': responses}
