from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("site_management", "0025_monthly_remuneration")]

    operations = [
        migrations.AddField(
            model_name="monthlyremunerationline",
            name="previous_yas_zantel_phone",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="monthlyremunerationline",
            name="previous_pbz_account_number",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="monthlyremunerationline",
            name="payment_saved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="monthlyremunerationline",
            name="payment_saved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="saved_remuneration_payment_decisions", to=settings.AUTH_USER_MODEL),
        ),
    ]
