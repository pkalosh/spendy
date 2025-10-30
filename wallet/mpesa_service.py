import requests
import base64
import json
from requests.exceptions import RequestException
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from django.conf import settings
from django.utils import timezone
from .models import MpesaTransaction
import logging

logger = logging.getLogger(__name__)

class MpesaDaraja:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.base_url = settings.MPESA_BASE_URL  # sandbox or production
        self.initiator_name = settings.MPESA_INITIATOR_NAME
        self.initiator_password = settings.MPESA_INITIATOR_PASSWORD
        self.shortcode = settings.MPESA_SHORTCODE  # Single shortcode for all transactions
        self.passkey = settings.MPESA_PASSKEY  # Passkey for STK push
        self.certificate_path = settings.MPESA_CERTIFICATE_PATH
        self.access_token = None
        self.security_credential = None
    
    def get_access_token(self):
        """Generate access token for API authentication"""
        try:
            # Encode consumer key and secret
            credentials = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data['access_token']
                logger.info("Access token generated successfully")
                return self.access_token
            else:
                logger.error(f"Failed to generate access token: {response.text}")
                raise Exception(f"Failed to generate access token: {response.text}")
                
        except Exception as e:
            logger.error(f"Error generating access token: {str(e)}")
            raise
    
    def generate_security_credential(self):
        """Generate security credential by encrypting initiator password"""
        try:
            with open(self.certificate_path, 'rb') as cert_file:
                cert_data = cert_file.read()
            
            # Load the certificate - CORRECTED IMPORT
            certificate = x509.load_pem_x509_certificate(cert_data)
            public_key = certificate.public_key()
            
            # Encrypt the password
            encrypted = public_key.encrypt(
                self.initiator_password.encode(),
                asym_padding.PKCS1v15()  # Also corrected the padding import
            )
            
            self.security_credential = base64.b64encode(encrypted).decode()
            return self.security_credential
            
        except Exception as e:
            logger.error(f"Error generating security credential: {str(e)}")
            raise
    
    def generate_password(self, timestamp=None):
        """Generate password for STK push"""
        if not timestamp:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        password_string = f"{self.shortcode}{self.passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()
        return password, timestamp
    
    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """
        Initiate STK Push (Lipa Na M-Pesa Online)
        
        Args:
            phone_number (str): Customer phone number (254XXXXXXXXX)
            amount (int): Amount to request
            account_reference (str): Account reference
            transaction_desc (str): Transaction description
        
        Returns:
            dict: API response
        """
        try:
            if not self.access_token:
                self.get_access_token()
            
            password, timestamp = self.generate_password()
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": phone_number,
                "PartyB": self.shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": f"{settings.BASE_URL}/stk/callback/",
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers=headers
            )
            
            response_data = response.json()
            
            # Save transaction to database
            if response.status_code == 200 and response_data.get('ResponseCode') == '0':
                MpesaTransaction.objects.create(
                    merchant_request_id=response_data.get('MerchantRequestID'),
                    checkout_request_id=response_data.get('CheckoutRequestID'),
                    transaction_type='STK_PUSH',
                    amount=amount,
                    party_a=phone_number,
                    party_b=self.shortcode,
                    phone_number=phone_number,
                    account_reference=account_reference,
                    transaction_desc=transaction_desc,
                    status='PENDING'
                )
                logger.info(f"STK Push initiated successfully: {response_data}")
                print(f"STK Push initiated successfully: {response_data}")
            else:
                logger.error(f"STK Push failed: {response_data}")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error initiating STK Push: {str(e)}")
            raise
    
    def stk_query(self, checkout_request_id):
        """
        Query STK Push status
        
        Args:
            checkout_request_id (str): Checkout request ID from STK push
        
        Returns:
            dict: API response
        """
        try:
            if not self.access_token:
                self.get_access_token()
            
            password, timestamp = self.generate_password()
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers=headers
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error querying STK Push status: {str(e)}")
            raise
    
    def c2b_register_urls(self, validation_url=None, confirmation_url=None, response_type="Completed"):
        """
        Register C2B URLs for payment notifications
        """
        try:
            if not self.access_token:
                self.get_access_token()

            payload = {
                "ShortCode": self.shortcode,
                "ResponseType": response_type,
                "ConfirmationURL": confirmation_url or f"{settings.BASE_URL}/c2b/confirmation/",
                "ValidationURL": validation_url or f"{settings.BASE_URL}/c2b/validation/"
            }
            print(payload)
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # --- ADDED DEBUGGING LINES ---
            print(f"Payload for C2B registration: {json.dumps(payload, indent=2)}")
            print(f"Authorization Header being used: {headers.get('Authorization')}") 
            # You can print the whole token, but be cautious with logging sensitive data
            # --- END DEBUGGING ---

            response = requests.post(
                f"{self.base_url}/mpesa/c2b/v2/registerurl",
                json=payload,
                headers=headers
            )
            
            response_data = response.json()
            logger.info(f"C2B URLs registered: {response_data}")
            return response_data
                
        except Exception as e:
            logger.error(f"Error registering C2B URLs: {str(e)}", exc_info=True)
            raise
    def b2c_payment(self, amount, phone_number, remarks, command_id='BusinessPayment', occasion=''):
        """
        Initiate B2C payment
        
        Args:
            amount (float): Amount to send
            phone_number (str): Customer phone number (254XXXXXXXXX)
            remarks (str): Transaction remarks
            command_id (str): BusinessPayment, SalaryPayment, or PromotionPayment
            occasion (str): Optional occasion
        
        Returns:
            dict: API response
        """
        try:
            # Get access token if not available
            if not self.access_token:
                self.get_access_token()
            
            # Generate security credential if not available
            if not self.security_credential:
                self.generate_security_credential()
            
            # Prepare request payload
            payload = {
                "InitiatorName": self.initiator_name,
                "SecurityCredential": self.security_credential,
                "CommandID": command_id,
                "Amount": amount,
                "PartyA": self.shortcode,
                "PartyB": phone_number,
                "Remarks": remarks,
                "QueueTimeOutURL": f"{settings.BASE_URL}/b2c/timeout/",
                "ResultURL": f"{settings.BASE_URL}/b2c/result/",
                "Occasion": occasion
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/b2c/v1/paymentrequest",
                json=payload,
                headers=headers
            )
            
            response_data = response.json()
            print(f"res {response_data}")
            
            # Save transaction to database
            if response.status_code == 200 and response_data.get('ResponseCode') == '0':
                MpesaTransaction.objects.create(
                    conversation_id=response_data.get('ConversationID'),
                    originator_conversation_id=response_data.get('OriginatorConversationID'),
                    transaction_type='B2C',
                    amount=amount,
                    party_a=self.shortcode,
                    party_b=phone_number,
                    phone_number=phone_number,
                    remarks=remarks,
                    status='PENDING'
                )
                logger.info(f"B2C payment initiated successfully: {response_data}")
            else:
                logger.error(f"B2C payment failed: {response_data}")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error initiating B2C payment: {str(e)}")
            raise
    
    def b2b_payment(self, amount, receiver_shortcode, remarks, account_reference=None,
                    command_id='BusinessPayBill', callback_url=None, timeout_url=None):
        """
        Initiate B2B payment
        
        Args:
            amount (float): Amount to send
            receiver_shortcode (str): Receiver organization shortcode
            account_reference (str): Account reference
            remarks (str): Transaction remarks
            command_id (str): BusinessPayBill, BusinessBuyGoods, etc.
        
        Returns:
            dict: API response
        """
        try:
            # Get access token if not available
            if not self.access_token:
                self.get_access_token()
            
            # Generate security credential if not available
            if not self.security_credential:
                self.generate_security_credential()
            
            # Prepare request payload
            queue_timeout_url = timeout_url or f"{settings.BASE_URL}/b2b/timeout/"
            result_url = callback_url or f"{settings.BASE_URL}/b2b/result/"
            
            # DYNAMIC: Set identifier types based on command_id
            sender_identifier_type = 4  # Always organization for sender
            if command_id == 'BusinessPayBill':
                receiver_identifier_type = 4  # PayBill receiver
            elif command_id == 'BusinessBuyGoods':
                receiver_identifier_type = 2  # Till receiver
            else:
                raise ValueError(f"Unsupported command_id: {command_id}. Must be 'BusinessPayBill' or 'BusinessBuyGoods'.")
            
            # Log types for debugging
            logger.info(f"B2B payload types: Sender={sender_identifier_type}, Receiver={receiver_identifier_type} for command={command_id}")
            
            # Prepare request payload
            payload = {
                "Initiator": self.initiator_name,
                "SecurityCredential": self.security_credential,
                "CommandID": command_id,
                "SenderIdentifierType": sender_identifier_type,
                "ReceiverIdentifierType": receiver_identifier_type,  # FIXED: Dynamic + correct spelling
                "Amount": amount,
                "PartyA": self.shortcode,
                "PartyB": receiver_shortcode,
                "AccountReference": account_reference or "",  # String; empty OK for BuyGoods but use transaction_ref
                "Remarks": remarks,
                "QueueTimeOutURL": queue_timeout_url,
                "ResultURL": result_url
            }
                
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/b2b/v1/paymentrequest",
                json=payload,
                headers=headers
            )
            
            response_data = response.json()
            
            # Save transaction to database
            if response.status_code == 200 and response_data.get('ResponseCode') == '0':
                MpesaTransaction.objects.create(
                    conversation_id=response_data.get('ConversationID'),
                    originator_conversation_id=response_data.get('OriginatorConversationID'),
                    transaction_type='B2B',
                    amount=amount,
                    party_a=self.shortcode,
                    party_b=receiver_shortcode,
                    account_reference=account_reference,
                    remarks=remarks,
                    status='PENDING'
                )
                logger.info(f"B2B payment initiated successfully: {response_data}")
            else:
                logger.error(f"B2B payment failed: {response_data}")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error initiating B2B payment: {str(e)}")
            raise
    
    def transaction_status(self, transaction_id, party_a):
        """Query transaction status"""
        try:
            if not self.access_token:
                self.get_access_token()
            
            if not self.security_credential:
                self.generate_security_credential()
            
            payload = {
                "Initiator": self.initiator_name,
                "SecurityCredential": self.security_credential,
                "CommandID": "TransactionStatusQuery",
                "TransactionID": transaction_id,
                "PartyA": party_a,
                "IdentifierType": 4,
                "ResultURL": f"{settings.BASE_URL}/status/result/",
                "QueueTimeOutURL": f"{settings.BASE_URL}/status/timeout/",
                "Remarks": "Transaction status query",
                "Occasion": ""
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/transactionstatus/v1/query",
                json=payload,
                headers=headers
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error querying transaction status: {str(e)}")
            raise
    
    def account_balance(self, party_a):
        """Query account balance"""
        try:
            if not self.access_token:
                self.get_access_token()
            
            if not self.security_credential:
                self.generate_security_credential()
            
            payload = {
                "Initiator": self.initiator_name,
                "SecurityCredential": self.security_credential,
                "CommandID": "AccountBalance",
                "PartyA": party_a,
                "IdentifierType": 4,
                "Remarks": "Account balance query",
                "QueueTimeOutURL": f"{settings.BASE_URL}/balance/timeout/",
                "ResultURL": f"{settings.BASE_URL}/balance/result/"
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/accountbalance/v1/query",
                json=payload,
                headers=headers
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error querying account balance: {str(e)}")
            raise

    def reversal(self, transaction_id, amount, receiver_party, remarks):
        """
        Reverse a transaction
        
        Args:
            transaction_id (str): Original transaction ID to reverse
            amount (float): Amount to reverse
            receiver_party (str): Party that will receive the reversed amount
            remarks (str): Reversal remarks
        
        Returns:
            dict: API response
        """
        try:
            if not self.access_token:
                self.get_access_token()
            
            if not self.security_credential:
                self.generate_security_credential()
            
            payload = {
                "Initiator": self.initiator_name,
                "SecurityCredential": self.security_credential,
                "CommandID": "TransactionReversal",
                "TransactionID": transaction_id,
                "Amount": amount,
                "ReceiverParty": receiver_party,
                "RecieverIdentifierType": 11,
                "ResultURL": f"{settings.BASE_URL}/reversal/result/",
                "QueueTimeOutURL": f"{settings.BASE_URL}/reversal/timeout/",
                "Remarks": remarks,
                "Occasion": ""
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/reversal/v1/request",
                json=payload,
                headers=headers
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error processing reversal: {str(e)}")
            raise