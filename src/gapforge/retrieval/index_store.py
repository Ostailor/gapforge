"""Persistence for retrieval indexes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.models import IndexManifest, RetrievalDocument, from_dict, to_plain


class RetrievalIndexStore:
    """Read/write retrieval documents, embeddings, and manifests."""

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir

    @classmethod
    def for_run(cls, run_dir: str | Path) -> RetrievalIndexStore:
        return cls(Path(run_dir) / "retrieval")

    @classmethod
    def for_project(cls, project_dir: str | Path) -> RetrievalIndexStore:
        return cls(Path(project_dir) / "retrieval")

    def save(self, manifest: IndexManifest, documents: list[RetrievalDocument], embeddings: list[list[float]]) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        manifest.path = str(self.index_dir)
        self._write_json("manifest.json", manifest)
        self._write_json("documents.json", documents)
        self._write_json("embeddings.json", embeddings)

    def load_manifest(self) -> IndexManifest:
        path = self.index_dir / "manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"No retrieval index manifest found at {path}")
        return from_dict(IndexManifest, json.loads(path.read_text(encoding="utf-8")))

    def load_documents(self) -> list[RetrievalDocument]:
        path = self.index_dir / "documents.json"
        if not path.exists():
            raise FileNotFoundError(f"No retrieval documents found at {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(RetrievalDocument, item) for item in raw]

    def load_embeddings(self) -> list[list[float]]:
        path = self.index_dir / "embeddings.json"
        if not path.exists():
            raise FileNotFoundError(f"No retrieval embeddings found at {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def exists(self) -> bool:
        return (self.index_dir / "manifest.json").exists() and (self.index_dir / "documents.json").exists()

    def _write_json(self, filename: str, value: Any) -> None:
        (self.index_dir / filename).write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")
