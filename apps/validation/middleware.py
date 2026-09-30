from django.utils.cache import patch_cache_control
from .services import record_visit

class ValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        # No IP addresses, user-agent fingerprints, query strings or clinical content stored.
        tracked = (request.path in ('/', '/accounts/signup/', '/accounts/login/', '/pilot/', '/workspace/', '/walkthrough/') or request.path.startswith('/cases/'))
        if tracked and request.method == 'GET' and not (request.user.is_authenticated and request.user.is_staff):
            record_visit(request)
        response = self.get_response(request)
        if request.user.is_authenticated or request.path.startswith(('/accounts/', '/pilot/', '/validation/')):
            patch_cache_control(response, private=True, no_store=True, max_age=0)
        return response
