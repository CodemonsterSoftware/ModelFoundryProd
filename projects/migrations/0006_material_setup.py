from django.db import migrations, models
import django.db.models.deletion

def create_default_materials(apps, schema_editor):
    Material = apps.get_model('projects', 'Material')
    Part = apps.get_model('projects', 'Part')
    
    # Create default materials
    default_materials = [
        {'name': 'PLA', 'density': 1.24, 'cost_per_kg': 20.00, 'color': 'Natural'},
        {'name': 'ABS', 'density': 1.04, 'cost_per_kg': 25.00, 'color': 'Natural'},
        {'name': 'PETG', 'density': 1.27, 'cost_per_kg': 22.00, 'color': 'Natural'},
        {'name': 'TPU', 'density': 1.21, 'cost_per_kg': 35.00, 'color': 'Natural'},
    ]
    
    materials = {}
    for material_data in default_materials:
        material, _ = Material.objects.get_or_create(**material_data)
        materials[material.name] = material
    
    # Update existing parts
    for part in Part.objects.all():
        if part.material_name and part.material_name in materials:
            part.material_fk = materials[part.material_name]
            part.save()

def reverse_materials(apps, schema_editor):
    Part = apps.get_model('projects', 'Part')
    Material = apps.get_model('projects', 'Material')
    
    for part in Part.objects.all():
        if part.material_fk:
            part.material_name = part.material_fk.name
            part.material_fk = None
            part.save()
    
    Material.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0005_part_volume'),
    ]

    operations = [
        # Create Material model
        migrations.CreateModel(
            name='Material',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('density', models.FloatField(help_text='Density in g/cm³')),
                ('cost_per_kg', models.DecimalField(decimal_places=2, help_text='Cost per kilogram', max_digits=10)),
                ('color', models.CharField(blank=True, help_text='Default color for this material', max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        # Rename existing material field to material_name
        migrations.RenameField(
            model_name='part',
            old_name='material',
            new_name='material_name',
        ),
        # Add new material foreign key field
        migrations.AddField(
            model_name='part',
            name='material_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='parts', to='projects.material'),
        ),
        # Run the data migration
        migrations.RunPython(create_default_materials, reverse_materials),
        # Remove the old material_name field
        migrations.RemoveField(
            model_name='part',
            name='material_name',
        ),
        # Rename material_fk to material
        migrations.RenameField(
            model_name='part',
            old_name='material_fk',
            new_name='material',
        ),
    ] 