"""Open a finished case in the user's local ParaView.

Writes a `<case>.foam` stub (the file ParaView's OpenFOAM reader opens) and
launches ParaView pointed at it. Backend runs on the user's machine, so this
opens their desktop ParaView directly.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def write_foam_stub(case_dir: Path) -> Path:
    stub = case_dir / f"{case_dir.name}.foam"
    stub.write_text("")  # empty file is enough for the reader
    return stub


def find_paraview() -> str | None:
    # PATH first, then the common macOS app bundle
    exe = shutil.which("paraview")
    if exe:
        return exe
    for p in Path("/Applications").glob("ParaView*.app/Contents/MacOS/paraview"):
        return str(p)
    return None


def open_in_paraview(case_dir: Path) -> dict:
    if not case_dir.exists():
        raise FileNotFoundError("case directory not found — generate and run first")
    stub = write_foam_stub(case_dir)
    exe = find_paraview()
    if exe is None:
        # Fall back to `open` with the app bundle on macOS
        subprocess.Popen(["open", "-a", "ParaView", str(stub)])
        return {"launched": True, "via": "open -a ParaView", "file": str(stub)}
    subprocess.Popen([exe, str(stub)])
    return {"launched": True, "via": exe, "file": str(stub)}
