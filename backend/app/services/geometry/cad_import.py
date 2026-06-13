"""CAD import: accept STL directly, or convert STEP -> STL via CadQuery.

Imported surfaces land in a case's constant/triSurface for snappyHexMesh.
"""

from __future__ import annotations

from pathlib import Path


def save_surface(data: bytes, filename: str, dest_dir: Path) -> dict:
    """Persist an uploaded geometry file as STL under dest_dir.

    STL is written as-is; STEP/STP is tessellated to STL with CadQuery.
    Returns basic info (name, format, triangle count if known).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    stem = Path(filename).stem

    if suffix == ".stl":
        out = dest_dir / f"{stem}.stl"
        out.write_bytes(data)
        return {"name": out.name, "format": "stl"}

    if suffix in (".step", ".stp"):
        import tempfile

        import cadquery as cq

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        shape = cq.importers.importStep(tmp_path)
        out = dest_dir / f"{stem}.stl"
        cq.exporters.export(shape, str(out))
        return {"name": out.name, "format": "step->stl"}

    raise ValueError(f"Unsupported geometry format: {suffix} (expected .stl, .step, .stp)")
