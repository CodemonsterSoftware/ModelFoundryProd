import os
from .models import UnclaimedSlice

def demo_banner(request):
    """
    Exposes the DEMO_BANNER_TEXT environment variable to templates.
    Used for showing a banner with test credentials on demo sites.
    """
    return {
        'DEMO_BANNER_TEXT': os.environ.get('DEMO_BANNER_TEXT', '')
    }

from django.db.models import Q
import json

def slicer_inbox_count(request):
    if request.user.is_authenticated:
        enable_slicer_inbox = True
        global_users = []
        
        # Check settings
        try:
            # We can't import UserSettings at the top level due to circular imports sometimes,
            # but we can import it here
            from .models import UserSettings
            
            for us in UserSettings.objects.filter(settings_type='api'):
                settings_data = json.loads(us.settings_data) if us.settings_data else {}
                if settings_data.get('is_global'):
                    global_users.append(us.user)
                    
            # Check if this specific user disabled it
            user_api_settings = UserSettings.objects.filter(user=request.user, settings_type='api').first()
            if user_api_settings:
                settings_data = json.loads(user_api_settings.settings_data) if user_api_settings.settings_data else {}
                enable_slicer_inbox = settings_data.get('enable_slicer_inbox', True)
        except Exception:
            pass
            
        if not enable_slicer_inbox:
            return {'unclaimed_slices_count': 0, 'enable_slicer_inbox': False}
            
        count = UnclaimedSlice.objects.filter(
            Q(user=request.user) | Q(user__in=global_users),
            status='pending'
        ).distinct().count()
        
        return {
            'unclaimed_slices_count': count,
            'enable_slicer_inbox': True
        }
    return {'unclaimed_slices_count': 0, 'enable_slicer_inbox': False}
