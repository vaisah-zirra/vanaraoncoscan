"""Validation evidence: turns the analytics cohort into structured, shareable insights.

Everything here is computed from recorded activity (registrations, walkthrough rounds,
survey responses and enquiries). Nothing is estimated or invented: if a number is not
recorded it is reported as such.
"""
import hashlib
import re
import json
import statistics
from collections import Counter
from django.db.models import Count
from django.utils import timezone
from .feedback_choices import USEFUL_PARTS, FACTOR_LABELS
from .models import INTENTS, ROLES, Lead
from .services import round_progress

ROLE_LABELS = dict(ROLES)
USEFUL_LABELS = dict(USEFUL_PARTS)
INTENT_LABELS = dict(INTENTS)
INTEREST_LABELS = {
    'Practice': 'Practice subscription', 'Clinic': 'Clinic subscription', 'Network': 'Network subscription',
    'Partnership': 'Partnership or research', 'General': 'General enquiry', 'Demo': 'Guided demonstration',
    'Pilot': 'Pilot discussion', 'Waitlist': 'Waitlist', 'Pricing': 'Pricing discussion', 'Deployment': 'Deployment discussion',
}
STAGE_ORDER = [code for code, _ in Lead.STAGES]
STAGE_LABELS = dict(Lead.STAGES)
DECISION_LABELS = {'ROUTINE': 'Returned to routine care', 'REFERRAL': 'Referral confirmed',
                   'FOLLOW_UP': 'Follow-up scheduled', 'SPECIALIST': 'Specialist review requested'}

# Keyword themes for written survey answers. Simple, transparent and auditable:
# a response counts towards a theme when it mentions one of its words.
THEMES = [
    ('Speed and ease of use', ['fast', 'quick', 'speed', 'easy', 'simple', 'intuitive', 'smooth', 'user friendly', 'user-friendly', 'seamless', 'straightforward', 'time']),
    ('Accuracy and clinical trust', ['accura', 'trust', 'reliab', 'evidence', 'validat', 'false', 'sensitiv', 'specific', 'precis', 'correct']),
    ('Cost and access', ['cost', 'price', 'pricing', 'afford', 'cheap', 'expensive', 'free', 'subscription', 'pay']),
    ('Training and guidance', ['train', 'learn', 'guide', 'tutorial', 'onboard', 'explain', 'help', 'instruction']),
    ('Connectivity and devices', ['internet', 'offline', 'network', 'phone', 'mobile', 'device', 'power', 'electric', 'bandwidth', 'slow']),
    ('Integration with existing systems', ['integrat', 'emr', 'ehr', 'pacs', 'dicom', 'hospital system', 'existing system', 'machine', 'scanner']),
    ('Specialist and referral workflow', ['specialist', 'radiolog', 'referr', 'follow-up', 'follow up', 'telerad', 'second opinion', 'second read']),
    ('Reports and documentation', ['report', 'pdf', 'document', 'print', 'record']),
    ('Privacy and regulation', ['privacy', 'secur', 'consent', 'regulat', 'approv', 'nafdac', 'ndpr', 'data protection', 'confidential']),
    ('Design and interface', ['design', 'interface', 'layout', 'look', 'colour', 'color', 'font', 'button', 'screen', 'beautiful']),
]


def _pct(part, whole):
    return round(part / whole * 100) if whole else 0


def _ranked(counter, labels=None, total=None):
    total = total if total is not None else sum(counter.values())
    return [{'label': (labels or {}).get(key, key) or 'Not recorded', 'n': n, 'pct': _pct(n, total)} for key, n in counter.most_common()]


def _themes(texts):
    rows = []
    for name, words in THEMES:
        pattern = re.compile('|'.join(r'\b' + re.escape(w) for w in words), re.IGNORECASE)
        scored = [(len(pattern.findall(t['text'])), t) for t in texts]
        hits = [t for n, t in scored if n]
        if hits:
            best = max(scored, key=lambda pair: (pair[0], pair[1]['rating']))[1]
            rows.append({'theme': name, 'n': len(hits), 'pct': _pct(len(hits), len(texts)), 'quote': best})
    rows.sort(key=lambda r: -r['n'])
    return rows


def _minutes(delta):
    return round(delta.total_seconds() / 60, 1)


