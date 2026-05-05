"""Citation and provenance tracking primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class ProvenanceRecord:
    artifact_id: str
    source_id: str
    source_type: str
    locator: str
    note: str


class ProvenanceTracker:
    def __init__(self) -> None:
        self.records: list[ProvenanceRecord] = []

    def add(self, artifact_id: str, source_id: str, source_type: str, locator: str, note: str) -> None:
        self.records.append(
            ProvenanceRecord(
                artifact_id=artifact_id,
                source_id=source_id,
                source_type=source_type,
                locator=locator,
                note=note,
            )
        )

    def to_dicts(self) -> list[dict[str, Any]]:
        return [asdict(record) for record in self.records]
