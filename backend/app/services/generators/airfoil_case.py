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
from app.services.physics.turbulence import TRANSITION_MODELS, re_theta_t, turbulence_inlet

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
    # mesh (Gmsh 2D C-mesh; optional snappy prism layers)
    # Far-field distance is the dominant drag-accuracy lever: 15c gives Cd~0.024,
    # 50c gives Cd~0.012 (correct for fully-turbulent RANS). Default large.
    farfield_radius: float = 50.0   # far-field radius in chords
    boundary_layers: bool = False   # opt-in prism layers (snappy addLayers); see ROADMAP
    n_layers: int = 15
    layer_expansion: float = 1.2
    target_yplus: float = 30.0      # wall-function band for the default (no-layer) mesh
    span: float = 0.05              # 2D span thickness [m]
    # numerics
    end_time: int = 2000
    write_interval: int = 200
    n_procs: int = 1                # parallel cores (1 = serial)

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
        out.farfield_radius = m.get("farfield_radius", out.farfield_radius)
        out.boundary_layers = m.get("boundary_layers", out.boundary_layers)
        out.n_layers = m.get("n_layers", out.n_layers)
        out.layer_expansion = m.get("layer_expansion", out.layer_expansion)
        out.target_yplus = m.get("target_yplus", out.target_yplus)
        out.span = m.get("span", out.span)
        out.end_time = n.get("end_time", out.end_time)
        out.write_interval = n.get("write_interval", out.write_interval)
        out.n_procs = n.get("n_procs", out.n_procs)
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
    mesh_reused: bool = False  # True when an up-to-date mesh was kept


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


def _mesh_signature(p: AirfoilParams, st: DerivedState) -> str:
    """Hash of everything that changes the Gmsh mesh. Physics changes that only
    touch fields/dicts don't invalidate the (slow) mesh."""
    import hashlib
    import json

    key = {
        "designation": p.designation,
        "chord": p.chord,
        "farfield_radius": p.farfield_radius,
        "span": p.span,
        # surface cell size + fitted layer count define the mesh
        "wall_cell": float(f"{wall_cell_size(p, st):.3g}"),
        "n_layers": fitted_n_layers(p, st),
    }
    return hashlib.sha1(json.dumps(key, sort_keys=True).encode()).hexdigest()


def build_case(spec: dict, case_dir: Path, force_mesh: bool = True) -> DerivedState:
    """Write a complete OpenFOAM case for `spec` into `case_dir`. Returns derived state.

    With force_mesh=False an existing mesh is reused when its signature matches
    (so Run doesn't redo a 50 s Gmsh job the Mesh tab just did).
    """
    params = AirfoilParams.from_spec(spec)
    st = derive(params)

    for sub in ("system", "constant/triSurface", "0"):
        (case_dir / sub).mkdir(parents=True, exist_ok=True)

    # --- geometry + clean 2D Gmsh mesh (reused when unchanged) ---
    airfoil = naca.generate(params.designation, params.chord, n=200)
    naca.export_stl(airfoil, case_dir / "constant/triSurface/airfoil.stl", span=params.span)
    sig = _mesh_signature(params, st)
    sig_file = case_dir / "airfoil.sig"
    reuse = (
        not force_mesh
        and (case_dir / "airfoil.msh").exists()
        and sig_file.exists()
        and sig_file.read_text().strip() == sig
    )
    if not reuse:
        _write_mesh(case_dir, params, st, airfoil)
        sig_file.write_text(sig)
    st.mesh_reused = reuse
    if params.boundary_layers:
        _write_snappy_layers(case_dir, params, st)

    _write_control_dict(case_dir, params, st)
    _write_fv_schemes(case_dir)
    _write_fv_solution(case_dir)
    _write_transport(case_dir, st)
    _write_turbulence(case_dir, params)
    _write_fields(case_dir, params, st)
    if params.n_procs > 1:
        _write_decompose_par(case_dir, params)
    _write_allrun(case_dir, params)
    return st


def layer_stack_thickness(p: AirfoilParams, first_layer: float) -> float:
    """Total thickness of the prism stack: first * (r^n - 1) / (r - 1)."""
    r = p.layer_expansion
    if abs(r - 1.0) < 1e-9:
        return first_layer * p.n_layers
    return first_layer * (r**p.n_layers - 1) / (r - 1)


