"""Generate a complete single-passage axial fan / compressor rotor case (MRF).

The machine is solved as **one blade passage** instead of the whole annulus:

- `blockMesh` lays down an annular sector of width 360/n_blades, with the two
  cut faces as rotationally-transformed `cyclicAMI` patches. One passage is
  1/n_blades of the work, so a 6-bladed fan costs a sixth of the cells.
- `snappyHexMesh` carves the blade out of that sector from an STL. The blade is
  written three times (at -pitch, 0, +pitch) so a blade that reaches across the
  periodic plane still cuts both sides identically.
- `topoSet` makes every cell a `rotor` cellZone and `MRFProperties` spins that
  zone at the shaft speed (Multiple Reference Frame): the mesh never moves, the
  momentum equation gains the Coriolis and centrifugal terms, and the steady
  solver stays steady. Rotating walls (blade, hub) get their real absolute
  velocity from `rotatingWallVelocity`; the casing stays stationary and is
  listed as a `nonRotatingPatches` entry.

Blade twist is derived from the velocity triangle (see geometry/blade.py), and
the function objects record everything a fan curve needs: flow rate, total
pressure rise and shaft torque.

Everything here is strict SI. Rotation is about +z; flow runs inlet -> outlet
along +z.
"""

from __future__ import annotations

import hashlib
import json
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from foamlib import FoamFieldFile, FoamFile

from app.services.geometry import blade as blade_geom
from app.services.geometry.blade import BladeSection, BladeSpec
from app.services.meshing.yplus import first_cell_height
from app.services.physics.fluids import get_fluid
from app.services.physics.turbulence import turbulence_inlet

warnings.filterwarnings("ignore", category=UserWarning, module="foamlib")

MESH_LOG = "log.mesh"
_SIG_FILE = "passage.sig"
_PATCHES = ("inlet", "outlet", "hub", "shroud", "blade", "periodic1", "periodic2")
_WALLS = ("hub", "shroud", "blade")
# walls that turn with the shaft (the casing does not)
_ROTATING_WALLS = ("hub", "blade")


@dataclass
class AxialFanParams:
    # geometry
    designation: str = "4412"
    n_blades: int = 6
    hub_radius: float = 0.06
    tip_radius: float = 0.15
    chord: float = 0.05
    incidence: float = 4.0
    # operating point
    rpm: float = 3000.0
    axial_velocity: float = 12.0
    fluid: str = "air"
    turbulence_model: str = "kOmegaSST"
    turbulence_intensity: float = 0.05   # 5% — internal machine, not free air
    # mesh
    cells_per_chord: int = 8             # background cell size = chord / this
    refinement_level: int = 2            # snappy surface refinement on the blade
    inlet_length: float = 2.0            # chords upstream of the blade
    outlet_length: float = 4.0           # chords downstream
    boundary_layers: bool = False
    n_layers: int = 8
    layer_expansion: float = 1.2
    target_yplus: float = 50.0
    # numerics
    end_time: int = 1500
    write_interval: int = 250
    n_procs: int = 1

    @classmethod
    def from_spec(cls, spec: dict) -> "AxialFanParams":
        g = spec.get("geometry", {}).get("parameters", {})
        p = spec.get("physics", {})
        ref = p.get("reference", {})
        m = spec.get("mesh", {}).get("parameters", {})
        n = spec.get("numerics", {})
        out = cls()
        for key in ("designation", "n_blades", "hub_radius", "tip_radius", "chord", "incidence"):
            setattr(out, key, g.get(key, getattr(out, key)))
        for key in ("rpm", "axial_velocity", "turbulence_intensity"):
            setattr(out, key, ref.get(key, getattr(out, key)))
        out.fluid = p.get("fluid", {}).get("name", out.fluid)
        out.turbulence_model = p.get("turbulence_model", out.turbulence_model)
        for key in ("cells_per_chord", "refinement_level", "inlet_length", "outlet_length",
                    "boundary_layers", "n_layers", "layer_expansion", "target_yplus"):
            setattr(out, key, m.get(key, getattr(out, key)))
        for key in ("end_time", "write_interval", "n_procs"):
            setattr(out, key, n.get(key, getattr(out, key)))
        return out

    def blade_spec(self) -> BladeSpec:
        return BladeSpec(
            designation=self.designation,
            n_blades=int(self.n_blades),
            hub_radius=self.hub_radius,
            tip_radius=self.tip_radius,
            chord=self.chord,
            rpm=self.rpm,
            axial_velocity=self.axial_velocity,
            incidence=self.incidence,
        )


