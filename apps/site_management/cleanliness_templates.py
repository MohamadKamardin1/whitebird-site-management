from __future__ import annotations

from typing import Any

from apps.core.models import AuditLog
from apps.core.services import model_data, record_audit

from .models import InspectionFrequency, InspectionItemType, InspectionTemplate, Site, SiteArea

DEFAULT_CLEANLINESS_AREAS = (
    ("Toilets / Vyooni", "TOILETS", "Toilet facilities and hygiene supplies."),
    ("Offices / Ofisini", "OFFICES", "Office floors, furniture, equipment, and readiness."),
    ("Indoor areas / Eneo la ndani", "INDOOR", "Indoor floors, entrances, furniture, and water readiness."),
    ("Outdoor areas / Eneo la nje", "OUTDOOR", "Paths, parking, fences, grass, and surrounding areas."),
    ("Garden / Bustani", "GARDEN", "Garden maintenance, watering, pruning, and safe paths."),
    ("Store and equipment / Usimamizi wa store", "STORE", "Store keys, equipment return, cleaning, and repair separation."),
    ("Staff performance / Maendeleo ya wafanyakazi", "STAFF", "Daily staff punctuality, attendance, conduct, and task completion."),
)

CLEANLINESS_ITEMS_BY_CODE: dict[str, tuple[tuple[str, str], ...]] = {
    "TOILETS": (
        ("Floor and wall surfaces have been washed and cleaned", "Confirm floors and walls are visibly clean."),
        ("Mirrors have been cleaned", "Check mirrors for marks, dust, and water spots."),
        ("Rubbish bin has been cleaned", "Empty, wash, line, and reset the bin."),
        ("Toilet has been washed and cleaned", "Check the toilet bowl, seat, base, and surrounding floor."),
        ("Soap, brushes, and cleaning tools are washed and stored properly", "Confirm tools are clean and returned to their designated place."),
        ("Water has been put into the cleaning tank", "Confirm water is available for cleaning work."),
        ("Water has been put into the hand-washing container", "Confirm hand-washing water is available."),
        ("Towels have been placed", "Confirm clean hand towels are available where required."),
        ("Toilet paper has been placed", "Confirm toilet paper is available and replenished."),
    ),
    "OFFICES": (
        ("Floor and wall surfaces have been cleaned", "Complete before the office opens."),
        ("Chairs, tables, and office equipment have been dusted", "Dust before the office is opened."),
        ("Rubbish bin has been washed and cleaned", "Empty, wash, line, and reset the bin."),
        ("Desk has been arranged and cleaned", "Leave the desk orderly and ready for use."),
        ("Floors, doors, and windows have been cleaned", "Check the full office entry and working area."),
        ("Tables have been arranged and curtains straightened", "Restore the room to its expected arrangement."),
        ("Ceiling has been wiped and cobwebs removed", "Check corners, ceiling edges, and fittings."),
        ("Furniture has been arranged", "Confirm chairs and furniture are in the agreed layout."),
        ("Rubbish bin has been placed", "Confirm the bin is returned to its designated location."),
    ),
    "INDOOR": (
        ("Floor and wall surfaces have been cleaned", "Check all indoor surfaces included in the daily route."),
        ("Stairs have been cleaned before opening", "Check steps, rails, landings, and edges."),
        ("Rubbish bin has been cleaned", "Empty, wash, line, and reset the bin."),
        ("Entrance has been wiped and cleaned", "Check the entrance, doors, and immediate approach."),
        ("Floors and doors have been cleaned", "Check the full indoor circulation route."),
        ("Furniture has been arranged and curtains straightened", "Restore the area to its expected presentation."),
        ("Ceiling has been wiped and cobwebs removed", "Check corners and ceiling edges."),
        ("Furniture has been arranged", "Confirm furniture is ready for use."),
        ("Bin has been placed", "Confirm the bin is returned to its designated location."),
        ("Water has been put in the water container and it has been covered", "Confirm water is available and safely covered."),
    ),
    "OUTDOOR": (
        ("Grass has been cut", "Check the designated outdoor grass areas."),
        ("Parking area has been cleaned", "Remove litter, leaves, and visible dirt from parking."),
        ("Fence has been cleaned", "Check the visible fence line and entrance points."),
        ("Paths and passages have been cleaned", "Ensure safe, clear movement through the site."),
        ("All surrounding areas have been cleaned", "Check the perimeter and areas around buildings."),
        ("Outdoor area has been watered", "Confirm watering was completed where scheduled."),
        ("Rubbish bin has been wiped and cleaned", "Reset outdoor bins and remove visible residue."),
    ),
    "GARDEN": (
        ("Grass has been cut", "Check grass and maintained lawn areas."),
        ("Flower beds have been watered", "Confirm flower beds received the required water."),
        ("Flowers have been pruned", "Remove dead growth and maintain the agreed appearance."),
        ("Garden area has been cleared", "Remove litter, leaves, and unnecessary material."),
        ("Garden area has been watered", "Confirm all scheduled garden watering is complete."),
        ("Safe paths have been created", "Keep paths clear, visible, and safe to use."),
        ("Garden has been maintained with care", "Record an exception if the garden needs additional work."),
        ("Branches have been cut", "Remove unsafe or obstructive branches where assigned."),
        ("Damaged plants have been removed or replaced", "Record the action or exception clearly."),
    ),
    "STORE": (
        ("Store door is locked and the key has been handed over", "Record the handover in the shift notes when needed."),
        ("Store door is locked and the key has been returned to the store", "Confirm the key is controlled and accounted for."),
        ("All equipment is returned to its place and organized", "Check the equipment layout against the store standard."),
        ("Used equipment has been washed and returned to the store", "Do not close the check while used tools remain dirty."),
        ("Used equipment is returned to its proper location", "Confirm equipment is easy to find for the next shift."),
        ("Equipment needing repair has been separated and reported", "Record the item and raise a stock or maintenance issue."),
    ),
    "STAFF": (
        ("Worker can perform within the required time", "Use the exception note for coaching or time-risk details."),
        ("Worker is honest and hardworking", "Record only work-related, evidenced observations."),
        ("Worker completes tasks before the required time", "Use the exception note if support or retraining is needed."),
        ("Worker is present in all assigned work areas", "Cross-check attendance and assigned route."),
        ("Worker does not leave the work area without informing the supervisor", "Record the responsible cleaner and corrective action when applicable."),
        ("Worker follows instructions and performs assigned work", "Use the exception note for a clear follow-up action."),
    ),
}


