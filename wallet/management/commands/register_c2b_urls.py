from django.core.management.base import BaseCommand
from wallet.mpesa_service import MpesaDaraja
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Registers M-Pesa C2B Validation and Confirmation URLs'

    def handle(self, *args, **options):
        try:
            mpesa = MpesaDaraja()
            response = mpesa.c2b_register_urls()
            
            if response.get('ResponseDescription') == 'success':
                self.stdout.write(self.style.SUCCESS("M-Pesa C2B URLs registered successfully."))
                logger.info("M-Pesa C2B URLs registered successfully.")
            else:
                self.stdout.write(self.style.ERROR(f"Failed to register M-Pesa C2B URLs: {response}"))
                logger.error(f"Failed to register M-Pesa C2B URLs: {response}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
            logger.error(f"An error occurred during URL registration: {str(e)}", exc_info=True)