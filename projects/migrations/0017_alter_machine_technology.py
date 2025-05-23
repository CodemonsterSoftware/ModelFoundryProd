# Generated by Django 5.0.2 on 2025-05-11 00:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0016_alter_usersettings_settings_type_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='machine',
            name='technology',
            field=models.CharField(choices=[('FDM', 'FDM (Fused Deposition Modeling)'), ('SLA', 'SLA (Stereolithography)'), ('SLS', 'SLS (Selective Laser Sintering)'), ('DLP', 'DLP (Digital Light Processing)'), ('MJF', 'MJF (Multi Jet Fusion)'), ('Other', 'Other Technology')], default='FDM', max_length=10),
        ),
    ]
