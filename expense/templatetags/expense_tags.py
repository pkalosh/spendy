from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Retrieves a value from a dictionary by key.
    Returns None if key not found.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

# Your existing mul filter (if added previously)
@register.filter
def mul(value, arg):
    from decimal import Decimal
    try:
        return Decimal(value) * Decimal(arg)
    except (ValueError, TypeError, AttributeError):
        return 0