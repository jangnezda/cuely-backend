# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2017-01-26 11:09
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dataimporter', '0035_only_metadata'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='document',
            name='intercom_title',
        ),
        migrations.RemoveField(
            model_name='document',
            name='intercom_user_id',
        ),
    ]
