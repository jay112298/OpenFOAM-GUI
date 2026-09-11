"""Validation rules for the axial fan / compressor passage (Phase 2.3).

Same contract as the aero rules: pure functions of the context, FAIL blocks the
run, WARN is overridable. These check the things a first-time turbomachinery
user gets wrong — a passage that isn't 360/n_blades wide, a blade that can't fit
in its own pitch, an operating point nowhere near where the blade was twisted
for, or a tip that has gone compressible under an incompressible solver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.validation.engine import Finding, Severity
# checkMesh quality is not domain-specific — reuse the aero rule verbatim
from app.services.validation.rules import mesh_quality

if TYPE_CHECKING:
    from app.services.validation.engine import ValidationContext

_WF_LOW, _WF_HIGH = 30.0, 300.0


def tip_mach(ctx: "ValidationContext") -> Finding | None:
    """The blade tip sees the highest relative speed in the machine."""
    ma = ctx.derived.tip_mach
    if ma > 0.3:
        return Finding(
            "tip-mach", Severity.fail,
            f"Relative Mach at the blade tip is {ma:.2f}, above 0.3, but this case is "
            "incompressible (simpleFoam) — density changes it ignores would be significant.",
            "Lower the RPM or the tip radius, or wait for the compressible turbo template.",
        )
    if ma > 0.25:
        return Finding(
            "tip-mach", Severity.warn,
            f"Relative Mach at the tip is {ma:.2f} — close to the incompressible limit of 0.3.",
            "Fine for now, but a modest RPM increase will push this case out of validity.",
        )
    return Finding("tip-mach", Severity.ok,
                   f"Tip relative Mach {ma:.2f} (tip speed {ctx.derived.tip_speed:.0f} m/s).")


def hub_tip_ratio(ctx: "ValidationContext") -> Finding | None:
    p = ctx.params
    if p.tip_radius <= p.hub_radius:
        return Finding(
            "hub-tip-ratio", Severity.fail,
            f"Tip radius {p.tip_radius:g} m is not larger than hub radius {p.hub_radius:g} m.",
            "There is no annulus to mesh. Set tip radius above hub radius.",
        )
    ratio = p.hub_radius / p.tip_radius
    if ratio < 0.2:
        return Finding(
            "hub-tip-ratio", Severity.warn,
            f"Hub/tip ratio {ratio:.2f} is very low — the blade twists through a huge angle "
            "from hub to tip and a single NACA section will be a poor fit at both ends.",
            "Axial fans usually sit between 0.3 and 0.7. Raise the hub radius.",
        )
    if ratio > 0.9:
        return Finding(
            "hub-tip-ratio", Severity.warn,
            f"Hub/tip ratio {ratio:.2f} leaves a very thin annulus; the hub and casing "
            "boundary layers will fill most of the passage.",
            "Lower the hub radius, or expect wall-dominated, low-accuracy results.",
        )
    return Finding("hub-tip-ratio", Severity.ok, f"Hub/tip ratio {ratio:.2f} is a sane annulus.")


def blade_fits_pitch(ctx: "ValidationContext") -> Finding | None:
    """A staggered blade reaches around the axis; it must not lap itself."""
    worst = max(ctx.derived.sections, key=lambda s: s.tangential_extent / s.pitch)
    ratio = worst.tangential_extent / worst.pitch
    if ratio >= 1.0:
        return Finding(
            "blade-fits-pitch", Severity.fail,
            f"At r = {worst.radius:.3f} m the staggered blade spans "
            f"{worst.tangential_extent * 1000:.0f} mm around, more than the "
            f"{worst.pitch * 1000:.0f} mm blade pitch — neighbouring blades overlap completely.",
            "Shorten the chord, add blades, or lower the RPM (which reduces stagger).",
        )
    if ratio > 0.75:
        return Finding(
            "blade-fits-pitch", Severity.warn,
            f"At r = {worst.radius:.3f} m the blade spans {ratio * 100:.0f}% of its pitch, "
            "so the passage between blades is narrow and the mesh there will be coarse.",
            "Raise cells per chord, or shorten the chord / add blades.",
        )
    return Finding("blade-fits-pitch", Severity.ok,
                   f"Blade spans at most {ratio * 100:.0f}% of the blade pitch.")


def solidity_range(ctx: "ValidationContext") -> Finding | None:
    hub, tip = ctx.derived.sections[0], ctx.derived.sections[-1]
    if hub.solidity < 0.4:
        return Finding(
            "solidity", Severity.warn,
            f"Hub solidity (chord/pitch) is {hub.solidity:.2f} — below ~0.5 the blades barely "
            "guide the flow, so the row turns it much less than the blade angles suggest.",
            "Lengthen the chord or add blades to reach a hub solidity near 1.",
        )
    if tip.solidity > 2.0:
        return Finding(
            "solidity", Severity.warn,
            f"Tip solidity is {tip.solidity:.2f}; the passage is a long, narrow channel.",
            "Shorten the chord or reduce the blade count unless a high-solidity cascade "
            "is what you intend.",
        )
    return Finding(
        "solidity", Severity.ok,
        f"Solidity {hub.solidity:.2f} at the hub to {tip.solidity:.2f} at the tip.",
    )


def flow_coefficient(ctx: "ValidationContext") -> Finding | None:
    """Through-flow versus tip speed — where the machine sits on its own map."""
    phi = ctx.derived.blade.flow_coefficient
    if phi < 0.05:
        return Finding(
            "flow-coefficient", Severity.fail,
            f"Flow coefficient phi = Va/U_tip is {phi:.3f}: the blade is spinning almost "
            "without through-flow, which is a stalled machine, not an operating point.",
            "Raise the axial velocity or lower the RPM.",
        )
    if not (0.1 <= phi <= 0.8):
        return Finding(
            "flow-coefficient", Severity.warn,
            f"Flow coefficient phi = {phi:.2f} is outside the usual 0.15–0.6 band for axial fans.",
            "Low phi risks stall, high phi means the blade does very little work.",
        )
    return Finding("flow-coefficient", Severity.ok,
                   f"Flow coefficient phi = {phi:.2f}, design flow {ctx.derived.volumetric_flow:.2f} m^3/s.")


def incidence_range(ctx: "ValidationContext") -> Finding | None:
    i = ctx.params.incidence
    if abs(i) > 12:
        return Finding(
            "incidence", Severity.warn,
            f"Design incidence {i:g}° is large; the section is likely to separate and steady "
            "RANS will not represent that well.",
            "Axial rotors are usually set between 0° and 8° incidence.",
        )
    return Finding("incidence", Severity.ok,
                   f"Blade set at {i:g}° incidence to the relative inflow at every radius.")


def periodic_sector(ctx: "ValidationContext") -> Finding | None:
    """The passage must be exactly one blade pitch wide or the machine modelled
    is not the machine drawn."""
    n = int(ctx.params.n_blades)
    if n < 3:
        sector = 360.0 / n if n > 0 else 360.0
        return Finding(
            "periodic-sector", Severity.fail,
            f"{n} blade{'s' if n != 1 else ''} gives a {sector:.0f}° passage; an arc edge "
            "spanning half a turn or more has no unique centre, so blockMesh cannot "
            "wrap the sector.",
            "Use 3 or more blades — below that the whole annulus has to be meshed.",
        )
    sector = 360.0 / n
    return Finding(
        "periodic-sector", Severity.ok,
        f"Solving one {sector:.1f}° passage of {n} blades, closed by rotational cyclicAMI.",
    )


def mrf_speed(ctx: "ValidationContext") -> Finding | None:
    rpm = ctx.params.rpm
    if rpm <= 0:
        return Finding(
            "mrf-speed", Severity.fail,
            f"Shaft speed is {rpm:g} rpm, so the MRF zone does not rotate and the rotor "
            "does no work at all.",
            "Set a positive RPM (rotation is about +z, the through-flow axis).",
        )
    return Finding(
        "mrf-speed", Severity.ok,
        f"MRF rotor zone at {rpm:g} rpm ({ctx.derived.shaft_omega:.0f} rad/s) about +z.",
    )


def yplus_wall_treatment(ctx: "ValidationContext") -> Finding | None:
    yp = ctx.params.target_yplus
    if ctx.params.boundary_layers:
        if yp > 5:
            return Finding(
                "yplus-wall-treatment", Severity.warn,
                f"Prism layers are on (resolved wall) but target y+ is {yp:g}.",
                "With layers, target y+ ~ 1 so the viscous sublayer is resolved.",
            )
        return Finding("yplus-wall-treatment", Severity.ok,
                       f"Resolved wall: y+ target {yp:g} with prism layers.")
    if not (_WF_LOW <= yp <= _WF_HIGH):
        return Finding(
            "yplus-wall-treatment", Severity.warn,
            f"Wall functions need y+ in [{_WF_LOW:g}, {_WF_HIGH:g}]; target is {yp:g}.",
            "Pick y+ 30–100, or enable prism layers and target y+ ~ 1.",
        )
    return Finding("yplus-wall-treatment", Severity.ok,
                   f"y+ target {yp:g} sits in the wall-function band.")


def reynolds_model(ctx: "ValidationContext") -> Finding | None:
    re = ctx.derived.reynolds
    if re < 5e4:
        return Finding(
            "reynolds-model", Severity.warn,
            f"Blade chord Reynolds number is {re:.1e}; below ~1e5 the boundary layer is "
            f"largely laminar and '{ctx.params.turbulence_model}' assumes it is not.",
            "Lengthen the chord, raise the speed, or treat the loss predictions as indicative.",
        )
    return Finding("reynolds-model", Severity.ok,
                   f"Chord Reynolds {re:.2e} at mid-span relative velocity.")


def domain_length(ctx: "ValidationContext") -> Finding | None:
    p = ctx.params
    if p.outlet_length < 2.0:
        return Finding(
            "domain-length", Severity.warn,
            f"Outlet duct is only {p.outlet_length:g} chords long; the swirling wake leaves "
            "the domain before it settles and the outlet pressure BC will distort it.",
            "Use at least 3–4 chords downstream.",
        )
    if p.inlet_length < 1.0:
        return Finding(
            "domain-length", Severity.warn,
            f"Inlet duct is only {p.inlet_length:g} chords long; the blade's upstream "
            "influence reaches the inlet plane where the velocity is held fixed.",
            "Use at least 1.5–2 chords upstream.",
        )
    return Finding(
        "domain-length", Severity.ok,
        f"Duct runs {p.inlet_length:g}c upstream and {p.outlet_length:g}c downstream of the blade.",
    )


def blade_resolution(ctx: "ValidationContext") -> Finding | None:
    """How many cells actually land on the blade surface."""
    p = ctx.params
    base = p.chord / max(2, int(p.cells_per_chord))
    surface_cell = base / (2 ** int(p.refinement_level))
    across = p.chord / surface_cell
    if across < 20:
        return Finding(
            "blade-resolution", Severity.warn,
            f"Only about {across:.0f} cells span the chord at the blade surface.",
            "Raise cells per chord or the refinement level; below ~30 the pressure "
            "distribution, and so the work and efficiency, are rough.",
        )
    return Finding("blade-resolution", Severity.ok,
                   f"About {across:.0f} cells across the chord on the blade surface.")


def turbulence_inlet_sanity(ctx: "ValidationContext") -> Finding | None:
    i = ctx.params.turbulence_intensity
    if not (0.001 <= i <= 0.2):
        return Finding(
            "turbulence-inlet", Severity.warn,
            f"Turbulence intensity {i * 100:.1f}% is outside the usual 0.1–20% range.",
            "Ducted machines are typically 3–10%.",
        )
    return Finding(
        "turbulence-inlet", Severity.ok,
        f"Inlet k={ctx.derived.k:.3g}, omega={ctx.derived.omega:.3g} computed from I={i * 100:.1f}%.",
    )


def euler_work_estimate(ctx: "ValidationContext") -> Finding | None:
    """Tell the user up front what the rotor should deliver.

    Euler: the ideal total pressure rise is rho * U * dV_theta. Using the exit
    relative angle implied by the blade metal angle would need the camber line,
    so this quotes the ceiling (complete turning to axial) as an upper bound.
    """
    d = ctx.derived
    mid = d.sections[len(d.sections) // 2]
    ceiling = d.density * mid.blade_speed * mid.blade_speed
    return Finding(
        "euler-work", Severity.ok,
        f"At mid-span U = {mid.blade_speed:.0f} m/s with relative inflow at "
        f"{mid.relative_angle:.0f}° from axial; Euler caps the total pressure rise at "
        f"{ceiling:.0f} Pa (a real row reaches a fraction of that).",
    )


ALL = [
    periodic_sector,
    mrf_speed,
    hub_tip_ratio,
    blade_fits_pitch,
    solidity_range,
    flow_coefficient,
    incidence_range,
    tip_mach,
    reynolds_model,
    yplus_wall_treatment,
    blade_resolution,
    domain_length,
    turbulence_inlet_sanity,
    euler_work_estimate,
    mesh_quality,
]
