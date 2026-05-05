"""Configuration helpers for GapForge."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GapForgeConfig:
    """Runtime paths for a GapForge workspace."""

    root: Path
    runs_dir: Path
    data_dir: Path
    skills_dir: Path
    cache_dir: Path

    @classmethod
    def from_cwd(cls, cwd: Path | None = None) -> GapForgeConfig:
        root = (cwd or Path.cwd()).resolve()
        cache_dir = Path(os.environ.get("GAPFORGE_CACHE_DIR", root / ".gapforge_cache")).resolve()
        return cls(
            root=root,
            runs_dir=root / "runs",
            data_dir=root / "data",
            skills_dir=root / "skills",
            cache_dir=cache_dir,
        )

    @classmethod
    def from_env_or_cwd(cls, cwd: Path | None = None) -> GapForgeConfig:
        root_override = os.environ.get("GAPFORGE_ROOT")
        return cls.from_cwd(Path(root_override) if root_override else cwd)

    def ensure_dirs(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
