from datetime import datetime, timedelta
from calendar import monthrange
import pytz
from collections import defaultdict
from decimal import Decimal

def get_week_of_month(date):
    """
    Returns the week number of the month for the specified date.
    Week 1 is the first week that contains the 1st day of the month.
    """
    # Get the first day of the month
    first_day = date.replace(day=1)
    
    # Calculate the day of the week (0 is Monday, 6 is Sunday)
    day_of_week = first_day.weekday()
    
    # Calculate the day of the month
    day_of_month = date.day
    
    # Calculate the week number
    week_number = ((day_of_month + day_of_week - 1) // 7) + 1
    
    return week_number

def get_weeks_in_month(year, month):
    """
    Returns the number of weeks in the specified month.
    """
    # Get the number of days in the month
    _, num_days = monthrange(year, month)
    
    # Create a date object for the last day of the month
    last_day = datetime(year, month, num_days)
    
    # Get the week number of the last day
    return get_week_of_month(last_day)

def format_week_label(year, month, week):
    """
    Returns a formatted string for the week label.
    """
    month_name = datetime(year, month, 1).strftime('%B')
    return f"Week {week} ({month_name})"

def get_week_date_range(year, month, week):
    """
    Returns the start and end dates for a given week in a month.
    """
    # Get the first day of the month
    first_day = datetime(year, month, 1)
    
    # Find the first day of the first week
    first_week_start = first_day - timedelta(days=first_day.weekday())
    
    # Calculate the start of the target week
    week_start = first_week_start + timedelta(weeks=week-1)
    
    # Calculate the end of the target week
    week_end = week_start + timedelta(days=6)
    
    # Adjust if the week spans across months
    if week_start.month < month:
        week_start = first_day
    
    # Adjust if the week end is in the next month
    _, last_day = monthrange(year, month)
    month_end = datetime(year, month, last_day)
    if week_end.month > month:
        week_end = month_end
    
    return week_start, week_end

def format_currency(amount):
    """
    Format a decimal amount as currency string.
    """
    if isinstance(amount, Decimal):
        return float(amount)
    return float(amount) if amount else 0.0