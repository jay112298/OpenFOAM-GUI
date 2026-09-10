"""System status: health, Docker daemon, OpenFOAM image, user settings."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import settings_service
from app.services.runner.docker_runner import docker_status

router = APIRouter()


class SettingsBody(BaseModel):
    openfoam_image: str | None = None
    default_n_procs: int | None = None


@router.get("/settings")
def get_settings():
    return settings_service.info()


@router.put("/settings")
def put_settings(body: SettingsBody):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    settings_service.save(updates)
    return settings_service.info()


@router.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@router.get("/docker")
async def docker():
    return docker_status()