@dataclass
class FanState:
    """Everything the case, the GUI and the validation rules read."""

    blade: BladeSpec
    sections: list[BladeSection]
    shaft_omega: float          # [rad/s]
    tip_speed: float            # [m/s]
    tip_mach: float             # relative Mach at the tip
    reynolds: float             # chord Reynolds on the mid-span relative velocity
    k: float
    omega: float                # turbulence specific dissipation rate
    nu: float
    density: float
    first_cell_height: float
    volumetric_flow: float      # design Q for the whole machine [m^3/s]
    solver: str = "simpleFoam"
    params: AxialFanParams = field(repr=False, default=None)  # type: ignore[assignment]
    mesh_reused: bool = False
    n_cells: int | None = None


def derive(params: AxialFanParams) -> FanState:
    spec = params.blade_spec()
    fluid = get_fluid(params.fluid)
    mid = blade_geom.section_at(spec, spec.mean_radius)
    tip = blade_geom.section_at(spec, spec.tip_radius)

    ti = turbulence_inlet(mid.relative_speed, params.turbulence_intensity, 0.07 * params.chord)
    fch = first_cell_height(
        mid.relative_speed, params.chord, fluid.nu, fluid.rho, params.target_yplus
    )
    annulus = math.pi * (spec.tip_radius**2 - spec.hub_radius**2)
    return FanState(
        blade=spec,
        sections=blade_geom.sections(spec),
        shaft_omega=spec.omega,
        tip_speed=spec.tip_speed,
        tip_mach=tip.relative_speed / fluid.a,
        reynolds=mid.relative_speed * params.chord / fluid.nu,
        k=ti.k,
        omega=ti.omega,
        nu=fluid.nu,
        density=fluid.rho,
        first_cell_height=fch.first_cell_height,
        volumetric_flow=annulus * params.axial_velocity,
        params=params,
    )


# --------------------------------------------------------------------------
# geometry of the background sector


@dataclass
class _Sector:
    """The annular sector blockMesh lays down, in one place."""

    r_hub: float
    r_tip: float
    half_angle: float
    z_in: float
    z_out: float
    n_r: int
    n_t: int
    n_z: int

    @property
    def base_cell(self) -> float:
        return (self.r_tip - self.r_hub) / self.n_r


def _sector(p: AxialFanParams) -> _Sector:
    spec = p.blade_spec()
    base = p.chord / max(2, int(p.cells_per_chord))
    span = spec.span
    pitch = 2 * math.pi * spec.mean_radius / spec.n_blades
    z_in, z_out = -p.inlet_length * p.chord, p.outlet_length * p.chord
    return _Sector(
        r_hub=spec.hub_radius,
        r_tip=spec.tip_radius,
        half_angle=spec.sector_angle / 2,
        z_in=z_in,
        z_out=z_out,
        n_r=max(6, round(span / base)),
        n_t=max(6, round(pitch / base)),
        n_z=max(10, round((z_out - z_in) / base)),
    )


def _cyl(r: float, theta: float, z: float) -> list[float]:
    return [r * math.cos(theta), r * math.sin(theta), z]


