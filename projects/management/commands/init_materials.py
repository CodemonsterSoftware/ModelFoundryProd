from django.core.management.base import BaseCommand
from projects.models import Material

class Command(BaseCommand):
    help = 'Initialize generic materials for common 3D printing materials'

    def handle(self, *args, **options):
        # Define generic materials with their properties
        generic_materials = [
            {
                'name': 'Generic PLA',
                'type': 'PLA',
                'description': 'Generic PLA filament',
                'density': '1.24',  # g/mm³
                'cost': '20.00',    # USD per kg
                'weight': '1000',   # grams
                'brand': 'Generic',
            },
            {
                'name': 'Generic ABS',
                'type': 'ABS',
                'description': 'Generic ABS filament',
                'density': '1.04',  # g/mm³
                'cost': '25.00',    # USD per kg
                'weight': '1000',   # grams
                'brand': 'Generic',
            },
            {
                'name': 'Generic PETG',
                'type': 'PETG',
                'description': 'Generic PETG filament',
                'density': '1.27',  # g/mm³
                'cost': '30.00',    # USD per kg
                'weight': '1000',   # grams
                'brand': 'Generic',
            },
            {
                'name': 'Generic Resin',
                'type': 'Resin',
                'description': 'Generic UV resin',
                'density': '1.12',  # g/mm³
                'cost': '25.00',    # USD per kg
                'weight': '1000',   # grams
                'brand': 'Generic',
            },
        ]

        created_count = 0
        for material_data in generic_materials:
            # Check if material already exists
            if not Material.objects.filter(name=material_data['name']).exists():
                Material.objects.create(**material_data)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created {material_data["name"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'{material_data["name"]} already exists'))

        self.stdout.write(self.style.SUCCESS(f'Successfully initialized {created_count} materials')) 