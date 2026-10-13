from core.permissions import reviewer_facility_ids


def teleradiology(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    ids = list(reviewer_facility_ids(user))
    if not ids:
        return {'teleradiology_access': False}
    from apps.workflow.models import SpecialistReview
    from apps.workflow.teleradiology import resolve_simulated_reviews
    waiting = SpecialistReview.objects.filter(case__patient__facility_id__in=ids, signed_at__isnull=True)
    for case in {review.case for review in waiting.select_related('case__patient__facility')[:20]}:
        resolve_simulated_reviews(case)
    pending = waiting.count()
    return {'teleradiology_access': True, 'teleradiology_pending': pending}
