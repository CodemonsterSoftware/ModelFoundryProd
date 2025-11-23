# Generated manually to change Instructions.image to Instructions.file (FileField)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0019_project_source_delete_slicedfile'),
    ]

    operations = [
        # Add new file field (nullable initially)
        migrations.AddField(
            model_name='instructions',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='instructions/', help_text='Instruction file (image, PDF, or DOCX)'),
        ),
        # Copy data from image to file
        migrations.RunPython(
            code=lambda apps, schema_editor: migrate_image_to_file(apps, schema_editor),
            reverse_code=lambda apps, schema_editor: migrate_file_to_image(apps, schema_editor),
        ),
        # Remove old image field
        migrations.RemoveField(
            model_name='instructions',
            name='image',
        ),
        # Make file field non-nullable
        migrations.AlterField(
            model_name='instructions',
            name='file',
            field=models.FileField(upload_to='instructions/', help_text='Instruction file (image, PDF, or DOCX)'),
        ),
    ]


def migrate_image_to_file(apps, schema_editor):
    """Copy data from image field to file field"""
    Instructions = apps.get_model('projects', 'Instructions')
    for instruction in Instructions.objects.all():
        if instruction.image:
            instruction.file = instruction.image
            instruction.save()


def migrate_file_to_image(apps, schema_editor):
    """Reverse migration: copy data from file field to image field"""
    Instructions = apps.get_model('projects', 'Instructions')
    for instruction in Instructions.objects.all():
        if instruction.file:
            instruction.image = instruction.file
            instruction.save()

