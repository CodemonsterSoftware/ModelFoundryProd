import logging
import json
from django.conf import settings

def apply_system_log_level(level_name=None):
    """
    Applies the specified log level to the main application loggers.
    If no level_name is provided, it tries to fetch it from the UserSettings model.
    """
    valid_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    if not level_name:
        try:
            # We import here to avoid AppRegistryNotReady errors
            from projects.models import UserSettings
            
            # Since this is a global setting, we can just get the first one
            # or try to find a user that has system settings configured
            system_setting = UserSettings.objects.filter(settings_type='system').first()
            if system_setting and system_setting.settings_data:
                data = json.loads(system_setting.settings_data)
                level_name = data.get('log_level', 'INFO')
        except Exception:
            pass
            
    if not level_name:
        level_name = 'INFO'
        
    level = valid_levels.get(level_name.upper(), logging.INFO)
    
    # Apply to our main loggers
    for logger_name in ['django', 'projects', 'mqtt_listener', 'forge']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)
            
    # Also update the root logger's handlers just in case they are shared
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setLevel(level)
        
    return level_name