def _mesh_signature(p: AxialFanParams, st: FanState) -> str:
    """Anything that changes the mesh. Note the operating point is in here:
    rpm and through-flow set the blade twist, so they are geometry."""
    s = _sector(p)
    key = {
        "blade": [p.designation, p.n_blades, p.hub_radius, p.tip_radius, p.chord, p.incidence],
        "twist": [p.rpm, p.axial_velocity],
        "sector": [s.n_r, s.n_t, s.n_z, s.z_in, s.z_out],
        "snappy": [p.refinement_level, p.boundary_layers, p.n_layers,
                   float(f"{st.first_cell_height:.3g}")],
    }
    return hashlib.sha1(json.dumps(key, sort_keys=True).encode()).hexdigest()


# --------------------------------------------------------------------------
# case assembly


def build_case(spec: dict, case_dir: Path, force_mesh: bool = True) -> FanState:
    """Write the whole passage case into `case_dir`, meshing it if needed.

    Unlike the 2D airfoil (Gmsh runs in-process), the passage mesh is built by
    blockMesh + snappyHexMesh *inside the OpenFOAM container*, so this blocks
    while that runs and streams progress to `log.mesh`.
    """
    p, st = write_case_files(spec, case_dir)

    sig = _mesh_signature(p, st)
    sig_path = case_dir / _SIG_FILE
    have_mesh = (case_dir / "constant/polyMesh/owner").exists()
    reuse = (
        not force_mesh
        and have_mesh
        and sig_path.exists()
        and sig_path.read_text().strip() == sig
    )
    st.mesh_reused = reuse
    if not reuse:
        run_mesh(case_dir)
        sig_path.write_text(sig)
    st.n_cells = mesh_cell_count(case_dir)
    return st


def write_case_files(spec: dict, case_dir: Path) -> tuple[AxialFanParams, FanState]:
    """Blade STL, every dict and both run scripts — everything except meshing."""
    p = AxialFanParams.from_spec(spec)
    st = derive(p)

    for sub in ("system", "constant/triSurface", "constant", "0"):
        (case_dir / sub).mkdir(parents=True, exist_ok=True)

    blade_geom.export_stl(p.blade_spec(), case_dir / "constant/triSurface/blade.stl")

    _write_block_mesh(case_dir, p)
    _write_surface_features(case_dir)
    _write_snappy(case_dir, p, st)
    _write_topo_set(case_dir)
    _write_mrf(case_dir, st)
    _write_control_dict(case_dir, p, st)
    _write_fv_schemes(case_dir)
    _write_fv_solution(case_dir)
    _write_transport(case_dir, st)
    _write_turbulence(case_dir, p)
    _write_fields(case_dir, p, st)
    if p.n_procs > 1:
        _write_decompose_par(case_dir, p)
    _write_allmesh(case_dir, p)
    _write_allrun(case_dir, p)
    return p, st


def run_mesh(case_dir: Path) -> None:
    """Run ./Allmesh in the OpenFOAM container, teeing output into log.mesh."""
    from app.services.runner.docker_runner import DockerRunner

    log = case_dir / MESH_LOG
    log.write_text("[mesh] starting OpenFOAM container (blockMesh -> snappyHexMesh)\n")
    runner = DockerRunner()
    handle = runner.submit(case_dir, "./Allmesh")
    with log.open("a") as fh:
        for chunk in runner.stream_logs(handle):
            fh.write(chunk)
            fh.flush()
    status = runner.status(handle)
    with log.open("a") as fh:
        fh.write(f"[mesh] {'done' if status == 'completed' else 'ERROR'} ({status})\n")
    if status != "completed":
        tail = "\n".join(log.read_text(errors="replace").splitlines()[-25:])
        raise RuntimeError(f"passage meshing failed:\n{tail}")


def mesh_cell_count(case_dir: Path) -> int | None:
    """Cell count reported by checkMesh at the end of Allmesh."""
    log = case_dir / "log.checkMesh"
    if not log.exists():
        return None
    for line in log.read_text(errors="replace").splitlines():
        s = line.strip()
        if s.startswith("cells:"):
            try:
                return int(s.split(":")[1])
            except ValueError:
                return None
    return None


