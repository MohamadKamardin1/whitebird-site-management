from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("site_management", "0031_multi_tier_store_workflow")]

    operations = [
        migrations.AddField(
            model_name="cleanerpaymentprofile",
            name="payment_account_holder_name",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="monthlyremunerationline",
            name="previous_payment_account_holder_name",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="monthlyremunerationline",
            name="proposed_payment_account_holder_name",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
    ]
