from django.db.models import Sum
from django import template

register = template.Library()

@register.filter
def get_class_name(obj):
    return obj.__class__.__name__

@register.filter
def filter_by_status(queryset, status):
    """
    Filter expenses by status (pending, approved, declined)
    """
    if status == 'pending':
        return queryset.filter(approved=False, declined=False)
    elif status == 'approved':
        return queryset.filter(approved=True)
    elif status == 'declined':
        return queryset.filter(declined=True)
    return queryset

@register.filter
def calculate_total(queryset, field_name):
    """
    Calculate the total sum of a specific field in a queryset
    """
    if not queryset:
        return 0
    
    total = 0
    for item in queryset:
        value = getattr(item, field_name, 0)
        if value:
            total += value
    return total

@register.filter
def group_by(queryset, field_name):
    """
    Group expenses by a specific field and calculate totals
    """
    if not queryset:
        return []
    
    # Create a dictionary to store grouped items
    groups = {}
    
    # Group items by the specified field
    for item in queryset:
        key = getattr(item, field_name, 'Other')
        if key not in groups:
            groups[key] = {
                'name': key,
                'items': [],
                'total': 0,
            }
        
        groups[key]['items'].append(item)
        groups[key]['total'] += getattr(item, 'amount', 0)
    
    # Convert dictionary to list and sort by total amount
    result = list(groups.values())
    result.sort(key=lambda x: x['total'], reverse=True)
    
    return result