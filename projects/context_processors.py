import os

def demo_banner(request):
    """
    Exposes the DEMO_BANNER_TEXT environment variable to templates.
    Used for showing a banner with test credentials on demo sites.
    """
    return {
        'DEMO_BANNER_TEXT': os.environ.get('DEMO_BANNER_TEXT', '')
    }
