# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-10 15:33
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_auto_20170315_1639'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='collective',
            options={'get_latest_by': 'created_at', 'ordering': ['created_at']},
        ),
        migrations.AlterModelOptions(
            name='individual',
            options={'get_latest_by': 'created_at', 'ordering': ['created_at']},
        ),
    ]
