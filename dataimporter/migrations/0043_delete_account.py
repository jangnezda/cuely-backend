# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2017-02-15 10:27
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataimporter', '0042_github_issue'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeletedUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('user_id', models.IntegerField()),
                ('email', models.CharField(blank=True, max_length=200, null=True)),
            ],
        ),
    ]
