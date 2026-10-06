from django.core.cache import caches
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LocalThrottleMixin:
    @property
    def cache(self):
        # A broker outage must not stop API requests before batch failure is recorded.
        return caches['throttle']


class LocalAnonThrottle(LocalThrottleMixin, AnonRateThrottle):
    pass


class LocalUserThrottle(LocalThrottleMixin, UserRateThrottle):
    pass
