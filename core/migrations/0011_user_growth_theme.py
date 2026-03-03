# Generated migration - adds growth_theme to core.User

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_exam_to_course_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='growth_theme',
            field=models.CharField(
                choices=[('bodybuilder', 'Bodybuilder'), ('tree', 'Ancient Tree'), ('city', 'City Builder')],
                default='bodybuilder',
                max_length=20,
            ),
        ),
    ]
