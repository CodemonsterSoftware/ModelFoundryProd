# Generated by Django 5.0.2 on 2025-05-11 00:15

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0015_usersettings'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersettings',
            name='settings_type',
            field=models.CharField(choices=[('general', 'General Settings'), ('slicer', 'Slicer Settings'), ('appearance', 'Appearance Settings'), ('machines', 'Machine Settings')], max_length=50),
        ),
        migrations.AlterField(
            model_name='usersettings',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='Machine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('maker', models.CharField(blank=True, max_length=100, null=True)),
                ('model', models.CharField(blank=True, max_length=100, null=True)),
                ('technology', models.CharField(choices=[('FDM', 'Fused Deposition Modeling'), ('SLA', 'Stereolithography'), ('SLS', 'Selective Laser Sintering'), ('DLP', 'Digital Light Processing'), ('MJF', 'Multi Jet Fusion'), ('Other', 'Other')], default='FDM', max_length=10)),
                ('print_volume_x', models.PositiveIntegerField(help_text='Print volume X in mm')),
                ('print_volume_y', models.PositiveIntegerField(help_text='Print volume Y in mm')),
                ('print_volume_z', models.PositiveIntegerField(help_text='Print volume Z in mm')),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='machines', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
    ]
