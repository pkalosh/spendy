from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Access dict by variable key: {{ mydict|get_item:item.id }}"""
    return dictionary.get(key)