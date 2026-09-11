"""Axial fan passage: blade geometry, case assembly, MRF setup, rules, post.

None of these need Docker — the meshing step is the only part that does, and
`write_case_files` stops short of it.
"""

import math
import struct

import numpy as np

from app.services.generators.axial_fan_case import (
    AxialFanParams,
    derive,
    write_case_files,
)
from app.services.geometry import blade
from app.services.post import fan
from app.services.validation.engine import preflight_report
from app.templates.axial_fan import AXIAL_FAN_TEMPLATE


def _spec(**over) -> dict:
    import copy

    spec = copy.deepcopy(AXIAL_FAN_TEMPLATE["spec"])
    for dotted, value in over.items():
        path = dotted.split("__")
        node = spec
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return spec


# --- geometry -------------------------------------------------------------


def test_blade_twist_follows_the_velocity_triangle():
    """Stagger is derived, not typed: gamma = atan(U/Va) - incidence."""
    spec = blade.BladeSpec(rpm=3000, axial_velocity=12, incidence=4)
    secs = blade.sections(spec, n=5)
    for s in secs:
        beta1 = math.degrees(math.atan2(spec.omega * s.radius, spec.axial_velocity))
        assert abs(s.relative_angle - beta1) < 1e-9
        assert abs(s.stagger - (beta1 - 4)) < 1e-9
    # the tip moves faster, so it must be staggered further round than the hub
    assert secs[-1].stagger > secs[0].stagger + 10


def test_zero_through_flow_would_be_a_fully_tangential_blade():
    spec = blade.BladeSpec(axial_velocity=1e-9)
    assert blade.section_at(spec, spec.mean_radius).relative_angle > 89


def test_blade_stl_is_a_closed_binary_solid_repeated_at_the_pitch(tmp_path):
    spec = blade.BladeSpec()
    path = blade.export_stl(spec, tmp_path / "blade.stl")
    raw = path.read_bytes()
    n_facets = struct.unpack("<I", raw[80:84])[0]
    assert len(raw) == 84 + 50 * n_facets          # binary STL, exactly
    assert n_facets % 3 == 0                        # three copies of one blade

    loft = blade.surface(spec)
    radius = np.hypot(loft[..., 0], loft[..., 1])
    # the loft must overhang both walls so snappy gets a clean cut
    assert radius.min() < spec.hub_radius
    assert radius.max() > spec.tip_radius


def test_default_blade_stays_inside_its_own_passage():
    spec = blade.BladeSpec()
    loft = blade.surface(spec)
    theta = np.arctan2(loft[..., 1], loft[..., 0])
    assert abs(theta).max() < spec.sector_angle / 2


def test_section_outline_is_closed_and_unrolled():
    spec = blade.BladeSpec()
    outline = blade.section_outline(spec, spec.mean_radius)
    assert len(outline) > 50
    assert all(len(p) == 2 for p in outline)
    # axial extent = chord projected on the axis
    axial = [p[0] for p in outline]
    gamma = math.radians(blade.section_at(spec, spec.mean_radius).stagger)
    assert abs((max(axial) - min(axial)) - spec.chord * math.cos(gamma)) < 0.2 * spec.chord


# --- case assembly --------------------------------------------------------


def test_passage_case_writes_every_dict(tmp_path):
    write_case_files(_spec(), tmp_path)
    for f in [
        "system/blockMeshDict", "system/snappyHexMeshDict", "system/topoSetDict",
        "system/surfaceFeatureExtractDict", "system/controlDict", "system/fvSchemes",
        "system/fvSolution", "constant/MRFProperties", "constant/transportProperties",
        "constant/turbulenceProperties", "constant/triSurface/blade.stl",
        "0/U", "0/p", "0/k", "0/omega", "0/nut", "Allmesh", "Allrun",
    ]:
        assert (tmp_path / f).exists(), f"missing {f}"
    assert (tmp_path / "Allrun").stat().st_mode & 0o111


def test_periodic_faces_are_rotational_cyclic_ami(tmp_path):
    write_case_files(_spec(), tmp_path)
    text = (tmp_path / "system/blockMeshDict").read_text()
    assert "cyclicAMI" in text
    assert "transform rotational" in text
    assert "rotationAxis (0 0 1)" in text
    assert "neighbourPatch periodic2" in text and "neighbourPatch periodic1" in text


def test_mrf_excludes_every_patch_that_is_not_a_rotating_wall(tmp_path):
    """Regression: with the inlet and outlet left off nonRotatingPatches, MRF
    treats them as rotating walls, zeroes their flux and seals the machine
    shut — the solver then converges on a fan churning a closed box."""
    write_case_files(_spec(), tmp_path)
    text = (tmp_path / "constant/MRFProperties").read_text()
    start = text.index("nonRotatingPatches")
    listed = text[start : text.index(";", start)]
    for patch in ("inlet", "outlet", "shroud", "periodic1", "periodic2"):
        assert patch in listed, f"{patch} must be excluded from the rotating frame"
    assert "blade" not in listed and " hub" not in listed
    assert "cellZone rotor" in text


