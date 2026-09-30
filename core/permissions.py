from django.core.exceptions import PermissionDenied
from apps.organizations.models import Membership

def facility_ids_for(user):
    if not user.is_authenticated:
        return Membership.objects.none().values_list('facility_id', flat=True)
    return Membership.objects.filter(user=user, is_active=True, role=Membership.Role.FACILITY).values_list('facility_id', flat=True)

def require_facility_access(user, facility_id):
    if facility_id not in facility_ids_for(user):
        raise PermissionDenied('You cannot access this facility.')
