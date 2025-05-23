# Generated by Django 5.0.2 on 2025-04-14 01:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0010_remove_material_cost_per_kg'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='type',
            field=models.CharField(choices=[('PLA', 'PLA'), ('ABS', 'ABS'), ('PETG', 'PETG'), ('TPU', 'TPU'), ('Nylon', 'Nylon'), ('PC', 'Polycarbonate'), ('ASA', 'ASA'), ('HIPS', 'HIPS'), ('PVA', 'PVA'), ('Resin', 'Resin'), ('Other', 'Other')], default='PLA', max_length=20),
        ),
    ]
