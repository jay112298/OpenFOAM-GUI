"""Validation stage: run the rule engine against a case spec -> preflight report."""

from fastapi import APIRouter

from app.services.validation.engine import run_preflight

router = APIRouter()


@router.post("/{case_id}/preflight")
async def preflight(case_id: str):
    return run_preflight(case_id)


@router.post("/{case_id}/override/{rule_id}")
async def override_warning(case_id: str, rule_id: str):
    # TODO(phase-1): log override to ValidationOverride table
    return {"todo": "phase-1"}
