from django.core.management.base import BaseCommand
from projects.models import Part
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generates thumbnails for Parts that have an STL file but no thumbnail.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force regeneration for parts that already have thumbnails')

    def handle(self, *args, **options):
        parts = Part.objects.filter(stl_file__isnull=False).exclude(stl_file='')
        
        if not options.get('force'):
            parts = parts.filter(thumbnail='')
        
        if not parts.exists():
            self.stdout.write(self.style.SUCCESS('No parts found needing thumbnails.'))
            return
            
        self.stdout.write(f'Found {parts.count()} parts needing thumbnails.')
        
        for part in parts:
            self.stdout.write(f'Processing part {part.id}: {part.name}')
            if options.get('force') and part.thumbnail:
                part.thumbnail.delete(save=False)
            # Simply saving the part will trigger the post_save signal
            part.save()
            
        self.stdout.write(self.style.SUCCESS('Finished processing thumbnails.'))
