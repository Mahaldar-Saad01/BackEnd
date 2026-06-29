# Generated manually for project document uploads

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_meeting_participants_meeting_project_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='project_document',
            field=models.FileField(blank=True, null=True, upload_to='project_docs/'),
        ),
    ]