def mesh_ready(case_dir: Path) -> bool:
    return (case_dir / "constant/polyMesh/owner").exists()


# --------------------------------------------------------------------------
# dictionaries


def _write_block_mesh(case_dir: Path, p: AxialFanParams) -> None:
    s = _sector(p)
    h = s.half_angle
    # 0-3 inlet plane (hub/tip x -theta/+theta), 4-7 the same at the outlet
    verts = [
        _cyl(s.r_hub, -h, s.z_in), _cyl(s.r_tip, -h, s.z_in),
        _cyl(s.r_tip, h, s.z_in), _cyl(s.r_hub, h, s.z_in),
        _cyl(s.r_hub, -h, s.z_out), _cyl(s.r_tip, -h, s.z_out),
        _cyl(s.r_tip, h, s.z_out), _cyl(s.r_hub, h, s.z_out),
    ]
    f = FoamFile(case_dir / "system/blockMeshDict")
    f["scale"] = 1.0
    f["vertices"] = verts
    f["blocks"] = ["hex", list(range(8)), [s.n_r, s.n_t, s.n_z], "simpleGrading", [1, 1, 1]]
    # The four circumferential edges are arcs, not chords, or the hub and casing
    # would be flat-sided polygons. blockMesh reads this as a flat token stream
    # (`arc v1 v2 (point)` repeated), not as a list of lists.
    arcs: list = []
    for a, b, r, z in ((0, 3, s.r_hub, s.z_in), (1, 2, s.r_tip, s.z_in),
                       (4, 7, s.r_hub, s.z_out), (5, 6, s.r_tip, s.z_out)):
        arcs += ["arc", a, b, _cyl(r, 0.0, z)]
    f["edges"] = arcs
    # face winding is outward-normal throughout
    f["boundary"] = [
        "inlet", {"type": "patch", "faces": [[0, 3, 2, 1]]},
        "outlet", {"type": "patch", "faces": [[4, 5, 6, 7]]},
        "hub", {"type": "wall", "faces": [[0, 4, 7, 3]]},
        "shroud", {"type": "wall", "faces": [[1, 2, 6, 5]]},
        "periodic1", {
            "type": "cyclicAMI", "neighbourPatch": "periodic2",
            "transform": "rotational", "rotationAxis": [0, 0, 1], "rotationCentre": [0, 0, 0],
            "faces": [[0, 1, 5, 4]],
        },
        "periodic2", {
            "type": "cyclicAMI", "neighbourPatch": "periodic1",
            "transform": "rotational", "rotationAxis": [0, 0, 1], "rotationCentre": [0, 0, 0],
            "faces": [[3, 7, 6, 2]],
        },
    ]


def _write_surface_features(case_dir: Path) -> None:
    f = FoamFile(case_dir / "system/surfaceFeatureExtractDict")
    f["blade.stl"] = {
        "extractionMethod": "extractFromSurface",
        "extractFromSurfaceCoeffs": {"includedAngle": 150},
        "writeObj": "no",
    }


