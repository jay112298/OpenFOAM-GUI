"""Template registry. Phase 1 ships the airfoil template; more per roadmap."""

from app.templates.airfoil import AIRFOIL_TEMPLATE

TEMPLATES = {AIRFOIL_TEMPLATE["id"]: AIRFOIL_TEMPLATE}


def list_templates() -> list[dict]:
    return [
        {"id": t["id"], "name": t["name"], "domain": t["domain"], "description": t["description"]}
        for t in TEMPLATES.values()
    ]


def get_template(template_id: str) -> dict | None:
    return TEMPLATES.get(template_id)
