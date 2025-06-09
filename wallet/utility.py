# notifications/utils.py
from userauths.models import User
from .models import Notification


class NotificationService:
    """
    Utility service for creating notifications across the application
    """
    
    @staticmethod
    def create_notification(user, notification_type, title, message):
        """
        Base method to create a notification
        
        Args:
            user: User instance or user ID
            notification_type: String matching NOTIFICATION_TYPE choices
            title: Notification title
            message: Notification message
        
        Returns:
            Notification instance
        """
        if isinstance(user, int):
            try:
                user = User.objects.get(id=user)
            except User.DoesNotExist:
                return None
        
        if user is None:
            return None
            
        return Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message
        )
    
    # Expense-related notifications
    @staticmethod
    def expense_created(user, expense_amount, expense_description=""):
        """Notify when a new expense is created"""
        title = "New Expense Created"
        message = f"You have created a new expense of ${expense_amount:.2f}"
        if expense_description:
            message += f" for {expense_description}"
        
        return NotificationService.create_notification(
            user, "Sent Expense request", title, message
        )
    
    @staticmethod
    def expense_approved(user, expense_amount, approver_name=""):
        """Notify when expense is approved"""
        title = "Expense Approved"
        message = f"Your expense of ${expense_amount:.2f} has been approved"
        if approver_name:
            message += f" by {approver_name}"
        
        return NotificationService.create_notification(
            user, "Approved Expense request", title, message
        )
    
    @staticmethod
    def expense_declined(user, expense_amount, reason="", declined_by=""):
        """Notify when expense is declined"""
        title = "Expense Declined"
        message = f"Your expense of ${expense_amount:.2f} has been declined"
        if declined_by:
            message += f" by {declined_by}"
        if reason:
            message += f". Reason: {reason}"
        
        return NotificationService.create_notification(
            user, "danger", title, message
        )
    
    @staticmethod
    def expense_paid(user, expense_amount, payment_method=""):
        """Notify when expense is paid"""
        title = "Expense Paid"
        message = f"Your expense of ${expense_amount:.2f} has been paid"
        if payment_method:
            message += f" via {payment_method}"
        
        return NotificationService.create_notification(
            user, "success", title, message
        )
    
    # Payment request notifications
    @staticmethod
    def payment_request_sent(sender, recipient, amount, description=""):
        """Notify when payment request is sent"""
        # Notify sender
        sender_title = "Payment Request Sent"
        sender_message = f"You sent a payment request of ${amount:.2f} to {recipient.get_full_name() or recipient.username}"
        if description:
            sender_message += f" for {description}"
        
        NotificationService.create_notification(
            sender, "Sent Payment Request", sender_title, sender_message
        )
        
        # Notify recipient
        recipient_title = "Payment Request Received"
        recipient_message = f"You received a payment request of ${amount:.2f} from {sender.get_full_name() or sender.username}"
        if description:
            recipient_message += f" for {description}"
        
        return NotificationService.create_notification(
            recipient, "Received Payment Request", recipient_title, recipient_message
        )
    
    @staticmethod
    def payment_request_approved(requester, payer, amount):
        """Notify when payment request is approved"""
        title = "Payment Request Approved"
        message = f"Your payment request of ${amount:.2f} has been approved by {payer.get_full_name() or payer.username}"
        
        return NotificationService.create_notification(
            requester, "success", title, message
        )
    
    @staticmethod
    def payment_request_declined(requester, payer, amount, reason=""):
        """Notify when payment request is declined"""
        title = "Payment Request Declined"
        message = f"Your payment request of ${amount:.2f} has been declined by {payer.get_full_name() or payer.username}"
        if reason:
            message += f". Reason: {reason}"
        
        return NotificationService.create_notification(
            requester, "danger", title, message
        )
    
    # Transfer notifications
    @staticmethod
    def transfer_sent(sender, recipient, amount, reference=""):
        """Notify when transfer is sent"""
        # Notify sender
        sender_title = "Transfer Sent"
        sender_message = f"You sent ${amount:.2f} to {recipient.get_full_name() or recipient.username}"
        if reference:
            sender_message += f" (Ref: {reference})"
        
        NotificationService.create_notification(
            sender, "Transfer", sender_title, sender_message
        )
        
        # Notify recipient
        recipient_title = "Transfer Received"
        recipient_message = f"You received ${amount:.2f} from {sender.get_full_name() or sender.username}"
        if reference:
            recipient_message += f" (Ref: {reference})"
        
        return NotificationService.create_notification(
            recipient, "Transfer", recipient_title, recipient_message
        )
    
    # Wallet notifications
    @staticmethod
    def wallet_created(user, wallet_name, wallet_type=""):
        """Notify when new wallet is created"""
        title = "New Wallet Created"
        message = f"Your new wallet '{wallet_name}' has been successfully created"
        if wallet_type:
            message += f" ({wallet_type})"
        
        return NotificationService.create_notification(
            user, "success", title, message
        )
    
    @staticmethod
    def wallet_deleted(user, wallet_name):
        """Notify when wallet is deleted"""
        title = "Wallet Deleted"
        message = f"Your wallet '{wallet_name}' has been deleted"
        
        return NotificationService.create_notification(
            user, "warning", title, message
        )
    
    @staticmethod
    def wallet_balance_low(user, wallet_name, current_balance, threshold):
        """Notify when wallet balance is low"""
        title = "Low Wallet Balance"
        message = f"Your wallet '{wallet_name}' balance is low (${current_balance:.2f}). Consider adding funds."
        
        return NotificationService.create_notification(
            user, "warning", title, message
        )
    
    # Staff notifications
    @staticmethod
    def new_staff_added(user, staff_name, role=""):
        """Notify when new staff is added"""
        title = "New Staff Member Added"
        message = f"New staff member {staff_name} has been added to your organization"
        if role:
            message += f" as {role}"
        
        return NotificationService.create_notification(
            user, "info", title, message
        )
    
    @staticmethod
    def staff_removed(user, staff_name, reason=""):
        """Notify when staff is removed"""
        title = "Staff Member Removed"
        message = f"Staff member {staff_name} has been removed from your organization"
        if reason:
            message += f". Reason: {reason}"
        
        return NotificationService.create_notification(
            user, "warning", title, message
        )
    
    @staticmethod
    def staff_role_changed(user, staff_name, old_role, new_role):
        """Notify when staff role is changed"""
        title = "Staff Role Updated"
        message = f"{staff_name}'s role has been changed from {old_role} to {new_role}"
        
        return NotificationService.create_notification(
            user, "info", title, message
        )
    
    # System notifications
    @staticmethod
    def system_maintenance(user, maintenance_date, duration=""):
        """Notify about system maintenance"""
        title = "Scheduled Maintenance"
        message = f"System maintenance is scheduled for {maintenance_date}"
        if duration:
            message += f" and will last approximately {duration}"
        
        return NotificationService.create_notification(
            user, "warning", title, message
        )
    
    @staticmethod
    def security_alert(user, alert_message, action_required=False):
        """Notify about security issues"""
        title = "Security Alert"
        message = alert_message
        if action_required:
            message += " Please take immediate action."
        
        return NotificationService.create_notification(
            user, "danger", title, message
        )
    
    # Bulk notifications
    @staticmethod
    def notify_multiple_users(users, notification_type, title, message):
        """
        Send notification to multiple users
        
        Args:
            users: List of User instances or QuerySet
            notification_type: String matching NOTIFICATION_TYPE choices
            title: Notification title
            message: Notification message
        
        Returns:
            List of created Notification instances
        """
        notifications = []
        for user in users:
            notification = NotificationService.create_notification(
                user, notification_type, title, message
            )
            if notification:
                notifications.append(notification)
        return notifications
    
    @staticmethod
    def mark_as_read(notification_id, user=None):
        """
        Mark notification as read
        
        Args:
            notification_id: ID of the notification
            user: Optional user to verify ownership
        
        Returns:
            Boolean indicating success
        """
        try:
            notification = Notification.objects.get(id=notification_id)
            if user and notification.user != user:
                return False
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
    
    @staticmethod
    def mark_all_as_read(user):
        """Mark all notifications as read for a user"""
        return Notification.objects.filter(user=user, is_read=False).update(is_read=True)
    
    @staticmethod
    def delete_old_notifications(days=30):
        """Delete notifications older than specified days"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        return Notification.objects.filter(date__lt=cutoff_date).delete()


# Example usage functions that you can call from your views/signals

def notify_expense_workflow(expense, action, **kwargs):
    """
    Helper function to handle expense notification workflow
    
    Args:
        expense: Expense model instance
        action: 'created', 'approved', 'declined', 'paid'
        **kwargs: Additional context (approver, reason, etc.)
    """
    if action == 'created':
        NotificationService.expense_created(
            expense.created_by, 
            expense.amount, 
            expense.description
        )
    elif action == 'approved':
        NotificationService.expense_approved(
            expense.approved_by, 
            expense.amount, 
            kwargs.get('approver_name', '')
        )
    elif action == 'declined':
        NotificationService.expense_declined(
            expense.approved_by, 
            expense.amount, 
            kwargs.get('reason', ''),
            kwargs.get('declined_by', '')
        )
    elif action == 'paid':
        NotificationService.expense_paid(
            expense.created_by, 
            expense.amount, 
            kwargs.get('payment_method', '')
        )

def notify_wallet_action(user, wallet, action, **kwargs):
    """
    Helper function to handle wallet notification workflow
    
    Args:
        user: User instance
        wallet: Wallet model instance
        action: 'created', 'deleted', 'low_balance'
        **kwargs: Additional context
    """
    if action == 'created':
        NotificationService.wallet_created(
            user, 
            wallet.name, 
            kwargs.get('wallet_type', '')
        )
    elif action == 'deleted':
        NotificationService.wallet_deleted(user, wallet.name)
    elif action == 'low_balance':
        NotificationService.wallet_balance_low(
            user, 
            wallet.name, 
            wallet.balance, 
            kwargs.get('threshold', 0)
        )