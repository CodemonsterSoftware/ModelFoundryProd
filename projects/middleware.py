from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings

class FirstSetupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Try to resolve the URL for first_setup to avoid errors during startup
        try:
            setup_url = reverse('first_setup')
        except Exception:
            setup_url = '/setup/'

        # Allow static, media, and setup urls to pass through
        if request.path.startswith(settings.STATIC_URL) or \
           request.path.startswith(settings.MEDIA_URL) or \
           request.path == setup_url:
            return self.get_response(request)

        # If no users exist, redirect to setup
        # Wrap in try/except to prevent issues during database creation/migrations
        try:
            if not User.objects.exists():
                return redirect('first_setup')
        except Exception:
            pass

        return self.get_response(request)
