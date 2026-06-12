"""System status: health, Docker daemon, OpenFOAM image availability."""

from fastapi import APIRouter

from app.services.runner.docker_runner import docker_status

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@router.get("/docker")
async def docker():
    return docker_status()
