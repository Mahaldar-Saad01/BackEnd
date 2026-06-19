# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_user_team_lead'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='report',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='task',
            name='proceed_flag',
            field=models.BooleanField(default=False),
        ),
    ]