def _write_snappy(case_dir: Path, p: AxialFanParams, st: FanState) -> None:
    s = _sector(p)
    lvl = int(p.refinement_level)
    # a point that is unambiguously fluid: mid-span, on the sector centreline,
    # well upstream of the blade
    seed = _cyl(0.5 * (s.r_hub + s.r_tip), 0.0, 0.5 * s.z_in)

    f = FoamFile(case_dir / "system/snappyHexMeshDict")
    f["castellatedMesh"] = True
    f["snap"] = True
    f["addLayers"] = bool(p.boundary_layers)
    f["geometry"] = {"blade.stl": {"type": "triSurfaceMesh", "name": "blade"}}
    f["castellatedMeshControls"] = {
        "maxLocalCells": 2000000,
        "maxGlobalCells": 6000000,
        "minRefinementCells": 0,
        "nCellsBetweenLevels": 2,
        "features": [{"file": '"blade.eMesh"', "level": lvl}],
        "refinementSurfaces": {
            "blade": {"level": [max(1, lvl - 1), lvl], "patchInfo": {"type": "wall"}}
        },
        "resolveFeatureAngle": 30,
        "refinementRegions": {
            "blade": {"mode": "distance", "levels": [[2.5 * s.base_cell, max(1, lvl - 1)]]}
        },
        "locationInMesh": seed,
        "allowFreeStandingZoneFaces": True,
    }
    f["snapControls"] = {
        "nSmoothPatch": 3, "tolerance": 2.0, "nSolveIter": 50, "nRelaxIter": 5,
        "nFeatureSnapIter": 10, "implicitFeatureSnap": False,
        "explicitFeatureSnap": True, "multiRegionFeatureSnap": False,
    }
    f["addLayersControls"] = {
        "relativeSizes": False,
        "layers": {"blade": {"nSurfaceLayers": int(p.n_layers)}},
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
        "maxConcave": 80, "minVol": 1e-16, "minTetQuality": -1e30, "minArea": -1,
        "minTwist": 0.02, "minDeterminant": 0.001, "minFaceWeight": 0.05,
        "minVolRatio": 0.01, "minTriangleTwist": -1, "nSmoothScale": 4, "errorReduction": 0.75,
    }
    f["mergeTolerance"] = 1e-6


def _write_topo_set(case_dir: Path) -> None:
    """Put every cell in a `rotor` cellZone — MRF needs a zone to spin."""
    big = 1.0e3
    f = FoamFile(case_dir / "system/topoSetDict")
    f["actions"] = [
        {"name": "rotor", "type": "cellSet", "action": "new", "source": "boxToCell",
         "boxes": [[-big, -big, -big], [big, big, big]]},
        {"name": "rotor", "type": "cellZoneSet", "action": "new", "source": "setToCellZone",
         "set": "rotor"},
    ]


def _write_mrf(case_dir: Path, st: FanState) -> None:
    """Spin the whole passage as one reference frame.

    `nonRotatingPatches` must list every patch of the zone that is *not* a
    surface turning with the shaft — here that is everything except the blade
    and the hub. This is not cosmetic: MRF treats any other patch of the zone as
    a rotating wall, forces its relative flux to zero and overwrites its
    velocity with omega x r. Leaving the inlet and outlet off this list seals
    the machine shut (sum(phi) = 0 through both) and the solver quietly churns
    a closed box.
    """
    f = FoamFile(case_dir / "constant/MRFProperties")
    f["rotor"] = {
        "cellZone": "rotor",
        "active": True,
        "nonRotatingPatches": [p for p in _PATCHES if p not in _ROTATING_WALLS],
        "origin": [0, 0, 0],
        "axis": [0, 0, 1],
        "omega": ("constant", st.shaft_omega),
    }


def _write_decompose_par(case_dir: Path, p: AxialFanParams) -> None:
    f = FoamFile(case_dir / "system/decomposeParDict")
    f["numberOfSubdomains"] = int(p.n_procs)
    f["method"] = "scotch"


