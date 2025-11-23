from django.core.management.base import BaseCommand
from projects.models import Material

class Command(BaseCommand):
    help = 'Clean up duplicate materials by removing non-generic versions'

    def handle(self, *args, **options):
        # Define the generic materials we want to keep
        generic_materials = [
            'Generic PLA',
            'Generic ABS', 
            'Generic PETG',
            'Generic Resin'
        ]
        
        deleted_count = 0
        
        # For each generic material, find and delete non-generic duplicates
        for generic_name in generic_materials:
            # Extract the material type (PLA, ABS, etc.)
            material_type = generic_name.replace('Generic ', '')
            
            # Find all materials of this type that are NOT generic
            non_generic_materials = Material.objects.filter(
                type=material_type
            ).exclude(
                name__startswith='Generic'
            )
            
            for material in non_generic_materials:
                self.stdout.write(f'Deleting duplicate material: {material.name}')
                material.delete()
                deleted_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully cleaned up {deleted_count} duplicate materials')
        ) 