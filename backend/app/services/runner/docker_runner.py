"""Local Docker runner targeting the opencfd/openfoam images (~/CFD scheme)."""

import docker
from docker.errors import DockerException

from app.config import settings


def docker_status() -> dict:
    """Daemon reachability + OpenFOAM image availability for the system panel."""
    try:
        client = docker.from_env()
        client.ping()
    except DockerException as exc:
        return {"connected": False, "error": str(exc), "image": None}

    try:
        image = client.images.get(settings.openfoam_image)
        image_info = {"name": settings.openfoam_image, "available": True, "id": image.short_id}
    except docker.errors.ImageNotFound:
        image_info = {"name": settings.openfoam_image, "available": False}

    return {"connected": True, "image": image_info}


class DockerRunner:
    """Implements the Runner protocol. TODO(phase-1): submit/logs/status/cancel."""

    # Containers run as the image's default user with the case dir mounted at
    # /case; Allrun-style scripts execute via the image's entrypoint shell.
