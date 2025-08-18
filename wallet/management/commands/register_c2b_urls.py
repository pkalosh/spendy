from django.core.management.base import BaseCommand
from wallet.mpesa_service import MpesaDaraja
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Registers M-Pesa C2B Validation and Confirmation URLs, ensuring a fresh access token is obtained.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Attempting to register M-Pesa C2B URLs..."))
        try:
            # Instantiate MpesaDaraja.
            # Its constructor will load settings and subsequent calls will handle token refresh.
            mpesa = MpesaDaraja()

            # The get_access_token() is called internally by c2b_register_urls
            # if self.access_token is not set.
            # However, for explicit debugging, you could force a token refresh here:
            self.stdout.write(self.style.NOTICE("Attempting to get a fresh access token..."))
            fresh_token = mpesa.get_access_token()
            print(f"Fresh access token obtained: {fresh_token}")  # Debugging output
            if not fresh_token:
                self.stdout.write(self.style.ERROR("Failed to obtain a fresh access token before registration."))
                return # Exit if token acquisition fails

            self.stdout.write(self.style.NOTICE("Calling c2b_register_urls with current settings..."))
            response = mpesa.c2b_register_urls()
            
            if response.get('ResponseDescription') == 'success' or response.get('ResponseCode') == '0':
                self.stdout.write(self.style.SUCCESS("M-Pesa C2B URLs registered successfully!"))
                logger.info("M-Pesa C2B URLs registered successfully.")
            else:
                self.stdout.write(self.style.ERROR(
                    f"Failed to register M-Pesa C2B URLs. API Response: {response}"
                ))
                logger.error(f"Failed to register M-Pesa C2B URLs: {response}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {str(e)}"))
            logger.error(f"An unexpected error occurred during URL registration: {str(e)}", exc_info=True)

