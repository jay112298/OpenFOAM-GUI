"""Template registry. One entry per ready-to-run case type; see ROADMAP."""

from app.templates.airfoil import AIRFOIL_COMPRESSIBLE_TEMPLATE, AIRFOIL_TEMPLATE
from app.templates.axial_fan import AXIAL_FAN_TEMPLATE

TEMPLATES = {
    t["id"]: t
    for t in (AIRFOIL_TEMPLATE, AIRFOIL_COMPRESSIBLE_TEMPLATE, AXIAL_FAN_TEMPLATE)
}


def list_templates() -> list[dict]:
    return [
        {"id": t["id"], "name": t["name"], "domain": t["domain"], "description": t["description"]}
        for t in TEMPLATES.values()
    ]


def get_template(template_id: str) -> dict | None:
    return TEMPLATES.get(template_id)
