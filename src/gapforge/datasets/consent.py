"""Dataset download consent records."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.datasets.cache import dataset_cache_dir
from gapforge.models import DatasetConsentRecord, Provenance, from_dict, to_plain
from gapforge.state import utc_now_iso


class DatasetConsentManager:
    """Persist explicit user consent for large or restricted dataset downloads."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def accept(
        self,
        *,
        dataset_id: str,
        user: str = "",
        consent_text: str = "",
        accepted_terms: list[str] | None = None,
    ) -> DatasetConsentRecord:
        now = utc_now_iso()
        record = DatasetConsentRecord(
            id=f"dataset-consent-{dataset_id}-{now.replace(':', '').replace('-', '')}",
            dataset_id=dataset_id,
            user=user or os.environ.get("USER", "unknown"),
            consent_text=consent_text or "User accepted dataset download/license terms for this GapForge workspace.",
            accepted_terms=accepted_terms or [],
            accepted_at=now,
            provenance=Provenance(
                created_by_skill="dataset-consent",
                source_ids=[dataset_id],
                timestamp=now,
                reasoning_summary="Recorded explicit dataset download consent. Consent is audit metadata, not a license guarantee.",
            ),
        )
        self._consent_dir().mkdir(parents=True, exist_ok=True)
        (self._consent_dir() / f"{record.id}.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        return record

    def has_consent(self, dataset_id: str) -> bool:
        return bool(self.list_consents(dataset_id))

    def list_consents(self, dataset_id: str = "") -> list[DatasetConsentRecord]:
        if not self._consent_dir().exists():
            return []
        records = [
            from_dict(DatasetConsentRecord, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._consent_dir().glob("dataset-consent-*.json"))
        ]
        if dataset_id:
            return [record for record in records if record.dataset_id == dataset_id]
        return records

    def _consent_dir(self) -> Path:
        return dataset_cache_dir(self.config) / "consent"


def render_dataset_consent_markdown(record: DatasetConsentRecord) -> str:
    return "\n".join(
        [
            f"# Dataset Consent `{record.id}`",
            "",
            f"- Dataset ID: `{record.dataset_id}`",
            f"- User: {record.user}",
            f"- Accepted at: {record.accepted_at}",
            f"- Accepted terms: {', '.join(record.accepted_terms) or 'not specified'}",
            "",
            record.consent_text,
            "",
        ]
    )
