from django.db import migrations


def reconcile_active_trainee_program_sites(apps, schema_editor):
    """Align legacy active trainee programmes with their current site assignment."""
    from django.db.models import Q
    from django.utils import timezone

    CleanerSiteAssignment = apps.get_model("site_management", "CleanerSiteAssignment")
    TraineeProgram = apps.get_model("site_management", "TraineeProgram")
    today = timezone.localdate()
    programmes = TraineeProgram.objects.filter(status__in=["in_training", "extended"])
    for programme in programmes.iterator():
        assignment = (
            CleanerSiteAssignment.objects.filter(
                cleaner_id=programme.cleaner_id,
                status__in=["draft", "active"],
                start_date__lte=today,
            )
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
            .order_by("-start_date", "-pk")
            .first()
        )
        if assignment is None or assignment.site_id == programme.site_id:
            continue
        programme.site_id = assignment.site_id
        programme.assigned_site_supervisor_id = None
        reconciliation = f"Reconciled to current site assignment on {today}."
        programme.notes = f"{programme.notes}\n{reconciliation}".strip()
        programme.save(update_fields=["site", "assigned_site_supervisor", "notes", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("site_management", "0032_remuneration_payment_account_holder_name")]

    operations = [migrations.RunPython(reconcile_active_trainee_program_sites, migrations.RunPython.noop)]