def test_rotating_walls_carry_the_shaft_speed(tmp_path):
    write_case_files(_spec(), tmp_path)
    u = (tmp_path / "0/U").read_text()
    assert u.count("rotatingWallVelocity") == 2        # blade + hub
    omega = AxialFanParams.from_spec(_spec()).rpm * 2 * math.pi / 60
    assert f"{omega:.3f}"[:6] in u or f"omega constant {omega}" in u
    assert "noSlip" in u                                # the casing stays put
    assert u.count("cyclicAMI") == 2


def test_topo_set_puts_every_cell_in_the_rotor_zone(tmp_path):
    write_case_files(_spec(), tmp_path)
    text = (tmp_path / "system/topoSetDict").read_text()
    assert "cellZoneSet" in text and "setToCellZone" in text and "rotor" in text


def test_derived_state_is_consistent_with_the_operating_point():
    p = AxialFanParams.from_spec(_spec())
    st = derive(p)
    assert st.solver == "simpleFoam"
    assert abs(st.shaft_omega - 3000 * 2 * math.pi / 60) < 1e-9
    assert abs(st.tip_speed - st.shaft_omega * p.tip_radius) < 1e-9
    annulus = math.pi * (p.tip_radius**2 - p.hub_radius**2)
    assert abs(st.volumetric_flow - annulus * p.axial_velocity) < 1e-9


def test_more_blades_make_a_narrower_sector(tmp_path):
    from app.services.generators.axial_fan_case import _sector

    six = _sector(AxialFanParams.from_spec(_spec()))
    twelve = _sector(AxialFanParams.from_spec(_spec(geometry__parameters__n_blades=12)))
    assert abs(twelve.half_angle - six.half_angle / 2) < 1e-12
    assert twelve.n_t < six.n_t


# --- design point vs operating point --------------------------------------


def test_a_single_case_designs_for_the_point_it_runs():
    p = AxialFanParams.from_spec(_spec())
    assert not p.is_off_design()
    assert p.blade_spec().rpm == p.operating_spec().rpm
    st = derive(p)
    # at the design point the incidence is flat at the requested value
    assert all(abs(s.incidence - p.incidence) < 1e-9 for s in st.incidence_profile)


def test_pinning_the_design_point_freezes_the_blade():
    spec = _spec(
        geometry__parameters__design_rpm=3000.0,
        geometry__parameters__design_axial_velocity=12.0,
        physics__reference__rpm=2400.0,
        physics__reference__axial_velocity=6.0,
    )
    p = AxialFanParams.from_spec(spec)
    assert p.is_off_design()
    # geometry follows the design point...
    assert p.blade_spec().rpm == 3000.0 and p.blade_spec().axial_velocity == 12.0
    # ...while the case is run at the operating point
    st = derive(p)
    assert abs(st.shaft_omega - 2400 * math.pi / 30) < 1e-9
    assert abs(st.tip_speed - st.shaft_omega * p.tip_radius) < 1e-9
    assert abs(st.flow_coefficient - 6.0 / st.tip_speed) < 1e-9


def test_throttling_the_fan_raises_the_incidence():
    """Less flow at the same speed means the flow arrives more tangentially,
    so it meets the fixed blade at a larger angle. That is how a fan stalls."""
    design = dict(geometry__parameters__design_rpm=3000.0,
                  geometry__parameters__design_axial_velocity=12.0,
                  physics__reference__rpm=3000.0)
    throttled = derive(AxialFanParams.from_spec(
        _spec(**design, physics__reference__axial_velocity=6.0)))
    opened = derive(AxialFanParams.from_spec(
        _spec(**design, physics__reference__axial_velocity=18.0)))

    assert throttled.peak_incidence.incidence > 4.0    # above the design 4 deg
    assert opened.peak_incidence.incidence < 4.0       # below it, toward negative
    assert throttled.peak_incidence.incidence > opened.peak_incidence.incidence


def test_the_blade_metal_angles_do_not_move_off_design():
    """Whatever the operating point, `sections` describes the blade as cut."""
    at_design = derive(AxialFanParams.from_spec(_spec()))
    off = derive(AxialFanParams.from_spec(_spec(
        geometry__parameters__design_rpm=3000.0,
        geometry__parameters__design_axial_velocity=12.0,
        physics__reference__axial_velocity=6.0,
    )))
    assert [s.stagger for s in at_design.sections] == [s.stagger for s in off.sections]


def test_off_design_incidence_is_reported_and_warned_about():
    report = preflight_report(_spec(
        geometry__parameters__design_rpm=3000.0,
        geometry__parameters__design_axial_velocity=12.0,
        physics__reference__axial_velocity=3.0,       # deeply throttled
    ))
    finding = _finding(report, "incidence")
    assert finding["severity"] == "warn"
    assert "Off design" in finding["message"]
    assert report["can_run"] is True   # a real point on the map, just a rough one


# --- validation rules -----------------------------------------------------


def _finding(report, rule_id):
    for f in report["findings"]:
        if f["rule_id"] == rule_id:
            return f
    return None


def test_template_defaults_pass_preflight():
    report = preflight_report(_spec())
    assert report["can_run"] is True, [
        f for f in report["findings"] if f["severity"] == "fail"
    ]


