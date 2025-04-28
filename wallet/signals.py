from django.db.models.signals import post_save
from django.dispatch import receiver
from userauths.models import User
from wallet.models import CompanyKYC, Wallet

@receiver(post_save, sender=User)
def post_user_create(sender, instance, created, **kwargs):
    if created:
        if not (instance.is_staff or instance.is_org_staff):
            # Create CompanyKYC instance
            kyc = CompanyKYC.objects.create(
                user=instance,
                company_name=f"{instance.first_name} {instance.last_name} Company"
            )

            # Determine default currency
            currency = 'KES' if getattr(instance, 'country', '').upper() == 'KENYA' else None

            # Create Wallet instance
            Wallet.objects.create(
                user=instance,
                company=kyc,
                wallet_type='PRIMARY',
                currency=currency
            )
