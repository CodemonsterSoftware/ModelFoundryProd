import os
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Part
from forge.services.blender_client import BlenderClient
from django.core.files import File
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Part)
def generate_part_thumbnail(sender, instance, created, **kwargs):
    """
    Signal receiver to generate a thumbnail when a Part is saved with an STL but no thumbnail.
    """
    if instance.stl_file and not instance.thumbnail:
        # Check if we are already generating to prevent infinite loop if save() is called inside
        if getattr(instance, '_is_generating_thumbnail', False):
            return
            
        instance._is_generating_thumbnail = True
        
        try:
            client = BlenderClient()
            if client.is_available():
                # Define output path
                # Since the file doesn't exist yet, we define a relative path inside media/thumbnails
                # Ensure the name is unique
                ext = '.png'
                base_name = os.path.splitext(os.path.basename(instance.stl_file.name))[0]
                filename = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
                output_rel_path = f"thumbnails/{filename}"
                
                # Get the relative path of the input file from MEDIA_ROOT
                # instance.stl_file.name is already relative to MEDIA_ROOT
                input_rel_path = instance.stl_file.name
                
                success = client.generate_thumbnail(input_rel_path, output_rel_path)
                
                if success:
                    # Update the thumbnail field
                    # We can just set the name, Django storage will handle it
                    # because the file was written directly to the media directory by Blender
                    instance.thumbnail.name = output_rel_path
                    instance.save(update_fields=['thumbnail'])
                    logger.info(f"Successfully attached generated thumbnail for Part {instance.id}")
            else:
                logger.warning("Blender service unavailable, skipping thumbnail generation")
        except Exception as e:
            logger.error(f"Error in thumbnail generation signal: {e}")
        finally:
            instance._is_generating_thumbnail = False
