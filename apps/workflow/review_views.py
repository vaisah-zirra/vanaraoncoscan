"""Facility-side Specialist reviews workspace: every teleradiology second read for your cases."""
import statistics
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_GET
from apps.clinical.report_library import BIRADS
from apps.workflow.models import SpecialistReview
from core.permissions import facility_ids_for


def _initials(name):
    parts = [p for p in (name or '').split() if p[:1].isalpha()]
    return ((parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')) if parts else '?').upper()


def birads_tone(category):
    c = (category or '').upper()
    if c in ('1', '2'): return 'benign'
    if c == '3': return 'probably'
    if c == '0': return 'incomplete'
    if c.startswith('4'): return 'suspicious'
    if c in ('5', '6'): return 'malignant'
    return 'none'


@login_required
@require_GET
def specialist_reviews(request):
    from apps.workflow.teleradiology import resolve_simulated_reviews
    scoped = SpecialistReview.objects.filter(case__patient__facility_id__in=facility_ids_for(request.user))
    for review in scoped.filter(signed_at__isnull=True).select_related('case__patient__facility'):
        resolve_simulated_reviews(review.case)  # sign any simulated reads that are due
    scoped = scoped.select_related('case__patient', 'reviewer')
    signed = list(scoped.filter(signed_at__isnull=False))
    with_concordance = [r for r in signed if r.concordance]
    turnaround = [(r.signed_at - r.requested_at).total_seconds() / 60 for r in signed if r.requested_at]
    median = statistics.median(turnaround) if turnaround else None
    if median is None:
        turnaround_label = '—'
    elif median < 60:
        turnaround_label = f'{max(1, round(median))} min'
    elif median < 60 * 48:
        turnaround_label = f'{median / 60:.1f} h'
    else:
        turnaround_label = f'{median / 1440:.1f} days'
    counts = {'awaiting': scoped.filter(signed_at__isnull=True).count(), 'signed': len(signed), 'all': scoped.count()}
    kpis = {
        'awaiting': counts['awaiting'], 'signed': counts['signed'], 'turnaround': turnaround_label,
        'agreement': round(sum(1 for r in with_concordance if r.concordance == 'AGREE') / len(with_concordance) * 100) if with_concordance else None,
        'changed': sum(1 for r in with_concordance if r.concordance != 'AGREE'),
    }
    status = request.GET.get('status', 'awaiting' if counts['awaiting'] else 'signed')
    if status not in counts:
        status = 'awaiting'
    q = request.GET.get('q', '').strip()[:120]
    items = scoped
    if status == 'awaiting':
        items = items.filter(signed_at__isnull=True)
    elif status == 'signed':
        items = items.filter(signed_at__isnull=False)
    if q:
        items = items.filter(Q(case__patient__display_name__icontains=q) | Q(case__patient__reference__icontains=q) | Q(recommendation__icontains=q))
    rows = []
    for r in items.order_by('-requested_at', '-pk')[:200]:
        rows.append({'review': r, 'case': r.case, 'patient': r.case.patient, 'initials': _initials(r.case.patient.display_name),
                     'birads_name': BIRADS.get(r.birads, ('',))[0] if r.birads else '', 'tone': birads_tone(r.birads),
                     'reviewer': (r.reviewer.get_full_name() or r.reviewer.username) if r.reviewer else ''})
    tabs = [('awaiting', 'Awaiting radiologist', counts['awaiting']), ('signed', 'Signed', counts['signed']), ('all', 'All reviews', counts['all'])]
    return render(request, 'specialist_reviews.html', {'rows': rows, 'kpis': kpis, 'tabs': tabs, 'status': status, 'q': q, 'counts': counts})
