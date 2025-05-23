# Generated by Django 5.2 on 2025-04-11 10:21

import django.core.validators
import django.db.models.deletion
import shortuuid.django_fields
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Wallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wallet_number', shortuuid.django_fields.ShortUUIDField(alphabet='1234567890', blank=True, length=7, max_length=25, null=True, prefix='SPDY')),
                ('wallet_type', models.CharField(choices=[('PRIMARY', 'PRIMARY'), ('EVENT', 'EVENT'), ('OPERATIONS', 'OPERATIONS'), ('EMERGENCY', 'EMERGENCY')], default='PRIMARY', max_length=10)),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=15, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('currency', models.CharField(blank=True, choices=[('KES', 'KES'), ('UGX', 'UGX')], max_length=3, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['user', 'currency'], name='wallet_wall_user_id_098bf8_idx')],
            },
        ),
    ]
