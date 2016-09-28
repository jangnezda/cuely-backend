# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-09-28 13:34
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataimporter', '0006_auto_20160927_0957'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='document',
            name='document_type',
        ),
        migrations.AlterField(
            model_name='document',
            name='download_status',
            field=models.IntegerField(choices=[(1, 'Pending'), (2, 'Processing'), (3, 'Ready')], default=1),
        ),
    ]
