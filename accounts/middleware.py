import logging
from time import perf_counter
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

logger = logging.getLogger('portal.audit')


class RequestAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = perf_counter()
        if request.path.startswith('/dashboard/'):
            if not request.user.is_authenticated:
                response = redirect_to_login(request.get_full_path())
            elif not request.user.verified:
                response = HttpResponseForbidden('Verify your email before accessing the portal.')
            else:
                response = self.get_response(request)
        else:
            response = self.get_response(request)
        logger.info('method=%s path=%s duration_ms=%.2f role=%s', request.method, request.path,
                    (perf_counter() - start) * 1000, getattr(request.user, 'role', 'anonymous'))
        return response
