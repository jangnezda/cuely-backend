# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-10-17 13:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataimporter', '0015_socialattributes'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='path',
            field=models.CharField(blank=True, max_length=2000, null=True),
        ),
    ]
