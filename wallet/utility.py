import logging
from typing import List, Dict, Optional
from django.conf import settings
from django.core.cache import cache
from userauths.models import User
from .models import Notification
from .sms_service import SMSService

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Enhanced utility service for creating notifications with SMS support
    """
    
    def __init__(self):
        self.sms_service = SMSService()
    
    @staticmethod
    def create_notification(user, notification_type, title, message, send_sms=False, sms_message=None):
        """
        Enhanced base method to create a notification with optional SMS
        
        Args:
            user: User instance or user ID
            notification_type: String matching NOTIFICATION_TYPE choices
            title: Notification title
            message: Notification message
            send_sms: Boolean to trigger SMS notification
            sms_message: Custom SMS message (if different from notification message)
        
        Returns:
            Dict with notification instance and SMS result
        """
        if isinstance(user, int):
            try:
                user = User.objects.get(id=user)
            except User.DoesNotExist:
                return {'notification': None, 'sms': None}
        
        if user is None:
            return {'notification': None, 'sms': None}
        
        # Create in-app notification
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message
        )
        
        result = {'notification': notification, 'sms': None}
        
        # Send SMS if requested and user has phone number
        if send_sms and hasattr(user, 'phone_number') and user.phone_number:
            sms_text = sms_message or f"{title}: {message}"
            sms_result = NotificationService._send_sms_notification(
                user, sms_text, notification_type
            )
            result['sms'] = sms_result
        
        return result
    
    @staticmethod
    def _send_sms_notification(user, message, notification_type):
        """
        Internal method to send SMS notification
        """
        try:
            sms_service = SMSService()
            
            # Rate limiting check
            cache_key = f"sms_rate_limit_{user.id}"
            recent_sms_count = cache.get(cache_key, 0)
            
            # Allow max 5 SMS per hour per user
            if recent_sms_count >= 5:
                logger.warning(f"SMS rate limit exceeded for user {user.id}")
                return {'success': False, 'error': 'Rate limit exceeded'}
            
            # Send SMS
            result = sms_service.send_notification(
                phone_number=user.phone_number,
                message=message,
                notification_type=notification_type
            )
            
            # Update rate limiting counter
            cache.set(cache_key, recent_sms_count + 1, 3600)  # 1 hour expiry
            
            return result
            
        except Exception as e:
            logger.error(f"SMS sending failed for user {user.id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Enhanced expense-related notifications with SMS
    @staticmethod
    def expense_created(user, expense_amount, expense_description="", send_sms=False):
        """Notify when a new expense is created"""
        title = "New Expense Created"
        message = f"You have created a new expense of ${expense_amount:.2f}"
        if expense_description:
            message += f" for {expense_description}"
        
        # SMS version (shorter)
        sms_message = f"Expense created: ${expense_amount:.2f}"
        if expense_description:
            sms_message += f" - {expense_description[:30]}..."
        
        return NotificationService.create_notification(
            user, "Sent Expense request", title, message, 
            send_sms=send_sms, sms_message=sms_message
        )
    
    @staticmethod
    def expense_approved(user, expense_amount, approver_name="", send_sms=True):
        """Notify when expense is approved - SMS enabled by default"""
        title = "Expense Approved"
        message = f"Your expense of ${expense_amount:.2f} has been approved"
        if approver_name:
            message += f" by {approver_name}"
        
        sms_message = f"✅ Expense approved: ${expense_amount:.2f}"
        if approver_name:
            sms_message += f" by {approver_name}"
        
        return NotificationService.create_notification(
            user, "Approved Expense request", title, message,
            send_sms=send_sms, sms_message=sms_message
        )
    
    @staticmethod
    def expense_declined(user, expense_amount, reason="", declined_by="", send_sms=True):
        """Notify when expense is declined - SMS enabled by default"""
        title = "Expense Declined"
        message = f"Your expense of ${expense_amount:.2f} has been declined"
        if declined_by:
            message += f" by {declined_by}"
        if reason:
            message += f". Reason: {reason}"
        
        sms_message = f"❌ Expense declined: ${expense_amount:.2f}"
        if reason:
            sms_message += f" - {reason[:40]}..."
        
        return NotificationService.create_notification(
            user, "danger", title, message,
            send_sms=send_sms, sms_message=sms_message
        )
    
    @staticmethod
    def expense_paid(user, expense_amount, payment_method="", send_sms=True):
        """Notify when expense is paid - SMS enabled by default"""
        title = "Expense Paid"
        message = f"Your expense of ${expense_amount:.2f} has been paid"
        if payment_method:
            message += f" via {payment_method}"
        
        sms_message = f"💰 Payment received: ${expense_amount:.2f}"
        if payment_method:
            sms_message += f" via {payment_method}"
        
        return NotificationService.create_notification(
            user, "success", title, message,
            send_sms=send_sms, sms_message=sms_message
        )
    
    # Enhanced payment request notifications
    @staticmethod
    def payment_request_sent(sender, recipient, amount, description="", send_sms=True):
        """Notify when payment request is sent"""
        # Notify sender
        sender_title = "Payment Request Sent"
        sender_message = f"You sent a payment request of ${amount:.2f} to {recipient.get_full_name() or recipient.username}"
        if description:
            sender_message += f" for {description}"
        
        NotificationService.create_notification(
            sender, "Sent Payment Request", sender_title, sender_message, 
            send_sms=False  # Don't SMS the sender
        )
        
        # Notify recipient with SMS
        recipient_title = "Payment Request Received"
        recipient_message = f"You received a payment request of ${amount:.2f} from {sender.get_full_name() or sender.username}"
        if description:
            recipient_message += f" for {description}"
        
        sms_message = f"💸 Payment request: ${amount:.2f} from {sender.get_full_name() or sender.username}"
        if description:
            sms_message += f" - {description[:30]}..."
        
        return NotificationService.create_notification(
            recipient, "Received Payment Request", recipient_title, recipient_message,
            send_sms=send_sms, sms_message=sms_message
        )
    
    @staticmethod
    def payment_request_approved(requester, payer, amount, send_sms=True):
        """Notify when payment request is approved"""
        title = "Payment Request Approved"
        message = f"Your payment request of ${amount:.2f} has been approved by {payer.get_full_name() or payer.username}"
        
        sms_message = f"✅ Payment approved: ${amount:.2f} by {payer.get_full_name() or payer.username}"
        
        return NotificationService.create_notification(
            requester, "success", title, message,
            send_sms=send_sms, sms_message=sms_message
        )
    
    # Enhanced transfer notifications
    @staticmethod
    def transfer_sent(sender, recipient, amount, reference="", send_sms=True):
        """Notify when transfer is sent"""
        # Notify sender
        sender_title = "Transfer Sent"
        sender_message = f"You sent ${amount:.2f} to {recipient.get_full_name() or recipient.username}"
        if reference:
            sender_message += f" (Ref: {reference})"
        
        NotificationService.create_notification(
            sender, "Transfer", sender_title, sender_message, send_sms=False
        )
        
        # Notify recipient with SMS
        recipient_title = "Transfer Received"
        recipient_message = f"You received ${amount:.2f} from {sender.get_full_name() or sender.username}"
        if reference:
            recipient_message += f" (Ref: {reference})"
        
        sms_message = f"💰 Received: ${amount:.2f} from {sender.get_full_name() or sender.username}"
        if reference:
            sms_message += f" Ref: {reference}"
        
        return NotificationService.create_notification(
            recipient, "Transfer", recipient_title, recipient_message,
            send_sms=send_sms, sms_message=sms_message
        )
    
    # Critical security notifications (always send SMS)
    @staticmethod
    def security_alert(user, alert_message, action_required=False, send_sms=True):
        """Notify about security issues - SMS always enabled for security"""
        title = "Security Alert"
        message = alert_message
        if action_required:
            message += " Please take immediate action."
        
        sms_message = f"🚨 SECURITY ALERT: {alert_message[:100]}..."
        if action_required:
            sms_message += " Action required."
        
        return NotificationService.create_notification(
            user, "danger", title, message,
            send_sms=send_sms, sms_message=sms_message
        )
    
    # Low balance alerts (critical - always SMS)
    @staticmethod
    def wallet_balance_low(user, wallet_name, current_balance, threshold, send_sms=True):
        """Notify when wallet balance is low - SMS enabled by default"""
        title = "Low Wallet Balance"
        message = f"Your wallet '{wallet_name}' balance is low (${current_balance:.2f}). Consider adding funds."
        
        sms_message = f"⚠️ Low balance: {wallet_name} - ${current_balance:.2f}. Add funds soon."
        
        return NotificationService.create_notification(
            user, "warning", title, message,
            send_sms=send_sms, sms_message=sms_message
        )
    
    # Bulk SMS notifications
    @staticmethod
    def send_bulk_sms_notifications(users, message, notification_type="info"):
        """
        Send SMS to multiple users (for announcements, alerts, etc.)
        
        Args:
            users: List of User instances or QuerySet
            message: SMS message content
            notification_type: Type of notification
        
        Returns:
            Dict with success and failure counts
        """
        sms_service = SMSService()
        
        # Prepare recipients
        recipients = []
        for user in users:
            if hasattr(user, 'phone_number') and user.phone_number:
                recipients.append({
                    'phone': user.phone_number,
                    'message': message,
                    'name': user.get_full_name() or user.username
                })
        
        # Send bulk SMS
        results = sms_service.send_bulk_notifications(recipients, notification_type)
        
        # Count successes and failures
        success_count = sum(1 for r in results if r['result']['success'])
        failure_count = len(results) - success_count
        
        logger.info(f"Bulk SMS sent: {success_count} success, {failure_count} failed")
        
        return {
            'total_sent': len(recipients),
            'success_count': success_count,
            'failure_count': failure_count,
            'results': results
        }
    
    # System-wide announcements
    @staticmethod
    def system_announcement(message, send_sms=False, user_filter=None):
        """
        Send system-wide announcement to all users or filtered users
        
        Args:
            message: Announcement message
            send_sms: Whether to send SMS as well
            user_filter: Optional queryset filter for users
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        users = User.objects.all()
        if user_filter:
            users = users.filter(**user_filter)
        
        # Create in-app notifications
        notifications = NotificationService.notify_multiple_users(
            users, "info", "System Announcement", message
        )
        
        result = {'notifications_created': len(notifications)}
        
        # Send SMS if requested
        if send_sms:
            sms_result = NotificationService.send_bulk_sms_notifications(
                users, f"📢 {message}", "info"
            )
            result['sms_result'] = sms_result
        
        return result
    
    # User preference management
    @staticmethod
    def get_user_sms_preference(user, notification_type="default"):
        """
        Check if user wants SMS for specific notification type
        Assumes you have a UserPreference model or similar
        """
        try:
            # This assumes you have a user preference model
            # You can adapt this to your preference system
            from .models import UserNotificationPreference
            
            preference = UserNotificationPreference.objects.get(
                user=user, notification_type=notification_type
            )
            return preference.sms_enabled
        except:
            # Default behavior if no preference model
            return True
    
    # All existing methods remain the same, but with enhanced versions above
    # ... (keep all your existing methods like wallet_created, staff_added, etc.)
    
    @staticmethod
    def notify_multiple_users(users, notification_type, title, message, send_sms=False):
        """
        Enhanced bulk notification with SMS support
        """
        notifications = []
        sms_results = []
        
        for user in users:
            result = NotificationService.create_notification(
                user, notification_type, title, message, send_sms=send_sms
            )
            if result['notification']:
                notifications.append(result['notification'])
            if result['sms']:
                sms_results.append(result['sms'])
        
        return {
            'notifications': notifications,
            'sms_results': sms_results
        }


