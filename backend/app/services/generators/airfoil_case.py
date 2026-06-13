"""Generate a complete 2D external-aerodynamics OpenFOAM case for an airfoil.

Setup (robust standard RANS external aero):
- blockMesh builds a rectangular far-field background domain, 2D (1 cell in z,
  empty front/back).
- snappyHexMesh carves the airfoil from an STL and adds the `airfoil` wall patch
  with boundary layers.
- Angle of attack is applied by rotating the freestream velocity vector, not the
  mesh — so sweeps reuse the same mesh.
- `freestream` / `freestreamPressure` BCs on the outer `farfield` patch adapt to
  in/outflow automatically (correct at any AoA).
- Turbulence inlet values are computed (never hand-typed).

Everything here is strict SI.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from foamlib import FoamFieldFile, FoamFile

from app.services.geometry import naca
from app.services.meshing.yplus import first_cell_height
from app.services.physics.fluids import get_fluid
from app.services.physics.turbulence import turbulence_inlet

# foamlib warns when it normalizes scheme strings to tokens / on-off to bool;
# the written OpenFOAM output is correct, so silence the noise.
warnings.filterwarnings("ignore", category=UserWarning, module="foamlib")


@dataclass
class AirfoilParams:
    designation: str = "0012"
    chord: float = 1.0
    velocity: float = 30.0          # freestream speed [m/s]
    angle_of_attack: float = 0.0    # degrees
    fluid: str = "air"
    turbulence_model: str = "kOmegaSST"
    turbulence_intensity: float = 0.05
    # domain extent in chord lengths
    upstream: float = 10.0
    downstream: float = 20.0
    vertical: float = 10.0
    # mesh
    base_cell: float = 0.5          # background cell size [m]
    surface_refine: int = 5         # snappy surface refinement level
    n_layers: int = 8
    target_yplus: float = 30.0      # wall-function band
    # numerics
    end_time: int = 2000
    write_interval: int = 200

    @classmethod
    def from_spec(cls, spec: dict) -> "AirfoilParams":
        g = spec.get("geometry", {}).get("parameters", {})
        p = spec.get("physics", {})
        ref = p.get("reference", {})
        m = spec.get("mesh", {}).get("parameters", {})
        n = spec.get("numerics", {})
        out = cls()
        out.designation = g.get("designation", out.designation)
        out.chord = g.get("chord", out.chord)
        out.velocity = ref.get("velocity", out.velocity)
        out.angle_of_attack = ref.get("angle_of_attack", out.angle_of_attack)
        out.fluid = p.get("fluid", {}).get("name", out.fluid)
        out.turbulence_model = p.get("turbulence_model", out.turbulence_model)
        out.turbulence_intensity = ref.get("turbulence_intensity", out.turbulence_intensity)
        out.upstream = m.get("upstream", out.upstream)
        out.downstream = m.get("downstream", out.downstream)
        out.vertical = m.get("vertical", out.vertical)
        out.base_cell = m.get("base_cell", out.base_cell)
        out.surface_refine = m.get("surface_refine", out.surface_refine)
        out.n_layers = m.get("n_layers", out.n_layers)
        out.target_yplus = m.get("target_yplus", out.target_yplus)
        out.end_time = n.get("end_time", out.end_time)
        out.write_interval = n.get("write_interval", out.write_interval)
        return out


@dataclass
class DerivedState:
    """Computed quantities a case + the validation engine both need."""

    velocity_vector: tuple[float, float, float]
    reynolds: float
    mach: float
    k: float
    omega: float
    nu: float
    first_cell_height: float
    params: AirfoilParams = field(repr=False, default=None)  # type: ignore


def derive(params: AirfoilParams) -> DerivedState:
    fluid = get_fluid(params.fluid)
    aoa = math.radians(params.angle_of_attack)
    u = params.velocity
    vec = (u * math.cos(aoa), u * math.sin(aoa), 0.0)
    re = u * params.chord / fluid.nu
    ma = u / fluid.a
    length_scale = 0.07 * params.chord
    ti = turbulence_inlet(u, params.turbulence_intensity, length_scale)
    fch = first_cell_height(u, params.chord, fluid.nu, fluid.rho, params.target_yplus)
    return DerivedState(
        velocity_vector=vec,
        reynolds=re,
        mach=ma,
        k=ti.k,
        omega=ti.omega,
        nu=fluid.nu,
        first_cell_height=fch.first_cell_height,
        params=params,
    )


def _header(path: Path, class_: str, object_: str, location: str) -> FoamFile:
    f = FoamFile(path)
    return f


def build_case(spec: dict, case_dir: Path) -> DerivedState:
    """Write a complete OpenFOAM case for `spec` into `case_dir`. Returns derived state."""
    params = AirfoilParams.from_spec(spec)
    st = derive(params)

    for sub in ("system", "constant/triSurface", "0"):
        (case_dir / sub).mkdir(parents=True, exist_ok=True)

    # --- geometry STL ---
    airfoil = naca.generate(params.designation, params.chord)
    naca.export_stl(airfoil, case_dir / "constant/triSurface/airfoil.stl", span=params.base_cell)

    _write_block_mesh(case_dir, params, airfoil)
    _write_snappy(case_dir, params)
    _write_control_dict(case_dir, params, st)
    _write_fv_schemes(case_dir)
    _write_fv_solution(case_dir)
    _write_transport(case_dir, st)
    _write_turbulence(case_dir, params)
    _write_fields(case_dir, params, st)
    _write_allrun(case_dir)
    return st


def _write_block_mesh(case_dir: Path, p: AirfoilParams, airfoil: naca.Airfoil) -> None:
    c = p.chord
    x0, x1 = -p.upstream * c, p.downstream * c
    y0, y1 = -p.vertical * c, p.vertical * c
    z0, z1 = 0.0, p.base_cell  # thin span (2D)

    nx = max(int((x1 - x0) / p.base_cell), 20)
    ny = max(int((y1 - y0) / p.base_cell), 20)

    f = FoamFile(case_dir / "system/blockMeshDict")
    f["scale"] = 1
    f["vertices"] = [
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ]
    f["blocks"] = [
        "hex", [0, 1, 2, 3, 4, 5, 6, 7], [nx, ny, 1], "simpleGrading", [1, 1, 1]
    ]
    f["edges"] = []
    f["boundary"] = [
        ("farfield", {"type": "patch", "faces": [
            [0, 4, 7, 3],  # left
            [1, 2, 6, 5],  # right
            [3, 7, 6, 2],  # top
            [0, 1, 5, 4],  # bottom
        ]}),
        ("frontAndBack", {"type": "empty", "faces": [
            [0, 3, 2, 1],  # back (z0)
            [4, 5, 6, 7],  # front (z1)
        ]}),
    ]
    f["mergePatchPairs"] = []


def _write_snappy(case_dir: Path, p: AirfoilParams) -> None:
    f = FoamFile(case_dir / "system/snappyHexMeshDict")
    f["castellatedMesh"] = True
    f["snap"] = True
    f["addLayers"] = True
    f["geometry"] = {
        "airfoil.stl": {"type": "triSurfaceMesh", "name": "airfoil"}
    }
    f["castellatedMeshControls"] = {
        "maxLocalCells": 1000000,
        "maxGlobalCells": 4000000,
        "minRefinementCells": 10,
        "nCellsBetweenLevels": 3,
        "features": [],
        "refinementSurfaces": {
            "airfoil": {"level": [p.surface_refine, p.surface_refine], "patchInfo": {"type": "wall"}}
        },
        "resolveFeatureAngle": 30,
        "refinementRegions": {},
        "locationInMesh": [-p.upstream * p.chord * 0.5, p.vertical * p.chord * 0.5, p.base_cell * 0.5],
        "allowFreeStandingZoneFaces": True,
    }
    f["snapControls"] = {
        "nSmoothPatch": 3, "tolerance": 2.0, "nSolveIter": 50, "nRelaxIter": 5,
        "nFeatureSnapIter": 10, "implicitFeatureSnap": True, "explicitFeatureSnap": False,
    }
    f["addLayersControls"] = {
        "relativeSizes": True,
        "layers": {"airfoil": {"nSurfaceLayers": p.n_layers}},
        "expansionRatio": 1.2,
        "finalLayerThickness": 0.5,
        "minThickness": 0.05,
        "nGrow": 0, "featureAngle": 60, "nRelaxIter": 5,
        "nSmoothSurfaceNormals": 1, "nSmoothNormals": 3, "nSmoothThickness": 10,
        "maxFaceThicknessRatio": 0.5, "maxThicknessToMedialRatio": 0.3,
        "minMedialAxisAngle": 90, "nBufferCellsNoExtrude": 0,
        "nLayerIter": 50,
    }
    f["meshQualityControls"] = {
        "maxNonOrtho": 65, "maxBoundarySkewness": 20, "maxInternalSkewness": 4,
        "maxConcave": 80, "minVol": 1e-13, "minTetQuality": 1e-15, "minArea": -1,
        "minTwist": 0.02, "minDeterminant": 0.001, "minFaceWeight": 0.05,
        "minVolRatio": 0.01, "minTriangleTwist": -1, "nSmoothScale": 4,
        "errorReduction": 0.75,
    }
    f["mergeTolerance"] = 1e-6


def _write_control_dict(case_dir: Path, p: AirfoilParams, st: DerivedState) -> None:
    rho = get_fluid(p.fluid).rho
    f = FoamFile(case_dir / "system/controlDict")
    f["application"] = "simpleFoam"
    f["startFrom"] = "startTime"
    f["startTime"] = 0
    f["stopAt"] = "endTime"
    f["endTime"] = p.end_time
    f["deltaT"] = 1
    f["writeControl"] = "timeStep"
    f["writeInterval"] = p.write_interval
    f["purgeWrite"] = 0
    f["writeFormat"] = "ascii"
    f["writePrecision"] = 8
    f["writeCompression"] = "off"
    f["timeFormat"] = "general"
    f["timePrecision"] = 6
    f["runTimeModifiable"] = True
    # force coefficients function object (lift/drag)
    aoa = p.angle_of_attack
    f["functions"] = {
        "forceCoeffs": {
            "type": "forceCoeffs",
            "libs": ["forces"],
            "writeControl": "timeStep",
            "writeInterval": 1,
            "patches": ["airfoil"],
            "rho": "rhoInf",
            "rhoInf": rho,
            "liftDir": [-math.sin(math.radians(aoa)), math.cos(math.radians(aoa)), 0],
            "dragDir": [math.cos(math.radians(aoa)), math.sin(math.radians(aoa)), 0],
            "CofR": [0.25 * p.chord, 0, 0],
            "pitchAxis": [0, 0, 1],
            "magUInf": p.velocity,
            "lRef": p.chord,
            "Aref": p.chord * p.base_cell,
        }
    }


def _write_fv_schemes(case_dir: Path) -> None:
    f = FoamFile(case_dir / "system/fvSchemes")
    f["ddtSchemes"] = {"default": "steadyState"}
    f["gradSchemes"] = {"default": "Gauss linear"}
    f["divSchemes"] = {
        "default": "none",
        "div(phi,U)": "bounded Gauss linearUpwind grad(U)",
        "div(phi,k)": "bounded Gauss upwind",
        "div(phi,omega)": "bounded Gauss upwind",
        "div(phi,epsilon)": "bounded Gauss upwind",
        "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
    }
    f["laplacianSchemes"] = {"default": "Gauss linear corrected"}
    f["interpolationSchemes"] = {"default": "linear"}
    f["snGradSchemes"] = {"default": "corrected"}
    f["wallDist"] = {"method": "meshWave"}


def _write_fv_solution(case_dir: Path) -> None:
    f = FoamFile(case_dir / "system/fvSolution")
    f["solvers"] = {
        "p": {"solver": "GAMG", "tolerance": 1e-6, "relTol": 0.1, "smoother": "GaussSeidel"},
        '"(U|k|omega|epsilon)"': {
            "solver": "smoothSolver", "smoother": "symGaussSeidel",
            "tolerance": 1e-6, "relTol": 0.1,
        },
    }
    f["SIMPLE"] = {
        "nNonOrthogonalCorrectors": 0,
        "consistent": True,
        "residualControl": {"p": 1e-4, "U": 1e-4, '"(k|omega|epsilon)"': 1e-4},
    }
    f["relaxationFactors"] = {
        "fields": {"p": 0.3},
        "equations": {"U": 0.7, '"(k|omega|epsilon)"': 0.7},
    }


def _write_transport(case_dir: Path, st: DerivedState) -> None:
    f = FoamFile(case_dir / "constant/transportProperties")
    f["transportModel"] = "Newtonian"
    f["nu"] = st.nu


def _write_turbulence(case_dir: Path, p: AirfoilParams) -> None:
    f = FoamFile(case_dir / "constant/turbulenceProperties")
    f["simulationType"] = "RAS"
    f["RAS"] = {"RASModel": p.turbulence_model, "turbulence": "on", "printCoeffs": "on"}


def _write_fields(case_dir: Path, p: AirfoilParams, st: DerivedState) -> None:
    u = st.velocity_vector

    fU = FoamFieldFile(case_dir / "0/U")
    fU.dimensions = [0, 1, -1, 0, 0, 0, 0]
    fU.internal_field = list(u)
    fU.boundary_field = {
        "farfield": {"type": "freestream", "freestreamValue": list(u)},
        "airfoil": {"type": "noSlip"},
        "frontAndBack": {"type": "empty"},
    }

    fp = FoamFieldFile(case_dir / "0/p")
    fp.dimensions = [0, 2, -2, 0, 0, 0, 0]
    fp.internal_field = 0.0
    fp.boundary_field = {
        "farfield": {"type": "freestreamPressure", "freestreamValue": 0.0},
        "airfoil": {"type": "zeroGradient"},
        "frontAndBack": {"type": "empty"},
    }

    fk = FoamFieldFile(case_dir / "0/k")
    fk.dimensions = [0, 2, -2, 0, 0, 0, 0]
    fk.internal_field = st.k
    fk.boundary_field = {
        "farfield": {"type": "inletOutlet", "inletValue": st.k, "value": st.k},
        "airfoil": {"type": "kqRWallFunction", "value": st.k},
        "frontAndBack": {"type": "empty"},
    }

    fo = FoamFieldFile(case_dir / "0/omega")
    fo.dimensions = [0, 0, -1, 0, 0, 0, 0]
    fo.internal_field = st.omega
    fo.boundary_field = {
        "farfield": {"type": "inletOutlet", "inletValue": st.omega, "value": st.omega},
        "airfoil": {"type": "omegaWallFunction", "value": st.omega},
        "frontAndBack": {"type": "empty"},
    }

    fn = FoamFieldFile(case_dir / "0/nut")
    fn.dimensions = [0, 2, -1, 0, 0, 0, 0]
    fn.internal_field = 0.0
    fn.boundary_field = {
        "farfield": {"type": "calculated", "value": 0.0},
        "airfoil": {"type": "nutkWallFunction", "value": 0.0},
        "frontAndBack": {"type": "empty"},
    }


def _write_allrun(case_dir: Path) -> None:
    script = """#!/bin/sh
cd "${0%/*}" || exit
. "${WM_PROJECT_DIR:?}/bin/tools/RunFunctions"

runApplication blockMesh
runApplication snappyHexMesh -overwrite
runApplication checkMesh -allTopology -allGeometry
runApplication renumberMesh -overwrite
runApplication simpleFoam
"""
    path = case_dir / "Allrun"
    path.write_text(script)
    path.chmod(0o755)
