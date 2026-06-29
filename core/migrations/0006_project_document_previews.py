from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_project_project_document'),
    ]

    operations = [
        migrations.RenameField(
            model_name='project',
            old_name='project_document',
            new_name='original_document',
        ),
        migrations.AlterField(
            model_name='project',
            name='original_document',
            field=models.FileField(blank=True, null=True, upload_to='project_docs/originals/'),
        ),
        migrations.AddField(
            model_name='project',
            name='preview_document',
            field=models.FileField(blank=True, null=True, upload_to='project_docs/previews/'),
        ),
    ]