def provision_site_cleanliness_setup(*, site: Site, actor: Any) -> int:
    """Create the PDF-derived operational areas when absent and provision surveys."""
    if not site.areas.filter(is_active=True).exists():
        for area_name, area_code, description in DEFAULT_CLEANLINESS_AREAS:
            area = SiteArea.objects.create(
                site=site,
                area_name=area_name,
                area_code=area_code,
                description=description,
                created_by=actor,
                updated_by=actor,
            )
            record_audit(
                action=AuditLog.Action.CREATE,
                actor=actor,
                entity=area,
                summary=f"Provisioned PDF-derived operational area {area_name} for {site.name}.",
                after_data=model_data(area),
            )
    return provision_site_cleanliness_templates(site=site, actor=actor)


def provision_site_cleanliness_templates(*, site: Site, actor: Any) -> int:
    """Create missing daily PDF-derived checklists without overwriting history."""
    created_count = 0
    for area_name, area_code, description in DEFAULT_CLEANLINESS_AREAS:
        area, _ = SiteArea.objects.get_or_create(
            site=site,
            area_code=area_code,
            defaults={
                "area_name": area_name,
                "description": description,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if not area.is_active:
            continue
        template, created = InspectionTemplate.objects.get_or_create(
            site=site,
            area=area,
            template_name=f"Daily Cleanliness Survey · {area.area_name}",
            defaults={
                "description": f"PDF-derived daily cleanliness worksheet for {area.area_name}.",
                "frequency": InspectionFrequency.DAILY,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if not created:
            continue
        created_count += 1
        for sequence, (item_label, help_text) in enumerate(CLEANLINESS_ITEMS_BY_CODE[area_code], start=1):
            template.items.create(
                item_label=item_label,
                item_type=InspectionItemType.YES_NO,
                required=True,
                sequence=sequence,
                help_text=help_text,
            )
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=template,
            summary=f"Provisioned PDF-derived daily cleanliness template for {site.name} / {area.area_name}.",
            after_data=model_data(template),
        )
    return created_count
