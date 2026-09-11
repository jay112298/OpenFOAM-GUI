"""Validation rules for the airfoil / external-aero pipeline (Phase 1).

Each rule takes a ValidationContext and returns a Finding (or None to stay
silent). Keep rules pure and independent; register them in ALL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from app.services.validation.engine import Finding, Severity

if TYPE_CHECKING:
    from app.services.validation.engine import ValidationContext

Rule = Callable[["ValidationContext"], "Finding | None"]

# wall-function y+ valid band
_WF_LOW, _WF_HIGH = 30.0, 300.0
_LOWRE_MODELS = {"kOmegaSSTLM", "kOmegaSSTSAS"}


def mach_regime(ctx: "ValidationContext") -> Finding | None:
    """Match the flow regime to the solver.

    The solver follows from the case's flow type (simpleFoam / rhoSimpleFoam),
    so this checks the *physics choice*: incompressible above Mach 0.3 is wrong,
    and compressible far below it is needlessly stiff.
    """
    ma = ctx.derived.mach
    solver = ctx.derived.solver
    if ctx.params.flow_type == "compressible":
        if ma > 0.7:
            return Finding(
                "mach-regime", Severity.warn,
                f"Mach {ma:.2f} is transonic — shocks are likely and '{solver}' resolves them poorly.",
                "Expect convergence trouble; a density-based solver (rhoCentralFoam) suits Mach > 0.7.",
            )
        if ma < 0.1:
            return Finding(
                "mach-regime", Severity.warn,
                f"Mach {ma:.2f} is effectively incompressible, but this case solves the energy equation.",
                "Switch the flow type to incompressible — simpleFoam converges faster and more robustly.",
            )
        return Finding("mach-regime", Severity.ok,
                       f"Mach {ma:.2f} — compressible solver '{solver}' is the right choice.")

    if ma > 0.3:
        return Finding(
            "mach-regime", Severity.fail,
            f"Mach {ma:.2f} exceeds 0.3 but this case is incompressible ('{solver}'), "
            "so density changes the solution ignores would be significant.",
            "Set the flow type to compressible (rhoSimpleFoam), or reduce the velocity.",
        )
    return Finding("mach-regime", Severity.ok, f"Mach {ma:.2f} — incompressible assumption valid.")


def yplus_wall_treatment(ctx: "ValidationContext") -> Finding | None:
    yp = ctx.params.target_yplus
    model = ctx.params.turbulence_model
    low_re = model in _LOWRE_MODELS
    # Resolved boundary layers (y+~1) + a continuous (Spalding) wall function are
    # valid for kOmegaSST, so a low y+ is correct, not a warning.
    if getattr(ctx.params, "boundary_layers", False):
        if yp > 5:
            return Finding(
                "yplus-wall-treatment", Severity.warn,
                f"Boundary layers are on (resolved wall) but target y+ is {yp:g}.",
                "With prism layers, target y+ ~ 1 to resolve the viscous sublayer.",
            )
        return Finding("yplus-wall-treatment", Severity.ok,
                       f"Resolved wall: y+ target {yp:g} with prism layers.")
    if low_re and yp > 5:
        return Finding(
            "yplus-wall-treatment", Severity.warn,
            f"Low-Re model '{model}' wants y+ ~1 but target y+ is {yp:g}.",
            "Set target y+ ~ 1 so the mesh resolves the viscous sublayer.",
        )
    if not low_re and not (_WF_LOW <= yp <= _WF_HIGH):
        return Finding(
            "yplus-wall-treatment", Severity.warn,
            f"Wall-function model '{model}' wants y+ in [{_WF_LOW:g}, {_WF_HIGH:g}], target is {yp:g}.",
            "Pick y+ ~ 30–300 for wall functions, or switch to a low-Re model with y+ ~ 1.",
        )
    return Finding("yplus-wall-treatment", Severity.ok, f"y+ target {yp:g} consistent with '{model}'.")


def transition_model_mesh(ctx: "ValidationContext") -> Finding | None:
    """kOmegaSSTLM only predicts transition on a wall-resolved mesh."""
    if ctx.params.turbulence_model not in _LOWRE_MODELS:
        return None
    p = ctx.params
    resolved = p.boundary_layers and p.target_yplus <= 5
    if not resolved:
        return Finding(
            "transition-model-mesh", Severity.warn,
            f"'{p.turbulence_model}' predicts laminar-turbulent transition, which needs a "
            f"wall-resolved mesh (y+ ~ 1). This case has "
            f"{'no boundary layers' if not p.boundary_layers else f'y+ target {p.target_yplus:g}'}.",
            "Enable boundary layers and set target y+ ~ 1, or use kOmegaSST (fully turbulent).",
        )
    return Finding(
        "transition-model-mesh", Severity.ok,
        f"'{p.turbulence_model}' with a wall-resolved mesh (y+ target {p.target_yplus:g}).",
    )


def reynolds_model(ctx: "ValidationContext") -> Finding | None:
    re = ctx.derived.reynolds
    model = ctx.params.turbulence_model
    if re < 1000:
        return Finding(
            "reynolds-model", Severity.warn,
            f"Re {re:.0f} is effectively laminar; a turbulence model may over-predict mixing.",
            "Consider a laminar setup (no turbulence model) at this Reynolds number.",
        )
    if re < 2e5 and model not in _LOWRE_MODELS:
        return Finding(
            "reynolds-model", Severity.warn,
            f"Re {re:.0f} is in the transitional range; '{model}' assumes fully turbulent flow.",
            "Use a transition model (kOmegaSSTLM) to capture laminar separation / transition.",
        )
    return Finding("reynolds-model", Severity.ok, f"Re {re:.2e} suits a fully-turbulent RANS model.")


def turbulence_inlet_sanity(ctx: "ValidationContext") -> Finding | None:
    i = ctx.params.turbulence_intensity
    if not (0.001 <= i <= 0.2):
        return Finding(
            "turbulence-inlet", Severity.warn,
            f"Turbulence intensity {i*100:.1f}% is outside the usual 0.1–20% range.",
            "External aero is typically 0.1–1%; internal/duct flows 1–10%.",
        )
    return Finding(
        "turbulence-inlet", Severity.ok,
        f"Inlet k={ctx.derived.k:.3g}, omega={ctx.derived.omega:.3g} computed from I={i*100:.1f}%.",
    )


def bc_completeness(ctx: "ValidationContext") -> Finding | None:
    # Airfoil template patches are fixed; assert they all resolve.
    required = {"farfield", "airfoil", "frontAndBack"}
    # spec-driven BCs may be empty for templated cases (generated at build time)
    bcs = ctx.spec.get("boundary_conditions", {})
    if bcs:
        missing = required - set(bcs)
        if missing:
            return Finding(
                "bc-completeness", Severity.fail,
                f"Boundary conditions missing for patches: {sorted(missing)}.",
                "Every mesh patch needs a BC for every field.",
            )
    return Finding("bc-completeness", Severity.ok, "All patches have boundary conditions.")


def scheme_solver_compat(ctx: "ValidationContext") -> Finding | None:
    solver = ctx.spec.get("numerics", {}).get("solver", "simpleFoam")
    time_treatment = ctx.spec.get("physics", {}).get("time_treatment", "steady")
    steady_solvers = {"simpleFoam", "rhoSimpleFoam"}
    if solver in steady_solvers and time_treatment == "transient":
        return Finding(
            "scheme-solver-compat", Severity.fail,
            f"Solver '{solver}' is steady-state but physics is set to transient.",
            "Use a transient solver (pimpleFoam) or set steady time treatment.",
        )
    return Finding("scheme-solver-compat", Severity.ok, "Solver and time treatment are consistent.")


def domain_size(ctx: "ValidationContext") -> Finding | None:
    r = ctx.params.farfield_radius
    if r < 10:
        return Finding(
            "domain-size", Severity.warn,
            f"Far-field radius {r:g}c is close to the body (<10c).",
            "Use >=15c far-field radius to avoid blockage effects on Cl/Cd.",
        )
    return Finding("domain-size", Severity.ok, f"Far-field radius {r:g}c avoids blockage.")


def aoa_range(ctx: "ValidationContext") -> Finding | None:
    aoa = abs(ctx.params.angle_of_attack)
    if aoa > 15:
        return Finding(
            "aoa-range", Severity.warn,
            f"Angle of attack {aoa:g}° is likely past stall for steady RANS.",
            "Expect separated flow; steady RANS is unreliable. Validate against data or go transient.",
        )
    return Finding("aoa-range", Severity.ok, f"Angle of attack {aoa:g}° is in the attached-flow range.")


def mesh_quality(ctx: "ValidationContext") -> Finding | None:
    """Fed by the checkMesh log, so it stays silent until the mesher has run.

    Domain-independent — the turbo rule set imports this one.
    """
    m = ctx.mesh_metrics
    if not m:
        return None  # only evaluated once checkMesh has run
    max_nonortho = m.get("maxNonOrtho")
    max_skew = m.get("maxSkewness")
    if not m.get("meshOK", True):
        numbers = ", ".join(
            part
            for part in (
                f"max non-orthogonality {max_nonortho:.0f}°" if max_nonortho is not None else "",
                f"max skewness {max_skew:.1f}" if max_skew is not None else "",
            )
            if part
        )
        return Finding(
            "mesh-quality", Severity.warn,
            "checkMesh flagged the mesh (skewness, concave cells or tet decomposition)"
            + (f": {numbers}." if numbers else "."),
            "The solver will usually still run; treat the numbers as indicative and refine "
            "the mesh if the residuals stall. log.checkMesh has the detail.",
        )
    if max_nonortho is not None and max_nonortho > 70:
        return Finding(
            "mesh-quality", Severity.warn,
            f"Max non-orthogonality {max_nonortho:.0f}° is high (>70°).",
            "Add non-orthogonal correctors or improve the mesh near the surface.",
        )
    if max_skew is not None and max_skew > 4:
        return Finding(
            "mesh-quality", Severity.warn,
            f"Max skewness {max_skew:.1f} exceeds 4.",
            "Reduce snappy refinement jumps or relax layer settings.",
        )
    return Finding("mesh-quality", Severity.ok, "Mesh quality within thresholds.")


ALL: list[Rule] = [
    mach_regime,
    yplus_wall_treatment,
    transition_model_mesh,
    reynolds_model,
    turbulence_inlet_sanity,
    bc_completeness,
    scheme_solver_compat,
    domain_size,
    aoa_range,
    mesh_quality,
]