def test_overlapping_blades_are_blocked():
    """A long chord at high stagger laps the next blade — unmeshable as a passage."""
    report = preflight_report(_spec(geometry__parameters__chord=0.3))
    assert report["can_run"] is False
    assert _finding(report, "blade-fits-pitch")["severity"] == "fail"


def test_transonic_tip_is_blocked_for_an_incompressible_solver():
    report = preflight_report(_spec(physics__reference__rpm=20000))
    assert report["can_run"] is False
    assert _finding(report, "tip-mach")["severity"] == "fail"


def test_a_stopped_shaft_is_blocked():
    report = preflight_report(_spec(physics__reference__rpm=0))
    assert report["can_run"] is False
    assert _finding(report, "mrf-speed")["severity"] == "fail"


def test_spinning_without_through_flow_is_blocked():
    report = preflight_report(_spec(physics__reference__axial_velocity=0.5))
    assert _finding(report, "flow-coefficient")["severity"] == "fail"
    assert report["can_run"] is False


def test_two_blades_cannot_be_a_sector():
    report = preflight_report(_spec(geometry__parameters__n_blades=2))
    assert _finding(report, "periodic-sector")["severity"] == "fail"


def test_inverted_annulus_is_blocked():
    report = preflight_report(_spec(geometry__parameters__hub_radius=0.2))
    assert _finding(report, "hub-tip-ratio")["severity"] == "fail"


def test_short_outlet_duct_only_warns():
    report = preflight_report(_spec(mesh__parameters__outlet_length=1.0))
    assert _finding(report, "domain-length")["severity"] == "warn"
    assert report["can_run"] is True


def test_turbo_rules_are_used_not_the_aero_ones():
    report = preflight_report(_spec())
    ids = {f["rule_id"] for f in report["findings"]}
    assert "tip-mach" in ids and "periodic-sector" in ids
    assert "aoa-range" not in ids and "domain-size" not in ids


# --- performance post -----------------------------------------------------


def _write_series(root, name, rows):
    d = root / "postProcessing" / name / "0"
    d.mkdir(parents=True, exist_ok=True)
    body = "# Time\tvalue\n" + "".join(f"{t}\t{v}\n" for t, v in rows)
    (d / "surfaceFieldValue.dat").write_text(body)


def test_fan_performance_scales_one_passage_to_the_machine(tmp_path):
    _write_series(tmp_path, "flowRate", [(100, "-0.1"), (200, "-0.1")])
    _write_series(tmp_path, "p0Inlet", [(100, "-100"), (200, "-100")])
    _write_series(tmp_path, "p0Outlet", [(100, "100"), (200, "100")])
    _write_series(tmp_path, "outletU", [(100, "(0 5 12)"), (200, "(0 5 12)")])
    moment = tmp_path / "postProcessing" / "bladeForces" / "0"
    moment.mkdir(parents=True)
    (moment / "moment.dat").write_text(
        "# Time\ttotal_x total_y total_z\n"
        "100\t0 0 -0.5\t0 0 -0.5\t0 0 0\n"
        "200\t0 0 -0.5\t0 0 -0.5\t0 0 0\n"
    )

    spec = _spec()
    perf = fan.performance(tmp_path, spec)
    last = perf["latest"]
    n = 6
    assert len(perf["history"]) == 2
    assert abs(last["flow_rate"] - 0.1 * n) < 1e-9        # one passage x blades
    assert abs(last["total_pressure_rise"] - 200.0) < 1e-9
    assert abs(last["torque"] - 0.5 * n) < 1e-9           # sign dropped, scaled up
    omega = 3000 * 2 * math.pi / 60
    assert abs(last["shaft_power"] - omega * 0.5 * n) < 1e-6
    assert abs(last["air_power"] - 200.0 * 0.6) < 1e-9
    assert abs(last["efficiency"] - (200.0 * 0.6) / (omega * 3.0)) < 1e-9
    assert abs(last["swirl"] - 5.0) < 1e-9


def test_fan_performance_is_empty_without_a_run(tmp_path):
    assert fan.performance(tmp_path, _spec())["latest"] is None


def test_efficiency_is_undefined_past_free_delivery(tmp_path):
    """Beyond free delivery dp0 goes negative while shaft power crosses zero;
    air/shaft is then a ratio of two things that no longer mean efficiency."""
    _write_series(tmp_path, "flowRate", [(100, "-0.1")])
    _write_series(tmp_path, "p0Inlet", [(100, "100")])
    _write_series(tmp_path, "p0Outlet", [(100, "-50")])      # a pressure drop
    _write_series(tmp_path, "outletU", [(100, "(0 1 12)")])
    moment = tmp_path / "postProcessing" / "bladeForces" / "0"
    moment.mkdir(parents=True)
    (moment / "moment.dat").write_text("# Time\ttotal\n100\t0 0 -0.001\n")

    last = fan.performance(tmp_path, _spec())["latest"]
    assert last["total_pressure_rise"] < 0
    assert last["efficiency"] is None
    # the raw powers are still reported — only the ratio is withheld
    assert last["air_power"] < 0 and last["shaft_power"] > 0
