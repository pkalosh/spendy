from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Custom filter to get a dict value by variable key.
    Usage: {{ mydict|get_item:mykey }}
    """
    return dictionary.get(key)