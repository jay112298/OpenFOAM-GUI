"""Case templates: pre-filled specs + field metadata for the GUI form."""

from fastapi import APIRouter, HTTPException

from app.templates.registry import get_template, list_templates

router = APIRouter()


@router.get("/")
async def templates():
    return list_templates()


@router.get("/{template_id}")
async def template(template_id: str):
    t = get_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return t
