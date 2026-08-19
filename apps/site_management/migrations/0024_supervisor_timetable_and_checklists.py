import apps.site_management.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("site_management", "0023_stockrequestitem_unit")]

    operations = [
        migrations.CreateModel(
            name="SupervisorTimetableEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("effective_from", models.DateField(db_index=True)),
                ("effective_to", models.DateField(blank=True, db_index=True, null=True)),
                ("work_days", models.JSONField(default=list, validators=[apps.site_management.validators.validate_effective_days])),
                ("off_days", models.JSONField(blank=True, default=list)),
                ("shift_slot", models.CharField(choices=[("asubuhi", "ASUBUHI"), ("mchana", "MCHANA")], max_length=16)),
                ("notes", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("relief_person", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supervisor_roster_relief_entries", to=settings.AUTH_USER_MODEL)),
                ("site", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supervisor_timetable_entries", to="site_management.site")),
                ("supervisor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supervisor_timetable_entries", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("zone", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supervisor_timetable_entries", to="site_management.zone")),
            ],
            options={"verbose_name": "Supervisor timetable entry", "verbose_name_plural": "Supervisor timetable entries", "ordering": ["supervisor__email", "effective_from", "site__name", "shift_slot"]},
        ),
        migrations.CreateModel(
            name="SupervisorChecklistSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("supervisor_role", models.CharField(db_index=True, max_length=64)),
                ("work_date", models.DateField(db_index=True)),
                ("shift_slot", models.CharField(choices=[("asubuhi", "ASUBUHI"), ("mchana", "MCHANA")], max_length=16)),
                ("checklist_kind", models.CharField(choices=[("site_zilizotembelewa", "SITE ZILIZO TEMBELEWA"), ("maeneo_yaliyokaguliwa", "MAENEO YALIYOKAGULIWA"), ("kazi_zilizofanyika", "KAZI ZILIZOFANYIKA"), ("taarifa_za_vitendeakazi", "TAARIFA ZA VITENDEA KAZI")], max_length=40)),
                ("table_entries", models.JSONField(default=list)),
                ("notes", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted"), ("reviewed", "Reviewed"), ("returned", "Returned")], db_index=True, default="draft", max_length=16)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("return_reason", models.TextField(blank=True, default="")),
                ("snapshot", models.JSONField(blank=True, default=dict)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_supervisor_checklists", to=settings.AUTH_USER_MODEL)),
                ("site", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supervisor_checklist_submissions", to="site_management.site")),
                ("supervisor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supervisor_checklist_submissions", to=settings.AUTH_USER_MODEL)),
                ("timetable_entry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checklist_submissions", to="site_management.supervisortimetableentry")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("zone", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supervisor_checklist_submissions", to="site_management.zone")),
            ],
            options={"verbose_name": "Supervisor checklist submission", "verbose_name_plural": "Supervisor checklist submissions", "ordering": ["-work_date", "site__name", "checklist_kind"]},
        ),
        migrations.AddConstraint(model_name="supervisorchecklistsubmission", constraint=models.UniqueConstraint(fields=("timetable_entry", "work_date", "checklist_kind"), name="uniq_supervisor_checklist_schedule_day_kind")),
        migrations.AddIndex(model_name="supervisortimetableentry", index=models.Index(fields=["supervisor", "is_active", "effective_from"], name="site_manage_supervi_1875fa_idx")),
        migrations.AddIndex(model_name="supervisortimetableentry", index=models.Index(fields=["site", "is_active", "effective_from"], name="site_manage_site_id_b4e1e3_idx")),
        migrations.AddIndex(model_name="supervisorchecklistsubmission", index=models.Index(fields=["supervisor", "work_date", "status"], name="site_manage_supervi_948c39_idx")),
        migrations.AddIndex(model_name="supervisorchecklistsubmission", index=models.Index(fields=["site", "work_date", "status"], name="site_manage_site_id_500451_idx")),
    ]
