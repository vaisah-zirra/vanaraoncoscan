from django.core.exceptions import PermissionDenied
from apps.organizations.models import Membership

def facility_ids_for(user):
    if not user.is_authenticated:
        return Membership.objects.none().values_list('facility_id', flat=True)
    return Membership.objects.filter(user=user, is_active=True, role=Membership.Role.FACILITY).values_list('facility_id', flat=True)

def require_facility_access(user, facility_id):
    if facility_id not in facility_ids_for(user):
        raise PermissionDenied('You cannot access this facility.')


def reviewer_facility_ids(user):
    """Facilities whose teleradiology queue this user may read and sign.

    Specialist reviewers always qualify. In demo/pilot workspaces the facility user may also
    act as the teleradiologist, so a single tester can experience both sides of the review.
    """
    if not user.is_authenticated:
        return Membership.objects.none().values_list('facility_id', flat=True)
    from django.db.models import Q
    return Membership.objects.filter(Q(role=Membership.Role.REVIEWER) | Q(role=Membership.Role.FACILITY, facility__is_demo=True),
                                     user=user, is_active=True).values_list('facility_id', flat=True)


def require_reviewer_access(user, facility_id):
    if facility_id not in reviewer_facility_ids(user):
        raise PermissionDenied('You cannot review cases for this facility.')
