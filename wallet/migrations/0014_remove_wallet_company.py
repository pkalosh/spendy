# Generated by Django 5.2 on 2025-04-28 14:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0013_wallet_company'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='wallet',
            name='company',
        ),
    ]
