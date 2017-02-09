# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2017-02-08 15:56
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataimporter', '0039_github_commit'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='github_file_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='document',
            name='github_file_title',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
