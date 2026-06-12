"""Case templates: pre-filled case specs per domain. Phase 1: airfoil."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_templates():
    # TODO(phase-1): populate from app/templates registry
    return []