def _write_control_dict(case_dir: Path, p: AxialFanParams, st: FanState) -> None:
    rho = st.density
    f = FoamFile(case_dir / "system/controlDict")
    f["application"] = "simpleFoam"
    f["startFrom"] = "startTime"
    f["startTime"] = 0
    f["stopAt"] = "endTime"
    f["endTime"] = int(p.end_time)
    f["deltaT"] = 1
    f["writeControl"] = "timeStep"
    f["writeInterval"] = int(p.write_interval)
    f["purgeWrite"] = 0
    f["writeFormat"] = "ascii"
    f["writePrecision"] = 8
    f["writeCompression"] = "off"
    f["timeFormat"] = "general"
    f["timePrecision"] = 6
    f["runTimeModifiable"] = True

    every = 25
    probe = {
        "type": "surfaceFieldValue", "libs": ["fieldFunctionObjects"], "regionType": "patch",
        "writeFields": False, "log": False,
        "executeControl": "timeStep", "executeInterval": every,
        "writeControl": "timeStep", "writeInterval": every,
    }
    # order matters: pTotal must be computed before the patch averages read it
    f["functions"] = {
        "pTotal": {
            "type": "pressure", "libs": ["fieldFunctionObjects"],
            "mode": "total", "result": "pTotal",
            # incompressible p is kinematic; rhoInf converts it to Pa
            "rho": "rhoInf", "rhoInf": rho,
            "writeControl": "writeTime",
        },
        "flowRate": {**probe, "name": "inlet", "operation": "sum", "fields": ["phi"]},
        "p0Inlet": {**probe, "name": "inlet", "operation": "areaAverage", "fields": ["pTotal"]},
        "p0Outlet": {**probe, "name": "outlet", "operation": "areaAverage", "fields": ["pTotal"]},
        # exit velocity: its tangential part is the swirl the rotor imparted,
        # which is what Euler's turbomachinery equation predicts the work from
        "outletU": {**probe, "name": "outlet", "operation": "areaAverage", "fields": ["U"]},
        "bladeForces": {
            "type": "forces", "libs": ["forces"], "patches": ["blade"],
            "CofR": [0, 0, 0], "rho": "rhoInf", "rhoInf": rho,
            "log": False, "executeControl": "timeStep", "executeInterval": every,
            "writeControl": "timeStep", "writeInterval": every,
        },
    }


def _write_fv_schemes(case_dir: Path) -> None:
    f = FoamFile(case_dir / "system/fvSchemes")
    f["ddtSchemes"] = {"default": "steadyState"}
    f["gradSchemes"] = {"default": ("cellLimited", "Gauss", "linear", 1)}
    f["divSchemes"] = {
        "default": "none",
        "div(phi,U)": "bounded Gauss linearUpwind grad(U)",
        "div(phi,k)": "bounded Gauss upwind",
        "div(phi,omega)": "bounded Gauss upwind",
        "div(phi,epsilon)": "bounded Gauss upwind",
        "div((nuEff*dev2(T(grad(U)))))": "Gauss linear",
    }
    # snappy meshes are non-orthogonal near the blade: limit the correction
    f["laplacianSchemes"] = {"default": ("Gauss", "linear", "limited", "corrected", 0.33)}
    f["interpolationSchemes"] = {"default": "linear"}
    f["snGradSchemes"] = {"default": ("limited", "corrected", 0.33)}
    f["wallDist"] = {"method": "meshWave"}


def _write_fv_solution(case_dir: Path) -> None:
    f = FoamFile(case_dir / "system/fvSolution")
    f["solvers"] = {
        "p": {"solver": "GAMG", "tolerance": 1e-7, "relTol": 0.01, "smoother": "GaussSeidel"},
        '"(U|k|omega|epsilon)"': {
            "solver": "smoothSolver", "smoother": "symGaussSeidel",
            "tolerance": 1e-8, "relTol": 0.1,
        },
    }
    f["SIMPLE"] = {
        # the AMI couple and the snapped blade surface both add non-orthogonality
        "nNonOrthogonalCorrectors": 2,
        "consistent": True,
        "residualControl": {"p": 1e-4, "U": 1e-4, '"(k|omega|epsilon)"': 1e-4},
    }
    f["relaxationFactors"] = {
        "fields": {"p": 0.3},
        "equations": {"U": 0.7, '"(k|omega|epsilon)"': 0.7},
    }


def _write_transport(case_dir: Path, st: FanState) -> None:
    f = FoamFile(case_dir / "constant/transportProperties")
    f["transportModel"] = "Newtonian"
    f["nu"] = st.nu


