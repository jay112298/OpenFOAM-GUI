"""Validation engine: rules run against a case spec, produce a preflight report.

Guardrail policy (locked in PLAN.md):
- FAIL  -> blocks the run, no override
- WARN  -> overridable with one click, override logged to ValidationOverride
- PASS  -> informational

Each rule is a callable taking a ValidationContext and returning a Finding.
Rules are pure functions of the context so reports are reproducible.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from app.services.generators.airfoil_case import AirfoilParams, DerivedState, derive


class Severity(str, Enum):
    ok = "pass"
    warn = "warn"
    fail = "fail"


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class ValidationContext:
    spec: dict
    params: AirfoilParams
    derived: DerivedState
    mesh_metrics: dict | None = None  # populated after checkMesh


def build_context(spec: dict) -> ValidationContext:
    params = AirfoilParams.from_spec(spec)
    return ValidationContext(spec=spec, params=params, derived=derive(params))


# --- import rules after Finding/Severity defined to avoid cycle ---
from app.services.validation import rules as _rules  # noqa: E402

RULES = _rules.ALL


def run_rules(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for rule in RULES:
        result = rule(ctx)
        if result is not None:
            findings.append(result)
    return findings


def summarize(findings: list[Finding]) -> dict:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for f in findings:
        counts[f.severity.value] += 1
    return counts


def preflight_report(spec: dict, mesh_metrics: dict | None = None) -> dict:
    ctx = build_context(spec)
    ctx.mesh_metrics = mesh_metrics
    findings = run_rules(ctx)
    summary = summarize(findings)
    return {
        "findings": [f.to_dict() for f in findings],
        "summary": summary,
        "can_run": summary["fail"] == 0,
    }


def run_preflight(case_id: str) -> dict:
    """Entry point used by the API. Loads the case spec, runs rules."""
    from sqlmodel import Session

    from app.db import engine
    from app.models.case import Case

    with Session(engine) as session:
        case = session.get(Case, case_id)
        if case is None:
            return {"error": "case not found", "findings": [], "summary": {}, "can_run": False}
        report = preflight_report(case.spec)
    report["case_id"] = case_id
    return report
