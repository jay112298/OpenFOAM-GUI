"""Clean 2D airfoil mesh via Gmsh.

Produces a genuinely 2D (single cell in span) unstructured mesh with prism
boundary layers sized to a target y+. Far-field is a circle; the airfoil is a
closed spline. The 2D surface is extruded one cell in z and recombined to
hex/prism, giving clean `empty` front/back patches (unlike snappy on a thin
slab, which refines the span direction and breaks the 2D constraint).

Patches (named via Gmsh physical groups -> OpenFOAM patches by gmshToFoam):
  airfoil       wall
  farfield      patch
  frontAndBack  empty
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path


def build_mesh(
    coords: list[list[float]],
    chord: float,
    first_layer: float,
    n_layers: int = 20,
    expansion: float = 1.2,
    farfield_radius: float = 15.0,
    span: float = 0.05,
    n_far: float = 4.0,
    out_path: Path | None = None,
) -> Path:
    """Generate the airfoil mesh in a spawned subprocess.

    Gmsh installs signal handlers that only work on the interpreter's main
    thread; FastAPI/uvicorn run request handlers in a worker thread, so we run
    Gmsh in a fresh process (its own main thread) and collect the .msh file.
    """
    out_path = out_path or Path("airfoil.msh")
    ctx = mp.get_context("spawn")
    proc = ctx.Process(
        target=_run_gmsh,
        args=(coords, chord, first_layer, n_layers, expansion, farfield_radius, span, n_far, str(out_path)),
    )
    proc.start()
    proc.join()
    if proc.exitcode != 0 or not out_path.exists():
        raise RuntimeError(f"Gmsh meshing failed (exit {proc.exitcode})")
    return out_path


def _run_gmsh(
    coords: list[list[float]],
    chord: float,
    first_layer: float,
    n_layers: int,
    expansion: float,
    farfield_radius: float,
    span: float,
    n_far: float,
    out_path_str: str,
) -> None:
    import gmsh

    out_path = Path(out_path_str)
    R = farfield_radius * chord
    cx = 0.25 * chord  # far-field centred at quarter chord

    # de-duplicate consecutive points and drop a closing duplicate
    pts = []
    for x, y in coords:
        if not pts or (abs(pts[-1][0] - x) > 1e-12 or abs(pts[-1][1] - y) > 1e-12):
            pts.append((float(x), float(y)))
    if abs(pts[0][0] - pts[-1][0]) < 1e-12 and abs(pts[0][1] - pts[-1][1]) < 1e-12:
        pts.pop()

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("airfoil")
        occ = gmsh.model.occ

        # airfoil closed spline
        ptags = [occ.addPoint(x, y, 0.0) for x, y in pts]
        spline = occ.addSpline(ptags + [ptags[0]])
        loop_af = occ.addCurveLoop([spline])

        # far-field circle
        circ = occ.addCircle(cx, 0.0, 0.0, R)
        loop_ff = occ.addCurveLoop([circ])

        surf = occ.addPlaneSurface([loop_ff, loop_af])
        occ.synchronize()

        # Graded size field: near-wall cell ~ first_layer (sized from the y+
        # target, wall-function band), growing to a coarse far field. We avoid
        # Gmsh's BoundaryLayer field on purpose: combined with OCC + structured
        # extrude it produces degenerate (negative-volume) cells. An isotropic
        # graded quad mesh is lower-aspect but robust and converges cleanly.
        field = gmsh.model.mesh.field
        f_dist = field.add("Distance")
        field.setNumbers(f_dist, "CurvesList", [spline])
        field.setNumber(f_dist, "Sampling", 400)
        lc_wall = max(first_layer, chord / 800.0)  # don't go absurdly fine
        lc_far = n_far * chord
        f_thr = field.add("Threshold")
        field.setNumber(f_thr, "InField", f_dist)
        field.setNumber(f_thr, "SizeMin", lc_wall)
        field.setNumber(f_thr, "SizeMax", lc_far)
        field.setNumber(f_thr, "DistMin", 0.01 * chord)
        field.setNumber(f_thr, "DistMax", 3.0 * chord)
        field.setAsBackgroundMesh(f_thr)

        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.Algorithm", 6)  # Frontal-Delaunay (quality)
        gmsh.option.setNumber("Mesh.RecombineAll", 1)
        gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 1)  # Blossom
        gmsh.option.setNumber("Mesh.Smoothing", 10)
        gmsh.model.mesh.generate(2)
        gmsh.model.mesh.optimize("Netgen")

        # extrude one cell in z (structured: replicates the 2D mesh) -> clean 2D
        ext = occ.extrude([(2, surf)], 0, 0, span, numElements=[1], recombine=True)
        occ.synchronize()

        vol = [e[1] for e in ext if e[0] == 3]
        _assign_physical_groups(gmsh, cx, R, chord, span, vol)

        gmsh.model.mesh.generate(3)
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)  # gmshToFoam wants msh2
        out_path.parent.mkdir(parents=True, exist_ok=True)
        gmsh.write(str(out_path))

        # sidecar with the 3D cell count, for UI feedback
        _types, tags3d, _ = gmsh.model.mesh.getElements(dim=3)
        n_cells = sum(len(t) for t in tags3d)
        out_path.with_suffix(".ncells").write_text(str(n_cells))
    finally:
        gmsh.finalize()


def _assign_physical_groups(gmsh, cx, R, chord, span, vol):
    """Classify boundary surfaces by bounding box: front/back are the flat
    z-faces (near-zero z extent); of the lateral surfaces, the far-field spans
    ~2R while the airfoil spans ~one chord. (Center-of-mass fails here: the full
    far-field cylinder's COM sits on its axis, same radius as the airfoil.)"""
    surfaces = gmsh.model.getEntities(2)
    front_back, airfoil, farfield = [], [], []
    for dim, tag in surfaces:
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
        z_extent = zmax - zmin
        xy_extent = max(xmax - xmin, ymax - ymin)
        if z_extent < 0.5 * span:
            front_back.append(tag)  # flat face at z=0 or z=span
        elif xy_extent > 3.0 * chord:
            farfield.append(tag)
        else:
            airfoil.append(tag)

    gmsh.model.addPhysicalGroup(3, vol, name="internal")
    if airfoil:
        gmsh.model.addPhysicalGroup(2, airfoil, name="airfoil")
    if farfield:
        gmsh.model.addPhysicalGroup(2, farfield, name="farfield")
    if front_back:
        gmsh.model.addPhysicalGroup(2, front_back, name="frontAndBack")
