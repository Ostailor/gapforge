"""Dataset cache path and maintenance helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig


def dataset_cache_dir(config: GapForgeConfig) -> Path:
    """Return the configurable cache root for downloaded datasets."""

    return Path(os.environ.get("GAPFORGE_DATASET_CACHE_DIR", config.cache_dir / "datasets")).resolve()


def dataset_cache_info(config: GapForgeConfig) -> dict[str, Any]:
    cache_dir = dataset_cache_dir(config)
    files = [path for path in cache_dir.rglob("*") if path.is_file()] if cache_dir.exists() else []
    return {
        "cache_dir": str(cache_dir),
        "exists": cache_dir.exists(),
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "download_records": len(list((cache_dir / "records").glob("*.json"))) if (cache_dir / "records").exists() else 0,
        "consent_records": len(list((cache_dir / "consent").glob("*.json"))) if (cache_dir / "consent").exists() else 0,
        "safe_to_commit": False,
        "reason": "Downloaded datasets and consent records are local generated artifacts and should not be committed by default.",
    }


def clean_dataset_cache(config: GapForgeConfig) -> dict[str, Any]:
    cache_dir = dataset_cache_dir(config)
    before = dataset_cache_info(config)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    after = dataset_cache_info(config)
    return {"before": before, "after": after}


def render_dataset_cache_info(info: dict[str, Any]) -> str:
    if "before" in info and "after" in info:
        return "\n".join(
            [
                "# Dataset Cache Clean",
                "",
                f"- Cache dir: `{info['before']['cache_dir']}`",
                f"- Files before: {info['before']['files']}",
                f"- Bytes before: {info['before']['bytes']}",
                f"- Files after: {info['after']['files']}",
                f"- Bytes after: {info['after']['bytes']}",
                "",
            ]
        )
    return "\n".join(
        [
            "# Dataset Cache",
            "",
            f"- Cache dir: `{info['cache_dir']}`",
            f"- Exists: {str(info['exists']).lower()}",
            f"- Files: {info['files']}",
            f"- Bytes: {info['bytes']}",
            f"- Download records: {info['download_records']}",
            f"- Consent records: {info['consent_records']}",
            f"- Safe to commit: {str(info['safe_to_commit']).lower()}",
            f"- Reason: {info['reason']}",
            "",
        ]
    )
