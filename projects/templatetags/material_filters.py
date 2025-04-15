from django import template
from decimal import Decimal
from django.utils.html import format_html

register = template.Library()

@register.filter
def div(value, arg):
    """Divide the value by the argument"""
    try:
        return Decimal(str(value)) / Decimal(str(arg))
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Multiply the value by the argument"""
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except ValueError:
        return 0

@register.filter
def color_tag(value):
    """Display a color swatch with the color name"""
    if not value:
        return ""
    return format_html(
        '<span class="badge" style="background-color: {}; color: white;">{}</span>',
        value,
        value
    ) 