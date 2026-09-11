"""Sweep fan-out: one axis (polar) and two axes (fan map), and the design pin.

Uses a throwaway SQLite database; no Docker and no solving — these check the
fan-out and aggregation, not the physics.
"""

import os
import tempfile

os.environ.setdefault("OFGUI_DATA_DIR", tempfile.mkdtemp(prefix="ofgui-sweeps-"))

import pytest  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.services import case_service, sweeps_service  # noqa: E402

init_db()


@pytest.fixture
def session():
    with Session(engine) as s:
        yield s


def _case(session, template):
    return case_service.create_case(session, f"base-{template}", template)


# --- fan-out --------------------------------------------------------------


def test_one_axis_makes_one_child_per_value(session):
    base = _case(session, "airfoil")
    sweep = sweeps_service.create_sweep(
        session, base.id, "physics.reference.angle_of_attack", [0, 4, 8], "AoA"
    )
    assert len(sweep.case_ids) == 3
    assert sweep.parameter2 is None
    assert [p["value"] for p in sweep.points] == [0, 4, 8]
    from app.models.case import Case

    aoas = [session.get(Case, cid).spec["physics"]["reference"]["angle_of_attack"]
            for cid in sweep.case_ids]
    assert aoas == [0, 4, 8]


def test_two_axes_make_the_cross_product(session):
    base = _case(session, "axial_fan")
    sweep = sweeps_service.create_sweep(
        session, base.id,
        "physics.reference.axial_velocity", [8, 12],
        "Fan map",
        parameter2="physics.reference.rpm", values2=[2400, 3000],
    )
    assert len(sweep.case_ids) == 4
    assert [(p["value"], p["value2"]) for p in sweep.points] == [
        (8, 2400), (8, 3000), (12, 2400), (12, 3000)
    ]
    assert sweep.domain == "turbo"


def test_second_parameter_without_values_is_rejected(session):
    base = _case(session, "axial_fan")
    with pytest.raises(ValueError):
        sweeps_service.create_sweep(
            session, base.id, "physics.reference.axial_velocity", [8],
            "bad", parameter2="physics.reference.rpm", values2=[],
        )


def test_empty_sweep_is_rejected(session):
    base = _case(session, "airfoil")
    with pytest.raises(ValueError):
        sweeps_service.create_sweep(session, base.id, "physics.reference.angle_of_attack", [], "x")


# --- the design pin -------------------------------------------------------


def test_map_pins_the_blade_to_the_base_operating_point(session):
    """Every point of a map must be the same fan, not a fan re-cut per point."""
    from app.models.case import Case

    base = _case(session, "axial_fan")
    base_rpm = base.spec["physics"]["reference"]["rpm"]
    base_va = base.spec["physics"]["reference"]["axial_velocity"]

    sweep = sweeps_service.create_sweep(
        session, base.id,
        "physics.reference.axial_velocity", [6, 12, 18],
        "Fan map",
        parameter2="physics.reference.rpm", values2=[2400, 3000],
    )
    for cid in sweep.case_ids:
        g = session.get(Case, cid).spec["geometry"]["parameters"]
        assert g["design_rpm"] == base_rpm
        assert g["design_axial_velocity"] == base_va


def test_pinning_never_overwrites_a_design_point_already_set():
    spec = {
        "geometry": {"parameters": {"design_rpm": 1800.0}},
        "physics": {"reference": {"rpm": 3000.0, "axial_velocity": 12.0}},
    }
    sweeps_service.pin_design_point(
        spec, ["physics.reference.rpm", "physics.reference.axial_velocity"]
    )
    assert spec["geometry"]["parameters"]["design_rpm"] == 1800.0        # kept
    assert spec["geometry"]["parameters"]["design_axial_velocity"] == 12.0  # filled in


def test_aero_sweeps_are_not_pinned(session):
    from app.models.case import Case

    base = _case(session, "airfoil")
    sweep = sweeps_service.create_sweep(
        session, base.id, "physics.reference.angle_of_attack", [0, 5], "AoA"
    )
    for cid in sweep.case_ids:
        assert "design_rpm" not in session.get(Case, cid).spec["geometry"]["parameters"]


def test_pinned_map_reuses_one_mesh_across_every_point(session):
    """The pin is only worth anything if it keeps the mesh signature fixed."""
    from app.models.case import Case
    from app.services.generators.axial_fan_case import (
        AxialFanParams,
        _mesh_signature,
        derive,
    )

    base = _case(session, "axial_fan")
    sweep = sweeps_service.create_sweep(
        session, base.id,
        "physics.reference.axial_velocity", [6, 12, 18],
        "Fan map",
        parameter2="physics.reference.rpm", values2=[2400, 3000],
    )
    signatures = set()
    for cid in sweep.case_ids:
        p = AxialFanParams.from_spec(session.get(Case, cid).spec)
        signatures.add(_mesh_signature(p, derive(p)))
    assert len(signatures) == 1

    # and without the pin, every point would be a different blade
    unpinned = set()
    for rpm in (2400, 3000):
        p = AxialFanParams.from_spec(base.spec)
        p.rpm = rpm
        unpinned.add(_mesh_signature(p, derive(p)))
    assert len(unpinned) == 2


# --- aggregation ----------------------------------------------------------


def test_results_report_the_axes_and_one_entry_per_child(session):
    base = _case(session, "axial_fan")
    sweep = sweeps_service.create_sweep(
        session, base.id,
        "physics.reference.axial_velocity", [8, 12],
        "Fan map",
        parameter2="physics.reference.rpm", values2=[3000],
    )
    out = sweeps_service.results(session, sweep.id)
    assert out["domain"] == "turbo"
    assert out["parameter2"] == "physics.reference.rpm"
    assert len(out["points"]) == 2
    # nothing has been solved, so the metrics are simply absent
    assert all("total_pressure_rise" not in p for p in out["points"])


def test_status_carries_both_axis_values(session):
    base = _case(session, "axial_fan")
    sweep = sweeps_service.create_sweep(
        session, base.id,
        "physics.reference.axial_velocity", [8],
        "Fan map",
        parameter2="physics.reference.rpm", values2=[2400, 3000],
    )
    st = sweeps_service.status(session, sweep.id)
    assert st["total"] == 2
    assert {c["value2"] for c in st["children"]} == {2400, 3000}
    assert all(c["status"] == "draft" for c in st["children"])