def build(c, identity='anonymised'):
    """Collect every figure the evidence report needs from one analytics cohort."""
    named = identity == 'named'
    participants = list(c['participants'].order_by('created_at', 'pk'))
    rounds = list(c['rounds'])
    responses = list(c['responses'].select_related('round__participant__user').order_by('created_at'))
    leads = list(c['leads'].order_by('created_at', 'pk'))
    visits = c['visits']

    # Stable pseudonyms inside this report: P-01 is the earliest registration in the cohort.
    alias = {p.pk: f'P-{i:02d}' for i, p in enumerate(participants, 1)}

    def who(participant):
        if not participant:
            return 'Unregistered visitor'
        if named:
            return participant.user.get_full_name() or participant.user.username
        return alias.get(participant.pk, 'Participant')

    progress = [round_progress(r) for r in rounds]
    by_participant = {}
    for item in progress:
        by_participant.setdefault(item['round'].participant_id, []).append(item)
    feedback_by_participant = {}
    for f in responses:
        feedback_by_participant.setdefault(f.round.participant_id, []).append(f)

    # ---- Engagement funnel -------------------------------------------------
    started_ids = {r.participant_id for r in rounds}
    completed_rounds = [r for r in rounds if r.completed_at]
    finisher_ids = {r.participant_id for r in completed_rounds}
    responder_ids = {f.round.participant_id for f in responses}
    landing = visits.filter(landing_seen=True).count()
    funnel = [
        {'label': 'Visited the landing page', 'n': landing},
        {'label': 'Registered for the workspace', 'n': len(participants)},
        {'label': 'Started a case', 'n': len(started_ids)},
        {'label': 'Completed the full journey', 'n': len(finisher_ids)},
        {'label': 'Left survey feedback', 'n': len(responder_ids)},
    ]
    for i, step in enumerate(funnel):
        prev = funnel[i - 1]['n'] if i else None
        # Only show a conversion where it is meaningful (people can register without a tracked landing visit).
        step['conv'] = _pct(step['n'], prev) if prev and step['n'] <= prev else None
    funnel.append({'label': 'Enquiries received (all channels)', 'n': len(leads), 'conv': None})

    # ---- Who took part -----------------------------------------------------
    roles = _ranked(Counter(p.role for p in participants), ROLE_LABELS, len(participants))
    sources = _ranked(Counter(p.source or 'direct' for p in participants), None, len(participants))
    orgs = Counter((p.organisation or '').strip() for p in participants if (p.organisation or '').strip())
    visit_sources = [{'label': row['source'] or 'direct', 'n': row['n']} for row in visits.values('source').order_by().annotate(n=Count('pk')).order_by('-n')]

    # ---- Walkthrough completion -------------------------------------------
    durations = [_minutes(r.completed_at - r.started_at) for r in completed_rounds if r.started_at]
    quality_path = sum(1 for item in progress if item['failed_quality'])
    decisions = Counter()
    specialist_reads = 0
    for r in rounds:
        for d in r.case.clinical_decisions.all():
            decisions[d.action] += 1
        specialist_reads += r.case.specialistreview_set.count()
    pauses = Counter(item['next_label'] for item in progress if not item['round'].completed_at)
    completion = {
        'rounds': len(rounds), 'completed': len(completed_rounds), 'rate': _pct(len(completed_rounds), len(rounds)),
        'finishers': len(finisher_ids), 'started': len(started_ids),
        'median_minutes': statistics.median(durations) if durations else None,
        'fastest_minutes': min(durations) if durations else None,
        'quality_path': quality_path, 'assessment_path': len(rounds) - quality_path,
        'decisions': _ranked(decisions, DECISION_LABELS), 'specialist_reads': specialist_reads,
        'pauses': _ranked(pauses),
        'repeat_users': sum(1 for items in by_participant.values() if len(items) > 1),
    }

    # ---- Survey responses --------------------------------------------------
    ratings = [f.rating for f in responses]
    distribution = [{'label': f'{star} star' + ('' if star == 1 else 's'), 'star': star, 'n': ratings.count(star),
                     'pct': _pct(ratings.count(star), len(ratings))} for star in (5, 4, 3, 2, 1)]
    factor_counter = Counter()
    for f in responses:
        factor_counter.update(set(f.barriers or ([f.barrier] if f.barrier else [])))
    written = [{'text': f.suggestion.strip(), 'rating': f.rating, 'who': who(f.round.participant),
                'role': ROLE_LABELS.get(f.round.participant.role, ''), 'organisation': f.round.participant.organisation,
                'date': f.created_at, 'intent': INTENT_LABELS.get(f.intent, f.intent)}
               for f in responses if (f.suggestion or '').strip()]
    survey = {
        'n': len(responses), 'respondents': len(responder_ids),
        'average': round(sum(ratings) / len(ratings), 2) if ratings else None,
        'median': statistics.median(ratings) if ratings else None,
        'top2': _pct(sum(1 for r in ratings if r >= 4), len(ratings)),
        'low': sum(1 for r in ratings if r <= 2),
        'distribution': distribution,
        'most_useful': _ranked(Counter(f.most_useful for f in responses), USEFUL_LABELS, len(responses)),
        'factors': _ranked(factor_counter, FACTOR_LABELS, len(responses)),
        'intents': _ranked(Counter(f.intent for f in responses), INTENT_LABELS, len(responses)),
        'wants_next_step': sum(1 for f in responses if f.intent != 'None'),
        'contact_ok': sum(1 for f in responses if f.contact_consent),
        'avg_completion': round(sum(f.completion_at_submission for f in responses) / len(responses)) if responses else None,
        'written': written, 'themes': _themes(written),
        'by_role': [],
    }
    role_ratings = {}
    for f in responses:
        role_ratings.setdefault(f.round.participant.role, []).append(f.rating)
    survey['by_role'] = sorted(({'label': ROLE_LABELS.get(k, k), 'n': len(v), 'average': round(sum(v) / len(v), 1)} for k, v in role_ratings.items()),
                               key=lambda r: (-r['n'], r['label']))

    # ---- Participant register ---------------------------------------------
    register = []
    for p in participants:
        items = by_participant.get(p.pk, [])
        fb = feedback_by_participant.get(p.pk, [])
        register.append({
            'who': who(p), 'email': p.user.email if named and p.user.email and '.invalid' not in p.user.email else '',
            'whatsapp': p.whatsapp if named and p.whatsapp_consent else '',
            'role': ROLE_LABELS.get(p.role, p.role), 'organisation': p.organisation, 'source': p.source or 'direct',
            'registered': p.created_at, 'last_seen': p.last_seen, 'rounds': len(items),
            'completed': sum(1 for i in items if i['round'].completed_at),
            'best': max((100 if i['round'].completed_at else i['percent'] for i in items), default=0),
            'rating': fb[-1].rating if fb else None,
            'useful': USEFUL_LABELS.get(fb[-1].most_useful, '') if fb else '',
            'intent': INTENT_LABELS.get(fb[-1].intent, '') if fb else '',
        })

    # ---- Interest & pipeline ----------------------------------------------
    lead_rows = []
    for i, lead in enumerate(leads, 1):
        lead_rows.append({
            'who': (lead.name if named else f'E-{i:02d}'),
            'email': lead.email if named else '', 'whatsapp': lead.whatsapp if named and lead.whatsapp_consent else '',
            'organisation': lead.organisation, 'role': ROLE_LABELS.get(lead.role, lead.role) if lead.role else '',
            'interest': INTEREST_LABELS.get(lead.interest, lead.interest), 'stage': STAGE_LABELS.get(lead.stage, lead.stage),
            'next_action': lead.next_action, 'next_date': lead.next_action_date, 'message': (lead.message or '').strip(),
            'source': lead.source or 'direct', 'date': lead.created_at,
            'tried': bool(lead.participant_id), 'origin': 'Website contact form' if lead.enquiry_id else ('Post-walkthrough survey' if lead.feedback_id else 'Pilot / interest form'),
        })
    stage_counter = Counter(lead.stage for lead in leads)
    interest = {
        'n': len(leads), 'rows': lead_rows,
        'by_type': _ranked(Counter(lead.interest for lead in leads), INTEREST_LABELS, len(leads)),
        'pipeline': [{'label': STAGE_LABELS[s], 'n': stage_counter.get(s, 0), 'pct': _pct(stage_counter.get(s, 0), len(leads))} for s in STAGE_ORDER],
        'by_role': _ranked(Counter(lead.role for lead in leads if lead.role), ROLE_LABELS),
        'by_source': _ranked(Counter(lead.source or 'direct' for lead in leads)),
        'organisations': sorted({(lead.organisation or '').strip() for lead in leads if (lead.organisation or '').strip()}),
        'tried': sum(1 for lead in leads if lead.participant_id),
        'demos': sum(1 for lead in leads if lead.interest == 'Demo'),
        'pilots': sum(1 for lead in leads if lead.interest in ('Pilot', 'Waitlist')),
        'commercial': sum(1 for lead in leads if lead.interest in ('Pricing', 'Deployment', 'Practice', 'Clinic', 'Network')),
        'partnership': sum(1 for lead in leads if lead.interest == 'Partnership'),
        'progressed': sum(1 for lead in leads if lead.stage not in ('New', 'Closed')),
    }

    data = {
        'generated': timezone.now(), 'identity': 'named' if named else 'anonymised',
        'filters': {'period': c['period'], 'source': c['source'] or 'All sources', 'role': c['role_label'] or 'All roles'},
        'totals': {'landing': landing, 'sessions': visits.count(), 'participants': len(participants),
                   'organisations': len(orgs), 'top_orgs': orgs.most_common(12)},
        'funnel': funnel, 'roles': roles, 'sources': sources, 'visit_sources': visit_sources,
        'completion': completion, 'survey': survey, 'register': register, 'interest': interest,
    }
    data['findings'] = findings(data)
    fingerprint_source = json.dumps({'funnel': [s['n'] for s in funnel], 'ratings': ratings, 'leads': [l.pk for l in leads],
                                     'participants': [p.pk for p in participants], 'filters': data['filters']}, sort_keys=True)
    data['fingerprint'] = hashlib.sha256(fingerprint_source.encode()).hexdigest()
    data['reference'] = 'VAL-' + data['generated'].strftime('%Y%m%d') + '-' + data['fingerprint'][:6].upper()
    return data