def wall_cell_size(p: AirfoilParams, st: DerivedState) -> float:
    """Target Gmsh cell size at the airfoil surface.

    Kept at a resolution-driven size in both cases. Cells here are isotropic, so
    this also sets the *streamwise* surface resolution — coarsening it to make
    room for prism layers costs more accuracy (pressure distribution) than the
    layers win back. With layers we instead cap their count to fit (see
    `fitted_n_layers`).
    """
    if p.boundary_layers:
        return p.chord / 800.0
    return max(st.first_cell_height, p.chord / 800.0)


def fitted_n_layers(p: AirfoilParams, st: DerivedState) -> int:
    """Largest layer count whose stack still fits inside one surface cell.

    snappy carves the prism stack out of the existing wall cell; if the stack is
    thicker than that cell it silently adds ~0 layers (seen as 0% coverage).
    Capping the count keeps a fine surface mesh *and* a resolved wall.
    """
    if not p.boundary_layers:
        return p.n_layers
    budget = 0.8 * wall_cell_size(p, st)
    first, r = st.first_cell_height, p.layer_expansion
    n = 0
    while n < p.n_layers:
        nxt = n + 1
        stack = first * nxt if abs(r - 1) < 1e-9 else first * (r**nxt - 1) / (r - 1)
        if stack > budget:
            break
        n = nxt
    return max(n, 1)


def _write_mesh(case_dir: Path, p: AirfoilParams, st: DerivedState, airfoil: naca.Airfoil) -> None:
    """Generate a clean 2D Gmsh C-mesh (.msh) -> converted by gmshToFoam in Allrun."""
    from app.services.meshing.gmsh_airfoil import build_mesh

    build_mesh(
        airfoil.coordinates,
        chord=p.chord,
        wall_cell=wall_cell_size(p, st),
        farfield_radius=p.farfield_radius,
        span=p.span,
        out_path=case_dir / "airfoil.msh",
    )


def _write_snappy_layers(case_dir: Path, p: AirfoilParams, st: DerivedState) -> None:
    """Layer-only snappyHexMesh: adds prism layers to the `airfoil` wall of the
    already-clean Gmsh mesh (no castellation/snapping). firstLayerThickness is
    the y+-target first-cell height for a resolved boundary layer.
    """
    f = FoamFile(case_dir / "system/snappyHexMeshDict")
    f["castellatedMesh"] = False
    f["snap"] = False
    f["addLayers"] = True
    f["geometry"] = {}
    f["castellatedMeshControls"] = {
        "maxLocalCells": 1000000, "maxGlobalCells": 4000000, "minRefinementCells": 0,
        "nCellsBetweenLevels": 1, "features": [], "refinementSurfaces": {},
        "resolveFeatureAngle": 30, "refinementRegions": {},
        "locationInMesh": [p.farfield_radius * p.chord * 0.5, p.farfield_radius * p.chord * 0.5, p.span * 0.5],
        "allowFreeStandingZoneFaces": True,
    }
    f["snapControls"] = {"nSmoothPatch": 3, "tolerance": 2.0, "nSolveIter": 30, "nRelaxIter": 5}
    f["addLayersControls"] = {
        "relativeSizes": False,
        "layers": {"airfoil": {"nSurfaceLayers": fitted_n_layers(p, st)}},
        "expansionRatio": p.layer_expansion,
        "firstLayerThickness": st.first_cell_height,
        "minThickness": st.first_cell_height * 0.1,
        "nGrow": 0, "featureAngle": 130, "nRelaxIter": 5,
        "nSmoothSurfaceNormals": 1, "nSmoothNormals": 3, "nSmoothThickness": 10,
        "maxFaceThicknessRatio": 0.5, "maxThicknessToMedialRatio": 0.3,
        "minMedialAxisAngle": 90, "nBufferCellsNoExtrude": 0, "nLayerIter": 50,
    }
    f["meshQualityControls"] = {
        "maxNonOrtho": 65, "maxBoundarySkewness": 20, "maxInternalSkewness": 4,
        "maxConcave": 80, "minVol": 1e-13, "minTetQuality": -1e30, "minArea": -1,
        "minTwist": 0.02, "minDeterminant": 0.001, "minFaceWeight": 0.05,
        "minVolRatio": 0.01, "minTriangleTwist": -1, "nSmoothScale": 4, "errorReduction": 0.75,
    }
    f["mergeTolerance"] = 1e-6


