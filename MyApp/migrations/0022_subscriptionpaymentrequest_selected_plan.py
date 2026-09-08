from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("MyApp", "0021_staff_unique_together_remove_workimage"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptionpaymentrequest",
            name="selected_plan",
            field=models.CharField(choices=[("free", "Free"), ("base", "Base"), ("premium", "Premium"), ("enterprise", "Enterprise")], default="free", max_length=30),
        ),
    ]