def findings(d):
    """Plain-language key findings, written only from the recorded figures."""
    out = []
    f = {s['label']: s['n'] for s in d['funnel']}
    reg = d['totals']['participants']; comp = d['completion']; sv = d['survey']; it = d['interest']
    if reg:
        line = f"{reg} participant{'s' if reg != 1 else ''} registered"
        if d['totals']['organisations']:
            line += f" from {d['totals']['organisations']} organisation{'s' if d['totals']['organisations'] != 1 else ''}"
        line += f"; {comp['started']} ({_pct(comp['started'], reg)}%) started a case and {comp['finishers']} ({_pct(comp['finishers'], reg)}%) completed the full scan-to-report journey."
        out.append(line)
        if d['roles']:
            top = d['roles'][0]
            out.append(f"Most common self-reported role: {top['label']} ({top['n']} of {reg}, {top['pct']}%).")
    if comp['rounds']:
        line = f"Across {comp['rounds']} walkthrough round{'s' if comp['rounds'] != 1 else ''}, {comp['rate']}% were completed"
        if comp['median_minutes'] is not None:
            line += f", with a median time of {comp['median_minutes']:g} minutes from first upload to final report"
        out.append(line + '.')
    if sv['n']:
        out.append(f"Participants rated the workflow {sv['average']:.1f} out of 5 on average ({sv['n']} response{'s' if sv['n'] != 1 else ''}); {sv['top2']}% gave 4 or 5 stars.")
        if sv['most_useful']:
            top = sv['most_useful'][0]
            out.append(f"Most valued part of the platform: {top['label']} ({top['n']} of {sv['n']} responses).")
        if sv['factors']:
            top = sv['factors'][0]
            out.append(f"Top factor that would influence adoption: {top['label']} (mentioned in {top['pct']}% of responses).")
        if sv['wants_next_step']:
            out.append(f"{sv['wants_next_step']} respondent{'s' if sv['wants_next_step'] != 1 else ''} asked for a next step after trying the workspace (pilot, demo, pricing or deployment).")
        if sv['themes']:
            out.append('Recurring themes in written feedback: ' + '; '.join(t['theme'] for t in sv['themes'][:3]) + '.')
    if it['n']:
        line = f"{it['n']} enquir{'ies' if it['n'] != 1 else 'y'} received"
        parts = []
        if it['pilots']: parts.append(f"{it['pilots']} pilot/waitlist")
        if it['demos']: parts.append(f"{it['demos']} demo")
        if it['commercial']: parts.append(f"{it['commercial']} subscription, pricing or deployment")
        if it['partnership']: parts.append(f"{it['partnership']} partnership")
        if parts: line += ' (' + ', '.join(parts) + ')'
        if it['tried']: line += f"; {it['tried']} came from people who had used the workspace"
        out.append(line + '.')
    if not out:
        out.append('No participant activity has been recorded for the selected period and filters yet.')
    return out
