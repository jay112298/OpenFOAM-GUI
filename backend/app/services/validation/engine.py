"""Validation engine: rules run against a case spec, produce a preflight report.

Guardrail policy (locked in PLAN.md):
- FAIL  -> blocks the run, no override
- WARN  -> overridable with one click, override logged to ValidationOverride
- PASS  -> informational

Each rule is a subclass of Rule registered in RULES. Rules must be pure
functions of the case spec (+ optional mesh metrics) so reports are reproducible.
"""

from dataclasses import dataclass
from enum import Enum


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


class Rule:
    """Base class. Subclasses set `rule_id` and implement `check(spec) -> Finding | None`."""

    rule_id: str = "base"

    def check(self, spec: dict) -> Finding | None:  # pragma: no cover - interface
        raise NotImplementedError


# TODO(phase-1) rules, in priority order:
#   bc-compatibility      well-posed inlet/outlet pressure-velocity combinations
#   mach-regime           incompressible solver blocked when estimated Ma > 0.3
#   yplus-wall-treatment  wall function vs low-Re mesh mismatch
#   turbulence-inlet      k/omega/epsilon computed from intensity + length scale
#   mesh-quality          checkMesh gates (non-orthogonality, skewness, aspect)
#   courant-estimate      transient dt sanity
#   scheme-solver-compat  steadyState ddt vs transient solver, etc.
#   reynolds-model        Re vs turbulence/transition model sanity
RULES: list[Rule] = []


def run_preflight(case_id: str) -> dict:
    """Run all rules against the case's spec. Stub until rules land in phase 1."""
    # TODO(phase-1): load spec from DB, evaluate RULES, persist report
    return {
        "case_id": case_id,
        "findings": [],
        "summary": {"pass": 0, "warn": 0, "fail": 0},
        "can_run": True,
    }
