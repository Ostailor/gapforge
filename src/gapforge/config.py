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
    project_root: Path
    data_dir: Path
    skills_dir: Path
    cache_dir: Path
    llm_mode: str = "off"

    @classmethod
    def from_cwd(cls, cwd: Path | None = None) -> GapForgeConfig:
        root = (cwd or Path.cwd()).resolve()
        cache_dir = Path(os.environ.get("GAPFORGE_CACHE_DIR", root / ".gapforge_cache")).resolve()
        project_root = Path(os.environ.get("GAPFORGE_PROJECT_ROOT", root / "projects")).resolve()
        llm_mode = os.environ.get("GAPFORGE_LLM_MODE", "off").strip().lower() or "off"
        if llm_mode not in {"off", "prompt-pack", "fake", "provider"}:
            llm_mode = "off"
        return cls(
            root=root,
            runs_dir=root / "runs",
            project_root=project_root,
            data_dir=root / "data",
            skills_dir=root / "skills",
            cache_dir=cache_dir,
            llm_mode=llm_mode,
        )

    @classmethod
    def from_env_or_cwd(cls, cwd: Path | None = None) -> GapForgeConfig:
        root_override = os.environ.get("GAPFORGE_ROOT")
        return cls.from_cwd(Path(root_override) if root_override else cwd)

    def ensure_dirs(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
