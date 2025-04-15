from django import template
from django.utils.html import format_html
from django.template.defaultfilters import stringfilter
from django.db.models import Sum

register = template.Library()

@register.filter
def get_material_count(project, material):
    """Returns the count of parts with the specified material in the project."""
    return project.parts.filter(material=material).count()

@register.filter
def get_item(dictionary, key):
    """Returns the value for the given key in the dictionary."""
    return dictionary.get(key)

@register.filter
def get_completed_parts(project):
    """Returns the count of completed parts in the project."""
    return project.parts.filter(completed=True).count()

@register.filter
def get_pending_parts(project):
    """Returns the count of pending parts in the project."""
    return project.parts.filter(completed=False).count()

@register.filter
def get_purchased_parts_status(project, status):
    """Returns the count of purchased parts with the specified status."""
    return project.purchased_parts.filter(status=status).count()

@register.filter
def get_group_parts(project, group):
    """Returns the parts belonging to a specific group in the project."""
    return project.parts.filter(group=group)

@register.filter
def get_project_images(project):
    """Returns all images associated with the project."""
    return project.images.all()

@register.filter
def get_part_thumbnail(part):
    """Returns the thumbnail URL for a part if it exists, otherwise returns a default icon."""
    if part.thumbnail:
        return part.thumbnail.url
    return '/static/projects/images/part-placeholder.png'

@register.filter
def sum_completed(parts):
    """Returns the sum of completed parts."""
    return parts.aggregate(total=Sum('completed'))['total'] or 0

@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def color_name(color_code):
    """Convert color code to a readable name."""
    if not color_code:
        return "No Color"
    
    # Remove # if present
    color_code = color_code.lstrip('#')
    
    # Common color names
    color_map = {
        '000000': 'Black',
        'FFFFFF': 'White',
        'FF0000': 'Red',
        '00FF00': 'Green',
        '0000FF': 'Blue',
        'FFFF00': 'Yellow',
        'FF00FF': 'Magenta',
        '00FFFF': 'Cyan',
        'FFA500': 'Orange',
        '800080': 'Purple',
        '808080': 'Gray',
        'A52A2A': 'Brown',
        'FFC0CB': 'Pink',
    }
    
    return color_map.get(color_code.upper(), color_code)

@register.filter
def color_tag(color_code):
    """Create a color tag with swatch and name."""
    if not color_code:
        return "No Color"
    
    name = color_name(color_code)
    return format_html(
        '<span class="badge" style="background-color: {}; color: {}; border: 1px solid #ddd;">'
        '<div class="color-swatch" style="display: inline-block; width: 12px; height: 12px; margin-right: 4px; vertical-align: middle; background-color: {};"></div>'
        '{}'
        '</span>',
        color_code,
        '#000' if color_code.upper().lstrip('#') in ['FFFFFF', 'FFFF00', 'FFA500', 'FFC0CB'] else '#fff',
        color_code,
        name
    )

@register.filter
def divide(value, arg):
    """Divide the value by the argument"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return None 