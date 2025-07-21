# notifications/sms_service.py
import logging
import africastalking
from typing import List, Dict, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SMSService:
    """
    SMS service class for Africa's Talking integration
    """
    
    def __init__(self):
        self.username = getattr(settings, 'AFRICASTALKING_USERNAME', 'production')
        self.api_key = getattr(settings, 'AFRICASTALKING_API_KEY', '')
        self.environment = getattr(settings, 'AFRICASTALKING_ENVIRONMENT', 'production')
        self.at_sms_shortcode = getattr(settings, 'AFRICASTALKING_SHORTCODE', '57680')
        
        if not self.api_key:
            logger.warning("Africa's Talking API key not configured")
            return
        
        # Initialize Africa's Talking
        try:
            africastalking.initialize(self.username, self.api_key)
            self.sms = africastalking.SMS
            logger.info("Africa's Talking SMS service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Africa's Talking: {str(e)}")
            self.sms = None
    
    def send_notification(self, phone_number: str, message: str, notification_type: str = "info") -> Dict:
        """
        Send SMS notification to a single recipient
        
        Args:
            phone_number: Recipient's phone number
            message: SMS message content
            notification_type: Type of notification for logging
        
        Returns:
            Dict with success status and details
        """
        if not self.sms:
            return {'success': False, 'error': 'SMS service not initialized'}
        
        try:
            # Format phone number
            formatted_number = self._format_phone_number(phone_number)
            
            # Truncate message to SMS limits (160 chars for single SMS)
            truncated_message = self._truncate_message(message)
            
            # Check rate limiting
            if not self._check_rate_limit(formatted_number):
                logger.warning(f"Rate limit exceeded for {formatted_number}")
                return {'success': False, 'error': 'Rate limit exceeded'}
            
            # Send SMS
            response = self.sms.send(
                message=truncated_message,
                recipients=[formatted_number]
            )
            print(response)
            
            # Parse response
            if response['SMSMessageData']['Recipients']:
                recipient_data = response['SMSMessageData']['Recipients'][0]
                
                if recipient_data['status'] == 'Success':
                    # Log successful send
                    self._log_sms_sent(formatted_number, truncated_message, notification_type)
                    
                    # Update rate limiting
                    self._update_rate_limit(formatted_number)
                    
                    logger.info(f"SMS sent successfully to {formatted_number}")
                    
                    return {
                        'success': True,
                        'message_id': recipient_data.get('messageId'),
                        'cost': recipient_data.get('cost'),
                        'status': recipient_data.get('status')
                    }
                else:
                    error_msg = recipient_data.get('status', 'Unknown error')
                    logger.error(f"SMS failed to {formatted_number}: {error_msg}")
                    
                    return {
                        'success': False,
                        'error': error_msg
                    }
            else:
                logger.error("No recipient data in SMS response")
                return {'success': False, 'error': 'No recipient data in response'}
                
        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_bulk_notifications(self, recipients: List[Dict], notification_type: str = "info") -> List[Dict]:
        """
        Send SMS notifications to multiple recipients
        
        Args:
            recipients: List of dicts with 'phone', 'message', 'name' keys
            notification_type: Type of notification for logging
        
        Returns:
            List of results for each recipient
        """
        if not self.sms:
            return [{'recipient': r.get('name', r['phone']), 'result': {'success': False, 'error': 'SMS service not initialized'}} for r in recipients]
        
        results = []
        
        # Process in batches to respect API limits
        batch_size = getattr(settings, 'SMS_BATCH_SIZE', 100)
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            batch_results = self._send_batch(batch, notification_type)
            results.extend(batch_results)
        
        return results
    
    def _send_batch(self, batch: List[Dict], notification_type: str) -> List[Dict]:
        """Send a batch of SMS messages"""
        results = []
        
        for recipient in batch:
            result = self.send_notification(
                phone_number=recipient['phone'],
                message=recipient['message'],
                notification_type=notification_type
            )
            
            results.append({
                'recipient': recipient.get('name', recipient['phone']),
                'phone': recipient['phone'],
                'result': result
            })
        
        return results
    
    def _format_phone_number(self, phone_number: str) -> str:
        """
        Format phone number to international format
        """
        # Remove any spaces, dashes, or parentheses
        clean_number = ''.join(filter(str.isdigit, phone_number))
        
        # Get country code from settings or default to Kenya
        default_country_code = getattr(settings, 'DEFAULT_COUNTRY_CODE', '254')
        
        # Add country code if not present
        if not phone_number.startswith('+'):
            if clean_number.startswith('0'):
                clean_number = default_country_code + clean_number[1:]
            elif not clean_number.startswith(default_country_code):
                clean_number = default_country_code + clean_number
            
            return '+' + clean_number
        
        return phone_number
    
    def _truncate_message(self, message: str, max_length: int = 160) -> str:
        """
        Truncate message to fit SMS character limits
        """
        if len(message) <= max_length:
            return message
        
        # Truncate and add ellipsis
        return message[:max_length - 3] + '...'
    
    def _check_rate_limit(self, phone_number: str) -> bool:
        """
        Check if phone number has exceeded rate limits
        """
        cache_key = f"sms_rate_limit_{phone_number}"
        current_count = cache.get(cache_key, 0)
        
        # Allow max SMS per hour (configurable)
        max_sms_per_hour = getattr(settings, 'SMS_RATE_LIMIT_PER_HOUR', 10)
        
        return current_count < max_sms_per_hour
    
    def _update_rate_limit(self, phone_number: str):
        """
        Update rate limiting counter for phone number
        """
        cache_key = f"sms_rate_limit_{phone_number}"
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, 3600)  # 1 hour expiry
    
    def _log_sms_sent(self, phone_number: str, message: str, notification_type: str):
        """
        Log SMS sending for audit purposes
        """
        try:
            from .models import SMSLog
           # my fields 


            SMSLog.objects.create(
                phone_number=phone_number,
                message=message,
                notification_type=notification_type,
                sent_at=timezone.now(),
                status='sent'
            )
        except Exception as e:
            # Don't fail SMS sending if logging fails
            logger.warning(f"Failed to log SMS: {str(e)}")
    
    def get_delivery_reports(self, message_ids: List[str]) -> Dict:
        """
        Get delivery reports for sent messages
        """
        if not self.sms:
            return {'error': 'SMS service not initialized'}
        
        try:
            # Note: This requires Africa's Talking premium account
            response = self.sms.fetchMessages()
            return response
        except Exception as e:
            logger.error(f"Failed to fetch delivery reports: {str(e)}")
            return {'error': str(e)}
    
    def get_account_balance(self) -> Dict:
        """
        Get account balance from Africa's Talking
        """
        try:
            application = africastalking.Application
            response = application.fetch_application_data()
            return {
                'success': True,
                'balance': response.get('UserData', {}).get('balance', 'Unknown')
            }
        except Exception as e:
            logger.error(f"Failed to fetch account balance: {str(e)}")
            return {'success': False, 'error': str(e)}

