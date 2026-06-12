from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, overridable via environment variables (OFGUI_ prefix)."""

    # Storage
    data_dir: Path = Path.home() / ".openfoam-gui"
    cases_dir: Path | None = None  # defaults to data_dir / "cases"
    db_path: Path | None = None  # defaults to data_dir / "ofgui.db"

    # OpenFOAM Docker image (matches user's ~/CFD/openfoam-docker scheme)
    openfoam_image: str = "opencfd/openfoam-run:2506"

    # Dev server
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_prefix": "OFGUI_"}

    def model_post_init(self, __context) -> None:
        if self.cases_dir is None:
            self.cases_dir = self.data_dir / "cases"
        if self.db_path is None:
            self.db_path = self.data_dir / "ofgui.db"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cases_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
