"""Data for the validation dashboard: KPI cards, small SVG charts and the people lists.

Charts are drawn server-side as inline SVG so the page has no chart library and
looks the same in every browser and in screenshots.
"""
import math
from collections import Counter
from datetime import timedelta
from django.utils import timezone
from .feedback_choices import USEFUL_PARTS, FACTOR_LABELS
from .models import INTENTS, ROLES, Lead, Visit
from .services import round_progress

ROLE_LABELS = dict(ROLES)
USEFUL_LABELS = dict(USEFUL_PARTS)
INTENT_LABELS = dict(INTENTS)
STAGE_LABELS = dict(Lead.STAGES)
INTEREST_LABELS = {'Practice': 'Practice subscription', 'Clinic': 'Clinic subscription', 'Network': 'Network subscription',
                   'Partnership': 'Partnership / research', 'General': 'General enquiry', 'Demo': 'Guided demo',
                   'Pilot': 'Pilot', 'Waitlist': 'Waitlist', 'Pricing': 'Pricing', 'Deployment': 'Deployment'}
PALETTE = ['#147c70', '#dc795a', '#2f6f8a', '#c49a2c', '#7a63b8', '#3f8f6b', '#a8324a', '#6b7f7f']


def _initials(name):
    titles = {'dr', 'prof', 'mr', 'mrs', 'ms', 'miss', 'pharm', 'nurse', 'engr', 'chief'}
    parts = [p for p in (name or '').replace('.', ' ').split() if p[:1].isalpha() and p.lower() not in titles]
    return ((parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')) if parts else '?').upper()


def _local_day(value):
    return timezone.localtime(value).date()


def _buckets(days, earliest):
    today = timezone.localdate()
    span = int(days) if days != 'all' else max(14, min(365, (today - earliest).days + 1 if earliest else 30))
    step = 1 if span <= 45 else 7
    count = math.ceil(span / step)
    starts = [today - timedelta(days=step * (count - 1 - i)) - timedelta(days=step - 1) for i in range(count)]
    return starts, step


def _series(values, starts, step):
    counts = [0] * len(starts)
    for day in values:
        for i in range(len(starts) - 1, -1, -1):
            if day >= starts[i]:
                if day < starts[i] + timedelta(days=step):
                    counts[i] += 1
                break
    return counts


def _smooth(points):
    """Catmull-Rom → cubic Bézier path through the points."""
    if not points:
        return ''
    d = f'M{points[0][0]:.1f},{points[0][1]:.1f}'
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f' C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}'
    return d


def trend_chart(starts, step, series, width=660, height=230):
    left, right, top, bottom = 34, 12, 14, 30
    iw, ih = width - left - right, height - top - bottom
    peak = max([max(s['values']) for s in series] + [1])
    nice = max(4, math.ceil(peak / 4) * 4)
    n = len(starts)
    x = lambda i: left + (iw * i / (n - 1) if n > 1 else iw / 2)
    y = lambda v: top + ih - ih * v / nice
    lines = []
    for s in series:
        pts = [(x(i), y(v)) for i, v in enumerate(s['values'])]
        path = _smooth(pts)
        area = f'{path} L{pts[-1][0]:.1f},{top + ih:.1f} L{pts[0][0]:.1f},{top + ih:.1f} Z' if pts else ''
        label = (lambda d: d.strftime('%d %b')) if step == 1 else (lambda d: 'Week of ' + d.strftime('%d %b'))
        dots = [{'x': round(px, 1), 'y': round(py, 1), 'v': v, 'tip': f"{label(starts[i])}: {v} {s['unit']}"} for i, ((px, py), v) in enumerate(zip(pts, s['values']))]
        lines.append(dict(s, path=path, area=area, dots=dots, total=sum(s['values'])))
    grid = [{'y': round(y(nice * k / 4), 1), 'label': int(nice * k / 4)} for k in range(5)]
    every = max(1, round(n / 6))
    ticks = [{'x': round(x(i), 1), 'label': starts[i].strftime('%d %b')} for i in range(0, n, every)]
    return {'width': width, 'height': height, 'lines': lines, 'grid': grid, 'ticks': ticks, 'left': left, 'right': width - right, 'base': top + ih}


def donut(parts, r=62, stroke=18):
    total = sum(p['n'] for p in parts)
    circ = 2 * math.pi * r
    offset, out = 0.0, []
    for p in parts:
        length = circ * p['n'] / total if total else 0
        out.append(dict(p, dash=f'{length:.2f} {circ - length:.2f}', offset=f'{-offset:.2f}', pct=round(p['n'] / total * 100) if total else 0))
        offset += length
    return {'parts': out, 'total': total, 'r': r, 'stroke': stroke, 'size': (r + stroke) * 2, 'c': r + stroke, 'circ': f'{circ:.2f}'}


def bars(counter, labels=None, limit=6, colors=PALETTE):
    total = sum(counter.values()) or 1
    top = counter.most_common(limit)
    peak = max([n for _, n in top] + [1])
    return [{'label': (labels or {}).get(k, k) or 'Direct', 'n': n, 'pct': round(n / total * 100), 'w': round(n / peak * 100),
             'color': colors[i % len(colors)]} for i, (k, n) in enumerate(top)]


def build(c, user):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    participants = list(c['participants'].order_by('-created_at', '-pk'))
    rounds = list(c['rounds'])
    responses = list(c['responses'].select_related('round__participant__user').order_by('-created_at'))
    leads = list(c['leads'].order_by('-created_at', '-pk'))
    visits = c['visits']
    landing_visits = list(visits.filter(landing_seen=True).values_list('started_at', 'source'))

    progress = {}
    for item in (round_progress(r) for r in rounds):
        progress.setdefault(item['round'].participant_id, []).append(item)
    feedback = {}
    for f in responses:
        feedback.setdefault(f.round.participant_id, f)  # newest first

    # ---- People --------------------------------------------------------
    registered, completed = [], []
    for p in participants:
        items = progress.get(p.pk, [])
        done = [i['round'] for i in items if i['round'].completed_at]
        best = max((100 if i['round'].completed_at else i['percent'] for i in items), default=0)
        name = p.user.get_full_name() or p.user.username
        email = p.user.email if p.user.email and '.invalid' not in p.user.email else ''
        fb = feedback.get(p.pk)
        row = {'name': name, 'initials': _initials(name), 'email': email, 'whatsapp': p.whatsapp if p.whatsapp_consent else '',
               'organisation': p.organisation, 'role': ROLE_LABELS.get(p.role, p.role), 'source': p.source or 'direct',
               'joined': p.created_at, 'last_seen': p.last_seen, 'rounds': len(items), 'best': best,
               'status': 'Completed' if done else ('In progress' if items else 'Not started'),
               'rating': fb.rating if fb else None, 'comment': (fb.suggestion or '').strip() if fb else '',
               'useful': USEFUL_LABELS.get(fb.most_useful, '') if fb else '', 'intent': INTENT_LABELS.get(fb.intent, '') if fb and fb.intent != 'None' else ''}
        registered.append(row)
        if done:
            first = min(done, key=lambda r: r.completed_at)
            minutes = round((first.completed_at - first.started_at).total_seconds() / 60) if first.started_at else None
            completed.append(dict(row, completed_at=max(r.completed_at for r in done), first_completed=first.completed_at, minutes=minutes, completions=len(done)))
    completed.sort(key=lambda r: r['completed_at'], reverse=True)

    def lead_row(lead):
        return {'pk': lead.pk, 'name': lead.name, 'initials': _initials(lead.name), 'email': lead.email,
                'whatsapp': lead.whatsapp if lead.whatsapp_consent else '', 'organisation': lead.organisation,
                'role': ROLE_LABELS.get(lead.role, lead.role) if lead.role else '', 'interest': INTEREST_LABELS.get(lead.interest, lead.interest),
                'stage': STAGE_LABELS.get(lead.stage, lead.stage), 'stage_key': lead.stage.lower(), 'message': (lead.message or '').strip(),
                'next_action': lead.next_action, 'source': lead.source or 'direct', 'date': lead.created_at, 'tried': bool(lead.participant_id)}
    pilot = [lead_row(l) for l in leads if l.interest == 'Pilot']
    waitlist = [lead_row(l) for l in leads if l.interest == 'Waitlist']
    other = [lead_row(l) for l in leads if l.interest not in ('Pilot', 'Waitlist')]

    # ---- KPI cards -----------------------------------------------------
    finishers = [r for r in completed]
    def recent(values):
        return sum(1 for v in values if v and v >= week_ago)
    kpis = [
        {'key': 'visits', 'label': 'Landing page visits', 'value': len(landing_visits), 'week': recent(v for v, _ in landing_visits), 'tone': 'teal', 'icon': 'eye'},
        {'key': 'registered', 'label': 'Registered users', 'value': len(registered), 'week': recent(p.created_at for p in participants), 'tone': 'blue', 'icon': 'user'},
        {'key': 'completed', 'label': 'Completed walkthroughs', 'value': len(finishers), 'week': recent(r['completed_at'] for r in finishers), 'tone': 'green', 'icon': 'check'},
        {'key': 'pilot', 'label': 'Pilot interest', 'value': len(pilot), 'week': recent(r['date'] for r in pilot), 'tone': 'coral', 'icon': 'flag'},
        {'key': 'waitlist', 'label': 'Waitlist', 'value': len(waitlist), 'week': recent(r['date'] for r in waitlist), 'tone': 'gold', 'icon': 'clock'},
    ]

    # ---- Charts --------------------------------------------------------
    earliest_candidates = [v for v, _ in landing_visits] + [p.created_at for p in participants]
    earliest = _local_day(min(earliest_candidates)) if earliest_candidates else None
    starts, step = _buckets(c['days'], earliest)
    trend = trend_chart(starts, step, [
        {'name': 'Landing visits', 'color': '#147c70', 'unit': 'visits', 'values': _series([_local_day(v) for v, _ in landing_visits], starts, step)},
        {'name': 'Registrations', 'color': '#dc795a', 'unit': 'registrations', 'values': _series([_local_day(p.created_at) for p in participants], starts, step)},
        {'name': 'Completed walkthroughs', 'color': '#2f6f8a', 'unit': 'people completed', 'values': _series([_local_day(r['first_completed']) for r in finishers], starts, step)},
    ])
    status = Counter(r['status'] for r in registered)
    status_donut = donut([{'label': 'Completed', 'n': status.get('Completed', 0), 'color': '#147c70'},
                          {'label': 'In progress', 'n': status.get('In progress', 0), 'color': '#c49a2c'},
                          {'label': 'Not started', 'n': status.get('Not started', 0), 'color': '#d5e3dd'}])
    completion_rate = round(len(finishers) / len(registered) * 100) if registered else 0

    started = sum(1 for r in registered if r['rounds'])
    funnel_raw = [('Visited the landing page', len(landing_visits)), ('Registered', len(registered)), ('Started a case', started),
                  ('Completed the walkthrough', len(finishers)), ('Left feedback', len({f.round.participant_id for f in responses})),
                  ('Asked to pilot or join waitlist', len(pilot) + len(waitlist))]
    fpeak = max([n for _, n in funnel_raw] + [1])
    funnel = [{'label': l, 'n': n, 'w': max(round(n / fpeak * 100), 2 if n else 0)} for l, n in funnel_raw]

    ratings = [f.rating for f in responses]
    rating = {'average': round(sum(ratings) / len(ratings), 1) if ratings else None, 'n': len(ratings),
              'top2': round(sum(1 for r in ratings if r >= 4) / len(ratings) * 100) if ratings else 0,
              'dist': [{'star': s, 'n': ratings.count(s), 'w': round(ratings.count(s) / max(len(ratings), 1) * 100)} for s in (5, 4, 3, 2, 1)]}
    rating['stars_full'] = int(rating['average'] or 0)
    rating['ring'] = donut([{'label': 'rating', 'n': rating['average'] or 0, 'color': '#c49a2c'}, {'label': 'rest', 'n': 5 - (rating['average'] or 0), 'color': '#f1e7cf'}], r=34, stroke=8)
    factors = Counter()
    for f in responses:
        factors.update(set(f.barriers or ([f.barrier] if f.barrier else [])))
    quotes = [{'text': f.suggestion.strip(), 'name': f.round.participant.user.get_full_name() or 'Participant',
               'initials': _initials(f.round.participant.user.get_full_name()), 'org': f.round.participant.organisation, 'rating': f.rating}
              for f in responses if (f.suggestion or '').strip()][:3]

    return {
        'greeting_name': user.first_name or user.username,
        'kpis': kpis, 'trend': trend, 'status_donut': status_donut, 'completion_rate': completion_rate,
        'funnel': funnel, 'rating': rating, 'quotes': quotes,
        'useful': bars(Counter(f.most_useful for f in responses), USEFUL_LABELS, 5),
        'factors': bars(Counter(factors), FACTOR_LABELS, 5),
        'visit_sources': bars(Counter((s or 'direct') for _, s in landing_visits), None, 6),
        'tabs': [
            {'key': 'pilot', 'label': 'Pilot interest', 'rows': pilot, 'kind': 'lead'},
            {'key': 'waitlist', 'label': 'Waitlist', 'rows': waitlist, 'kind': 'lead'},
            {'key': 'registered', 'label': 'Registered users', 'rows': registered, 'kind': 'registered'},
            {'key': 'completed', 'label': 'Completed walkthroughs', 'rows': completed, 'kind': 'completed'},
            {'key': 'other', 'label': 'Other enquiries', 'rows': other, 'kind': 'lead'},
        ],
        'counts': {'registrations': len(registered), 'rounds': len(rounds), 'completed': len(finishers), 'leads': len(leads)},
    }