def _write_turbulence(case_dir: Path, p: AxialFanParams) -> None:
    f = FoamFile(case_dir / "constant/turbulenceProperties")
    f["simulationType"] = "RAS"
    f["RAS"] = {"RASModel": p.turbulence_model, "turbulence": "on", "printCoeffs": "on"}


def _write_fields(case_dir: Path, p: AxialFanParams, st: FanState) -> None:
    va = p.axial_velocity
    cyclic = {"type": "cyclicAMI"}
    rotating = {
        "type": "rotatingWallVelocity",
        "origin": [0, 0, 0], "axis": [0, 0, 1],
        "omega": ("constant", st.shaft_omega),
        "value": [0.0, 0.0, 0.0],
    }

    fU = FoamFieldFile(case_dir / "0/U")
    fU.dimensions = [0, 1, -1, 0, 0, 0, 0]
    fU.internal_field = [0.0, 0.0, va]
    fU.boundary_field = {
        "inlet": {"type": "fixedValue", "value": [0.0, 0.0, va]},
        "outlet": {"type": "inletOutlet", "inletValue": [0.0, 0.0, 0.0], "value": [0.0, 0.0, va]},
        # blade and hub turn with the shaft; MRF works in the absolute frame, so
        # these walls carry their real velocity omega x r
        "hub": dict(rotating),
        "blade": dict(rotating),
        "shroud": {"type": "noSlip"},
        "periodic1": cyclic,
        "periodic2": cyclic,
    }

    fp = FoamFieldFile(case_dir / "0/p")
    fp.dimensions = [0, 2, -2, 0, 0, 0, 0]   # kinematic (simpleFoam)
    fp.internal_field = 0.0
    fp.boundary_field = {
        "inlet": {"type": "zeroGradient"},
        "outlet": {"type": "fixedValue", "value": 0.0},
        **{w: {"type": "zeroGradient"} for w in _WALLS},
        "periodic1": cyclic,
        "periodic2": cyclic,
    }

    fk = FoamFieldFile(case_dir / "0/k")
    fk.dimensions = [0, 2, -2, 0, 0, 0, 0]
    fk.internal_field = st.k
    fk.boundary_field = {
        "inlet": {"type": "fixedValue", "value": st.k},
        "outlet": {"type": "inletOutlet", "inletValue": st.k, "value": st.k},
        **{w: {"type": "kqRWallFunction", "value": st.k} for w in _WALLS},
        "periodic1": cyclic,
        "periodic2": cyclic,
    }

    fo = FoamFieldFile(case_dir / "0/omega")
    fo.dimensions = [0, 0, -1, 0, 0, 0, 0]
    fo.internal_field = st.omega
    fo.boundary_field = {
        "inlet": {"type": "fixedValue", "value": st.omega},
        "outlet": {"type": "inletOutlet", "inletValue": st.omega, "value": st.omega},
        **{w: {"type": "omegaWallFunction", "value": st.omega} for w in _WALLS},
        "periodic1": cyclic,
        "periodic2": cyclic,
    }

    fn = FoamFieldFile(case_dir / "0/nut")
    fn.dimensions = [0, 2, -1, 0, 0, 0, 0]
    fn.internal_field = 0.0
    fn.boundary_field = {
        "inlet": {"type": "calculated", "value": 0.0},
        "outlet": {"type": "calculated", "value": 0.0},
        # Spalding is continuous across y+, so it holds for both the default
        # wall-function mesh and an opt-in resolved one
        **{w: {"type": "nutUSpaldingWallFunction", "value": 0.0} for w in _WALLS},
        "periodic1": cyclic,
        "periodic2": cyclic,
    }


# --------------------------------------------------------------------------
# run scripts


