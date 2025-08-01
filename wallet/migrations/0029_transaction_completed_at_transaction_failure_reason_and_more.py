# Generated by Django 5.2 on 2025-07-21 05:08

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0028_transaction_merchant_request_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='completed_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp when transaction was completed', null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='failure_reason',
            field=models.TextField(blank=True, help_text='Reason for transaction failure, if applicable', null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='paid_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp when payment was made', null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='parent_transaction',
            field=models.ForeignKey(blank=True, help_text='For nested transactions like refunds or splits', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='child_transactions', to='wallet.transaction'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='payment_completed',
            field=models.BooleanField(default=False, help_text='Whether the payment for this transaction has been completed'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='payment_wallet',
            field=models.ForeignKey(blank=True, help_text='Wallet used for payment in this transaction', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_transactions', to='wallet.wallet'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='transfer_fee',
            field=models.DecimalField(blank=True, decimal_places=2, default=0.0, max_digits=12, null=True),
        ),
    ]
