"""Local Docker runner targeting the opencfd/openfoam images (~/CFD scheme).

Implements the Runner protocol. The OpenFOAM image runs as user `openfoam`;
we mount the case at /data and execute the case's Allrun via the image's
shell (which sources the OpenFOAM environment on login).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import docker
from docker.errors import DockerException, ImageNotFound

from app.config import settings


def get_client():
    client = docker.from_env()
    client.ping()
    return client


def docker_status() -> dict:
    """Daemon reachability + OpenFOAM image availability for the system panel."""
    try:
        client = get_client()
    except DockerException as exc:
        return {"connected": False, "error": str(exc), "image": None}

    try:
        image = client.images.get(settings.openfoam_image)
        image_info = {"name": settings.openfoam_image, "available": True, "id": image.short_id}
    except ImageNotFound:
        image_info = {"name": settings.openfoam_image, "available": False}
    return {"connected": True, "image": image_info}


class DockerRunner:
    """Runs an OpenFOAM case directory in a container, streaming logs."""

    def __init__(self, image: str | None = None):
        self.image = image or settings.openfoam_image

    def submit(self, case_dir: Path, command: str = "./Allrun") -> str:
        client = get_client()
        container = client.containers.run(
            self.image,
            command=["/bin/bash", "-lc", command],
            volumes={str(case_dir.resolve()): {"bind": "/data", "mode": "rw"}},
            working_dir="/data",
            detach=True,
            labels={"openfoam-gui": "true"},
            remove=False,
        )
        return container.id

    def stream_logs(self, handle: str) -> Iterator[str]:
        client = get_client()
        container = client.containers.get(handle)
        for chunk in container.logs(stream=True, follow=True):
            yield chunk.decode("utf-8", errors="replace")

    async def alogs(self, handle: str) -> AsyncIterator[str]:
        import asyncio

        loop = asyncio.get_event_loop()
        gen = self.stream_logs(handle)
        while True:
            line = await loop.run_in_executor(None, lambda: next(gen, None))
            if line is None:
                break
            yield line

    def status(self, handle: str) -> str:
        client = get_client()
        try:
            container = client.containers.get(handle)
        except docker.errors.NotFound:
            return "unknown"
        state = container.status  # created|running|exited|...
        if state == "exited":
            code = container.attrs["State"]["ExitCode"]
            return "completed" if code == 0 else "failed"
        return "running" if state == "running" else state

    def cancel(self, handle: str) -> None:
        client = get_client()
        try:
            client.containers.get(handle).stop(timeout=5)
        except docker.errors.NotFound:
            pass