def _write_allmesh(case_dir: Path, p: AxialFanParams) -> None:
    """Meshing only — the GUI runs this from the Mesh tab and watches log.mesh."""
    spec = p.blade_spec()
    script = f"""#!/bin/bash
cd "${{0%/*}}" || exit
# pipefail matters: every stage is piped into tee, so without it a failing
# solver or mesher is masked by tee's exit status and the script marches on
set -eo pipefail

echo "============================================================"
echo " OpenFOAM GUI :: axial fan passage — meshing"
echo " blades: {spec.n_blades}   sector: {360 / spec.n_blades:.1f} deg   hub/tip: {p.hub_radius:g}/{p.tip_radius:g} m"
echo "============================================================"

echo "[1/4] blockMesh — annular sector background mesh"
blockMesh 2>&1 | tee log.blockMesh

echo "[2/4] surfaceFeatureExtract — blade feature edges"
surfaceFeatureExtract 2>&1 | tee log.surfaceFeatureExtract

echo "[3/4] snappyHexMesh — carving the blade from the passage"
snappyHexMesh -overwrite 2>&1 | tee log.snappy

echo "[4/4] topoSet + checkMesh"
topoSet 2>&1 | tee log.topoSet
# quality problems are reported to the user through preflight, not by failing
# the mesh step, so this one check is deliberately non-fatal
checkMesh -allGeometry -allTopology 2>&1 | tee log.checkMesh || true
echo "MESH DONE"
"""
    path = case_dir / "Allmesh"
    path.write_text(script)
    path.chmod(0o755)


def _write_allrun(case_dir: Path, p: AxialFanParams) -> None:
    n = int(p.n_procs)
    if n > 1:
        solve = (
            "decomposePar -force 2>&1 | tee log.decomposePar\n"
            f"mpirun --allow-run-as-root -np {n} simpleFoam -parallel 2>&1 | tee log.simpleFoam\n"
            "reconstructPar -latestTime 2>&1 | tee log.reconstructPar\n"
        )
    else:
        solve = "simpleFoam 2>&1 | tee log.simpleFoam\n"

    spec = p.blade_spec()
    script = f"""#!/bin/bash
cd "${{0%/*}}" || exit
# pipefail matters: every stage is piped into tee, so without it a failing
# solver or mesher is masked by tee's exit status and the script marches on
set -eo pipefail

echo "============================================================"
echo " OpenFOAM GUI :: axial fan passage (MRF)"
echo " {spec.rpm:g} rpm   cores: {n}   turbulence: {p.turbulence_model}"
echo " single passage of {spec.n_blades} blades — cyclicAMI periodics"
echo "============================================================"

if [ ! -f constant/polyMesh/owner ]; then
  echo "[1/3] mesh missing — running Allmesh first"
  ./Allmesh
else
  echo "[1/3] reusing the passage mesh already on disk"
fi

echo "[2/3] renumberMesh"
renumberMesh -overwrite 2>&1 | tee log.renumberMesh

echo "[3/3] simpleFoam (MRF rotor at {spec.rpm:g} rpm)"
{solve}
echo "DONE"
"""
    path = case_dir / "Allrun"
    path.write_text(script)
    path.chmod(0o755)




# registry alias (see services/generators/__init__.py)
Params = AxialFanParams


def summary(st: FanState) -> dict:
    """Derived quantities the Mesh tab shows after generating the passage."""
    return {
        "reynolds": st.reynolds,
        "mach": st.tip_mach,
        "k": st.k,
        "omega": st.omega,
        "first_cell_height": st.first_cell_height,
        "shaft_omega": st.shaft_omega,
        "tip_speed": st.tip_speed,
        "volumetric_flow": st.volumetric_flow,
        "flow_coefficient": st.blade.flow_coefficient,
        "sections": [
            {
                "radius": s.radius,
                "blade_speed": s.blade_speed,
                "relative_angle": s.relative_angle,
                "stagger": s.stagger,
                "solidity": s.solidity,
            }
            for s in st.sections
        ],
    }
