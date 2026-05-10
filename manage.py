#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modelfoundry.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
        
    # Monkey patch Django's StatReloader to handle FileNotFoundError 
    # which can occur when .venv files or __pycache__ are deleted during scanning.
    # This prevents the Django development server from crashing.
    try:
        import django.utils.autoreload
        original_snapshot = getattr(django.utils.autoreload.StatReloader, 'snapshot_files', None)
        if original_snapshot:
            def safe_snapshot_files(self):
                try:
                    yield from original_snapshot(self)
                except FileNotFoundError:
                    # Ignore the error, the next tick will rescan correctly.
                    pass
            django.utils.autoreload.StatReloader.snapshot_files = safe_snapshot_files
    except Exception:
        pass
        
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
