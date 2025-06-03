from .models import Notification

def create_alert(user, title, message, notification_type='None'):
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type
    )