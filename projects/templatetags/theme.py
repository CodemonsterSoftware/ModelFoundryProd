from django import template
from django.utils.safestring import mark_safe
import json
from projects.models import UserSettings

register = template.Library()

@register.simple_tag(takes_context=True)
def get_theme(context):
    """
    Get the theme class to apply to the HTML element.
    This tag checks for theme preference in the following order:
    1. Cookie
    2. User settings (if user is authenticated)
    3. Default to 'dark'
    """
    request = context.get('request')
    if not request:
        return 'dark-theme'  # Default theme
    
    # First check cookie
    theme = request.COOKIES.get('theme_preference')
    
    # If no cookie and user is authenticated, check user settings
    if not theme and request.user.is_authenticated:
        try:
            appearance_settings = UserSettings.objects.get(
                user=request.user, 
                settings_type='appearance'
            )
            if appearance_settings.settings_data:
                appearance_data = json.loads(appearance_settings.settings_data)
                theme = appearance_data.get('theme_preference')
        except (UserSettings.DoesNotExist, json.JSONDecodeError):
            pass
    
    # If still no theme, default to dark
    if not theme:
        theme = 'dark'
    
    # Return the appropriate theme class
    if theme == 'dark':
        return ''  # No class needed for dark theme (default)
    else:
        return f'{theme}-theme' 