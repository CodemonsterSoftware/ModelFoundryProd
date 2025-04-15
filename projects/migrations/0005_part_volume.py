# Generated by Django 5.0.2 on 2025-04-13 22:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0004_designer_project_user_alter_project_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='part',
            name='volume',
            field=models.FloatField(blank=True, help_text='Volume in cubic millimeters', null=True),
        ),
    ]
