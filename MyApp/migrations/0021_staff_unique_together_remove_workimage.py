from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MyApp', '0020_company_registration_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staff',
            name='staff_id',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterUniqueTogether(
            name='staff',
            unique_together={('company', 'staff_id')},
        ),
        migrations.DeleteModel(
            name='WorkImage',
        ),
    ]