# Enhanced helper functions with SMS support
def notify_expense_workflow(expense, action, send_sms=None, **kwargs):
    """
    Enhanced expense notification workflow with SMS support
    
    Args:
        expense: Expense model instance
        action: 'created', 'approved', 'declined', 'paid'
        send_sms: Override SMS sending (None uses default behavior)
        **kwargs: Additional context
    """
    # Determine SMS default based on action criticality
    sms_defaults = {
        'created': False,    # Not critical
        'approved': True,    # Important
        'declined': True,    # Important
        'paid': True        # Critical
    }
    
    should_send_sms = send_sms if send_sms is not None else sms_defaults.get(action, False)
    
    if action == 'created':
        return NotificationService.expense_created(
            expense.created_by, 
            expense.amount, 
            expense.description,
            send_sms=should_send_sms
        )
    elif action == 'approved':
        return NotificationService.expense_approved(
            expense.created_by, 
            expense.amount, 
            kwargs.get('approver_name', ''),
            send_sms=should_send_sms
        )
    elif action == 'declined':
        return NotificationService.expense_declined(
            expense.created_by, 
            expense.amount, 
            kwargs.get('reason', ''),
            kwargs.get('declined_by', ''),
            send_sms=should_send_sms
        )
    elif action == 'paid':
        return NotificationService.expense_paid(
            expense.created_by, 
            expense.amount, 
            kwargs.get('payment_method', ''),
            send_sms=should_send_sms
        )


# Usage examples:
"""
# Basic usage with SMS
NotificationService.expense_approved(
    user=expense.user, 
    expense_amount=500.00, 
    approver_name="John Doe",
    send_sms=True
)

# Bulk SMS announcement
NotificationService.system_announcement(
    message="System maintenance scheduled for tonight at 10 PM",
    send_sms=True,
    user_filter={'is_active': True}
)

# Security alert (always sends SMS)
NotificationService.security_alert(
    user=user,
    alert_message="Suspicious login attempt detected",
    action_required=True
)
"""