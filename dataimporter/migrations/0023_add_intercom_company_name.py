# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-11-03 14:56
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataimporter', '0022_remove_conversation_open'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='intercom_company',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]