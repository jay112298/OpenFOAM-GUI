"""Runner protocol: where solves execute.

DockerRunner (local) is the only implementation now. SSHRunner (remote
cluster/cloud) plugs in later — API and queue code depend only on this protocol.
"""

from pathlib import Path
from typing import AsyncIterator, Protocol


class Runner(Protocol):
    async def submit(self, case_dir: Path, command: str) -> str:
        """Start a job, return an opaque job handle (e.g. container id)."""
        ...

    async def logs(self, handle: str) -> AsyncIterator[str]:
        """Stream log lines from a running job."""
        ...

    async def status(self, handle: str) -> str:
        """queued | running | completed | failed"""
        ...

    async def cancel(self, handle: str) -> None: ...
