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
