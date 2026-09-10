"""API smoke tests via FastAPI TestClient (no Docker required)."""

import os
import tempfile

os.environ.setdefault("OFGUI_DATA_DIR", tempfile.mkdtemp(prefix="ofgui-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
client = TestClient(app)


def test_health():
    r = client.get("/api/system/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_templates():
    r = client.get("/api/templates/")
    assert r.status_code == 200
    assert any(t["id"] == "airfoil" for t in r.json())


def test_geometry_naca():
    r = client.post("/api/geometry/naca", json={"designation": "0012", "chord": 1.0})
    assert r.status_code == 200
    assert len(r.json()["coordinates"]) > 50


def test_yplus():
    r = client.post("/api/meshing/yplus", json={"velocity": 30, "length": 1.0, "target_yplus": 30})
    assert r.status_code == 200
    assert r.json()["first_cell_height"] > 0


def test_case_lifecycle():
    # create
    r = client.post("/api/cases/", json={"name": "test-naca", "template": "airfoil"})
    assert r.status_code == 200
    cid = r.json()["id"]
    # generate dicts
    r = client.post(f"/api/cases/{cid}/generate")
    assert r.status_code == 200, r.text
    assert r.json()["reynolds"] > 0
    # validate
    r = client.get(f"/api/cases/{cid}/validate")
    assert r.status_code == 200
    assert r.json()["can_run"] is True
    # delete
    assert client.delete(f"/api/cases/{cid}").status_code == 200


def test_pipeline_status_reflects_progress():
    """The UI seeds stage gating from this, so it must report the mesh + preflight."""
    cid = client.post("/api/cases/", json={"name": "pipe-status", "template": "airfoil"}).json()["id"]

    before = client.get(f"/api/cases/{cid}/pipeline-status").json()
    assert before["mesh"]["exists"] is False
    assert before["latest_run"] is None
    assert before["has_results"] is False

    client.post(f"/api/cases/{cid}/generate")
    after = client.get(f"/api/cases/{cid}/pipeline-status").json()
    assert after["mesh"]["exists"] is True
    assert after["mesh"]["n_cells"] > 0
    assert after["validation"]["can_run"] is True

    client.delete(f"/api/cases/{cid}")


def test_mesh_is_reused_when_unchanged():
    """Run must not redo the (slow) Gmsh mesh when nothing mesh-related changed."""
    from sqlmodel import Session

    from app.db import engine
    from app.models.case import Case
    from app.services import case_service

    cid = client.post("/api/cases/", json={"name": "mesh-reuse", "template": "airfoil"}).json()["id"]
    with Session(engine) as s:
        case = s.get(Case, cid)
        first = case_service.generate(s, case, force_mesh=True)
        assert first["mesh_reused"] is False
        again = case_service.generate(s, case, force_mesh=False)
        assert again["mesh_reused"] is True

    # a mesh-affecting change invalidates it (via the API, like the UI does)
    spec = client.get(f"/api/cases/{cid}").json()["spec"]
    spec["mesh"]["parameters"]["farfield_radius"] = 12.0
    client.put(f"/api/cases/{cid}/spec", json={"spec": spec})
    with Session(engine) as s:
        case = s.get(Case, cid)
        changed = case_service.generate(s, case, force_mesh=False)
        assert changed["mesh_reused"] is False

    client.delete(f"/api/cases/{cid}")


def test_sweep_create_and_status():
    base = client.post("/api/cases/", json={"name": "sweep-base", "template": "airfoil"}).json()["id"]
    r = client.post(
        "/api/sweeps/",
        json={
            "base_case_id": base,
            "values": [0, 4],
            "parameter": "physics.reference.angle_of_attack",
            "name": "test sweep",
        },
    )
    assert r.status_code == 200
    sid = r.json()["id"]

    st = client.get(f"/api/sweeps/{sid}/status").json()
    assert st["total"] == 2
    assert st["done"] == 0
    assert st["queue"]["running"] is False
    assert [c["value"] for c in st["children"]] == [0, 4]
    # child specs carry the swept parameter
    child = client.get(f"/api/cases/{st['children'][1]['case_id']}").json()
    assert child["spec"]["physics"]["reference"]["angle_of_attack"] == 4