def _write_decompose_par(case_dir: Path, p: AirfoilParams) -> None:
    f = FoamFile(case_dir / "system/decomposeParDict")
    f["numberOfSubdomains"] = p.n_procs
    f["method"] = "scotch"


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
            "Aref": p.chord * p.span,
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
        # transition model (kOmegaSSTLM) transport equations
        "div(phi,gammaInt)": "bounded Gauss upwind",
        "div(phi,ReThetat)": "bounded Gauss upwind",
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
        '"(U|k|omega|epsilon|gammaInt|ReThetat)"': {
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
        "equations": {"U": 0.7, '"(k|omega|epsilon|gammaInt|ReThetat)"': 0.7},
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
        # Spalding wall function is continuous across y+ (valid for the resolved
        # y+~1 boundary layers as well as coarse wall-function meshes).
        "airfoil": {"type": "nutUSpaldingWallFunction", "value": 0.0},
        "frontAndBack": {"type": "empty"},
    }

    # kOmegaSSTLM (Langtry-Menter) solves two extra transport equations.
    if p.turbulence_model in TRANSITION_MODELS:
        rtt = re_theta_t(p.turbulence_intensity)

        fg = FoamFieldFile(case_dir / "0/gammaInt")
        fg.dimensions = [0, 0, 0, 0, 0, 0, 0]
        fg.internal_field = 1.0
        fg.boundary_field = {
            "farfield": {"type": "inletOutlet", "inletValue": 1.0, "value": 1.0},
            "airfoil": {"type": "zeroGradient"},
            "frontAndBack": {"type": "empty"},
        }

        fr = FoamFieldFile(case_dir / "0/ReThetat")
        fr.dimensions = [0, 0, 0, 0, 0, 0, 0]
        fr.internal_field = rtt
        fr.boundary_field = {
            "farfield": {"type": "inletOutlet", "inletValue": rtt, "value": rtt},
            "airfoil": {"type": "zeroGradient"},
            "frontAndBack": {"type": "empty"},
        }


def _write_allrun(case_dir: Path, p: AirfoilParams) -> None:
    """Allrun that streams every stage to stdout (via tee) so the GUI terminal
    shows live mesh + solver output, with optional parallel solve."""
    n = p.n_procs
    if n > 1:
        solve = (
            f'decomposePar 2>&1 | tee log.decomposePar\n'
            f'mpirun --allow-run-as-root -np {n} simpleFoam -parallel 2>&1 | tee log.simpleFoam\n'
            f'reconstructPar -latestTime 2>&1 | tee log.reconstructPar\n'
        )
    else:
        solve = "simpleFoam 2>&1 | tee log.simpleFoam\n"

    total = 6 if p.boundary_layers else 5
    layers_step = ""
    if p.boundary_layers:
        layers_step = (
            f'\necho "[4/{total}] snappyHexMesh — adding {p.n_layers} prism layers"\n'
            "snappyHexMesh -overwrite 2>&1 | tee log.snappy\n"
        )
    check_i, renum_i, solve_i = (3, 5, 6) if p.boundary_layers else (3, 4, 5)

    script = f"""#!/bin/sh
cd "${{0%/*}}" || exit
. "${{WM_PROJECT_DIR:?}}/bin/tools/RunFunctions"
set -e

echo "============================================================"
echo " OpenFOAM GUI :: airfoil case"
echo " cores: {n}   turbulence: {p.turbulence_model}   AoA: {p.angle_of_attack} deg"
echo "============================================================"

echo "[1/{total}] gmshToFoam — importing 2D mesh"
gmshToFoam airfoil.msh 2>&1 | tee log.gmshToFoam

echo "[2/{total}] setting patch types (airfoil=wall, farfield=patch, frontAndBack=empty)"
foamDictionary constant/polyMesh/boundary -entry entry0/airfoil/type -set wall
foamDictionary constant/polyMesh/boundary -entry entry0/airfoil/inGroups -set '1(wall)'
foamDictionary constant/polyMesh/boundary -entry entry0/farfield/type -set patch
foamDictionary constant/polyMesh/boundary -entry entry0/frontAndBack/type -set empty
{layers_step}
echo "[{check_i}/{total}] checkMesh"
checkMesh -allGeometry -allTopology 2>&1 | tee log.checkMesh

echo "[{renum_i}/{total}] renumberMesh"
renumberMesh -overwrite 2>&1 | tee log.renumberMesh

echo "[{solve_i}/{total}] simpleFoam"
{solve}
echo "DONE"
"""
    path = case_dir / "Allrun"
    path.write_text(script)
    path.chmod(0o755)
