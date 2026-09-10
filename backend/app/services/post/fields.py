"""Field extraction for in-browser visualisation.

The airfoil cases are 2D (one cell across the span), so a mid-span slice *is*
the solution. We read the case with PyVista, slice it, triangulate, and ship a
compact triangle soup the browser can paint on a canvas.

That is deliberately lighter than the VTK.js path in the roadmap: for a planar
result there is nothing to orbit, and a few hundred KB of triangles beats
loading a 3D rendering library into the page.
"""

from __future__ import annotations

from pathlib import Path

# vector fields are offered as magnitude plus components
_VECTOR_COMPONENTS = {"Magnitude": None, "x": 0, "y": 1}


def _reader(case_dir: Path):
    import pyvista as pv

    stub = case_dir / "case.foam"
    if not stub.exists():
        stub.write_text("")
    return pv.OpenFOAMReader(str(stub))


def available(case_dir: Path) -> dict:
    """Fields and time values present in the case, or an empty result if unrun."""
    if not (case_dir / "constant" / "polyMesh").exists():
        return {"fields": [], "times": [], "ready": False}
    try:
        reader = _reader(case_dir)
        times = [float(t) for t in reader.time_values]
        if len(times) <= 1:  # only time 0 -> nothing solved yet
            return {"fields": [], "times": times, "ready": False}
        reader.set_active_time_value(times[-1])
        mesh = reader.read()["internalMesh"]
        names = []
        for name in mesh.point_data.keys():
            arr = mesh.point_data[name]
            if arr.ndim == 1:
                names.append(name)
            else:
                names.extend(f"{name}:{c}" for c in _VECTOR_COMPONENTS)
        return {"fields": sorted(names), "times": times, "ready": True}
    except Exception as exc:  # noqa: BLE001 - report instead of 500ing the tab
        return {"fields": [], "times": [], "ready": False, "error": str(exc)}


def slice_field(case_dir: Path, field: str, time: float | None = None, max_tris: int = 60000) -> dict:
    """Mid-span slice of `field` as triangles + per-point values.

    Returns flat arrays (points xy, triangle indices, values) so the payload
    stays small and the client can paint it directly.
    """
    import numpy as np

    reader = _reader(case_dir)
    times = [float(t) for t in reader.time_values]
    if not times:
        raise ValueError("no time steps in case")
    t = time if time is not None else times[-1]
    reader.set_active_time_value(t)
    mesh = reader.read()["internalMesh"]

    name, _, comp = field.partition(":")
    if name not in mesh.point_data:
        raise ValueError(f"unknown field: {name}")

    sl = mesh.slice(normal="z").triangulate()
    if sl.n_cells > max_tris:
        sl = sl.decimate(1 - max_tris / sl.n_cells)

    arr = np.asarray(sl.point_data[name])
    if arr.ndim > 1:
        idx = _VECTOR_COMPONENTS.get(comp or "Magnitude")
        arr = np.linalg.norm(arr, axis=1) if idx is None else arr[:, idx]

    pts = np.asarray(sl.points)[:, :2]
    faces = np.asarray(sl.faces).reshape(-1, 4)[:, 1:]  # [3, i, j, k] per triangle

    finite = arr[np.isfinite(arr)]
    lo, hi = (float(finite.min()), float(finite.max())) if finite.size else (0.0, 1.0)

    return {
        "field": field,
        "time": t,
        "times": times,
        "range": [lo, hi],
        "bounds": [float(pts[:, 0].min()), float(pts[:, 0].min() * 0 + pts[:, 1].min()),
                   float(pts[:, 0].max()), float(pts[:, 1].max())],
        "n_triangles": int(faces.shape[0]),
        "points": [round(float(v), 5) for v in pts.ravel()],
        "triangles": [int(v) for v in faces.ravel()],
        "values": [round(float(v), 6) for v in arr],
    }
