import apps.accounts.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("site_management", "0024_supervisor_timetable_and_checklists")]

    operations = [
        migrations.CreateModel(
            name="CleanerPaymentProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("yas_zantel_phone", models.CharField(blank=True, default="", max_length=16, validators=[apps.accounts.validators.validate_phone])),
                ("pbz_account_number", models.CharField(blank=True, default="", max_length=64)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_payment_profiles", to=settings.AUTH_USER_MODEL)),
                ("cleaner", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="payment_profile", to="site_management.cleaner")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Cleaner payment profile", "verbose_name_plural": "Cleaner payment profiles"},
        ),
        migrations.CreateModel(
            name="MonthlyRemunerationReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period", models.DateField(db_index=True, help_text="First day of the remuneration month.")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted"), ("reviewed", "Reviewed"), ("returned", "Returned")], db_index=True, default="draft", max_length=16)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("return_reason", models.TextField(blank=True, default="")),
                ("snapshot", models.JSONField(blank=True, default=dict)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("prepared_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="prepared_monthly_remuneration_reports", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_monthly_remuneration_reports", to=settings.AUTH_USER_MODEL)),
                ("site", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="monthly_remuneration_reports", to="site_management.site")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Monthly remuneration report", "verbose_name_plural": "Monthly remuneration reports", "ordering": ["-period", "site__name"]},
        ),
        migrations.CreateModel(
            name="MonthlyRemunerationLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("present_days", models.PositiveSmallIntegerField(default=0)),
                ("absent_days", models.PositiveSmallIntegerField(default=0)),
                ("start_work_date", models.DateField(blank=True, null=True)),
                ("proposed_yas_zantel_phone", models.CharField(blank=True, default="", max_length=16, validators=[apps.accounts.validators.validate_phone])),
                ("proposed_pbz_account_number", models.CharField(blank=True, default="", max_length=64)),
                ("phone_change_status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("account_change_status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("assignment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="monthly_remuneration_lines", to="site_management.cleanersiteassignment")),
                ("cleaner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="monthly_remuneration_lines", to="site_management.cleaner")),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="site_management.monthlyremunerationreport")),
            ],
            options={"verbose_name": "Monthly remuneration line", "verbose_name_plural": "Monthly remuneration lines", "ordering": ["cleaner__last_name", "cleaner__first_name"]},
        ),
        migrations.AddIndex(model_name="monthlyremunerationreport", index=models.Index(fields=["site", "period", "status"], name="site_manage_site_id_35cb96_idx")),
        migrations.AddConstraint(model_name="monthlyremunerationreport", constraint=models.UniqueConstraint(fields=("site", "period"), name="uniq_site_monthly_remuneration_report")),
        migrations.AddConstraint(model_name="monthlyremunerationline", constraint=models.UniqueConstraint(fields=("report", "cleaner"), name="uniq_monthly_remuneration_cleaner")),
    ]
