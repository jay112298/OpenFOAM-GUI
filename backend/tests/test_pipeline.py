"""End-to-end pipeline tests that don't need Docker: generation + validation."""

import math

from app.services.generators.airfoil_case import build_case, derive, AirfoilParams
from app.services.geometry import naca
from app.services.physics.turbulence import turbulence_inlet
from app.services.meshing.yplus import first_cell_height
from app.services.validation.engine import preflight_report


def test_naca0012_thickness():
    af = naca.generate("0012", chord=1.0, n=120)
    assert abs(max(af.y) * 2 - 0.12) < 0.005   # 12% thick
    assert abs(af.y[0]) < 1e-6 and abs(af.y[-1]) < 1e-6  # closed TE


def test_turbulence_inlet_k():
    ti = turbulence_inlet(30, 0.05, 0.07)
    assert abs(ti.k - 1.5 * (30 * 0.05) ** 2) < 1e-9


def test_yplus_positive():
    est = first_cell_height(30, 1.0, 1.5e-5, 1.225, 1.0)
    assert est.first_cell_height > 0
    assert est.reynolds == 30 * 1.0 / 1.5e-5


def test_aoa_rotates_freestream():
    p = AirfoilParams(velocity=30, angle_of_attack=5)
    st = derive(p)
    assert abs(st.velocity_vector[0] - 30 * math.cos(math.radians(5))) < 1e-6
    assert abs(st.velocity_vector[1] - 30 * math.sin(math.radians(5))) < 1e-6


def test_build_case_writes_files(tmp_path):
    spec = {
        "geometry": {"parameters": {"designation": "0012", "chord": 1.0}},
        "physics": {"fluid": {"name": "air"}, "turbulence_model": "kOmegaSST",
                    "reference": {"velocity": 30, "angle_of_attack": 0, "turbulence_intensity": 0.01}},
        "mesh": {"parameters": {}},
        "numerics": {"solver": "simpleFoam"},
    }
    build_case(spec, tmp_path)
    for f in ["system/controlDict", "system/fvSchemes", "system/fvSolution",
              "airfoil.msh",
              "constant/transportProperties", "constant/turbulenceProperties",
              "constant/triSurface/airfoil.stl", "0/U", "0/p", "0/k", "0/omega", "0/nut",
              "Allrun"]:
        assert (tmp_path / f).exists(), f"missing {f}"


def test_validation_blocks_transonic_incompressible():
    spec = {
        "geometry": {"parameters": {"designation": "0012", "chord": 1.0}},
        "physics": {"fluid": {"name": "air"}, "turbulence_model": "kOmegaSST",
                    "reference": {"velocity": 150, "angle_of_attack": 0, "turbulence_intensity": 0.01}},
        "mesh": {"parameters": {}},
        "numerics": {"solver": "simpleFoam"},
    }
    report = preflight_report(spec)
    assert report["can_run"] is False
    assert any(f["rule_id"] == "mach-regime" and f["severity"] == "fail" for f in report["findings"])


def test_validation_passes_good_case():
    spec = {
        "geometry": {"parameters": {"designation": "0012", "chord": 1.0}},
        "physics": {"fluid": {"name": "air"}, "turbulence_model": "kOmegaSST",
                    "reference": {"velocity": 30, "angle_of_attack": 5, "turbulence_intensity": 0.01}},
        "mesh": {"parameters": {"target_yplus": 30}},
        "numerics": {"solver": "simpleFoam"},
    }
    report = preflight_report(spec)
    assert report["can_run"] is True
