from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'

    def ready(self):
        import projects.signals
        try:
            from projects.logging_utils import apply_system_log_level
            apply_system_log_level()
        except Exception:
            pass
