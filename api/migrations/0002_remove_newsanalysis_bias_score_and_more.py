# Generated by Django 4.2.16 on 2025-03-17 17:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="newsanalysis",
            name="bias_score",
        ),
        migrations.RemoveField(
            model_name="newsanalysis",
            name="rewritten_text",
        ),
    ]
