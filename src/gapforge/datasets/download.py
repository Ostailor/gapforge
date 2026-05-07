"""Explicit dataset download planning and execution."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.datasets.cache import dataset_cache_dir
from gapforge.datasets.consent import DatasetConsentManager
from gapforge.datasets.licenses import license_warnings, requires_terms_consent, url_requires_auth
from gapforge.datasets.registry import DatasetRegistry
from gapforge.models import DatasetDownloadPlan, DatasetDownloadRecord, DatasetRecord, Provenance, to_plain
from gapforge.state import slugify, utc_now_iso

DEFAULT_LARGE_DOWNLOAD_BYTES = 50 * 1024 * 1024


class DatasetDownloadManager:
    """Plan and execute explicit dataset downloads into an ignored cache."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.registry = DatasetRegistry(config)
        self.consent = DatasetConsentManager(config)

    def build_plan(self, dataset_id: str) -> DatasetDownloadPlan:
        record = self.registry.load_dataset(dataset_id)
        urls = _dataset_urls(record)
        estimated_size = _estimate_size(record, urls)
        destination = self._destination(record, urls)
        warnings = license_warnings(record.license)
        requires_auth = any(url_requires_auth(url) for url in urls)
        manual_required = _manual_required(record, urls, requires_auth)
        if not urls:
            warnings.append("No source URL is recorded; manual download instructions are required.")
        if requires_auth:
            warnings.append("Dataset source appears to require authentication or gated terms.")
        if manual_required:
            warnings.append("Manual download required: download the dataset outside GapForge and register the local path.")
        threshold = _large_download_threshold()
        large = estimated_size > threshold > 0
        if large:
            warnings.append(f"Estimated download size {estimated_size} bytes exceeds explicit-consent threshold {threshold} bytes.")
        consent_required = large or requires_auth or requires_terms_consent(record.license)
        return DatasetDownloadPlan(
            id=f"dataset-download-plan-{dataset_id}",
            dataset_id=dataset_id,
            urls=urls,
            estimated_size_bytes=estimated_size,
            license=record.license,
            requires_auth=requires_auth,
            requires_manual_download=manual_required,
            destination=str(destination),
            safety_warnings=warnings,
            consent_required=consent_required,
            provenance=Provenance(
                created_by_skill="dataset-download-plan",
                source_ids=[dataset_id, *urls],
                timestamp=utc_now_iso(),
                reasoning_summary="Planned dataset download without fetching network content.",
            ),
        )

    def download(self, dataset_id: str, *, accept_license: bool = False, user: str = "") -> DatasetDownloadRecord:
        plan = self.build_plan(dataset_id)
        record = self.registry.load_dataset(dataset_id)
        started = utc_now_iso()
        if plan.requires_manual_download:
            return self._write_record(
                DatasetDownloadRecord(
                    id=f"dataset-download-{dataset_id}-{_timestamp_id(started)}",
                    dataset_id=dataset_id,
                    status="manual_required",
                    local_path="",
                    started_at=started,
                    completed_at=utc_now_iso(),
                    error=(
                        "Manual download required. Register the downloaded local file with "
                        "`gapforge dataset-register` or update the dataset path."
                    ),
                    provenance=_download_provenance(dataset_id, plan, "manual-required"),
                )
            )
        if plan.consent_required and not (accept_license or self.consent.has_consent(dataset_id)):
            return self._write_record(
                DatasetDownloadRecord(
                    id=f"dataset-download-{dataset_id}-{_timestamp_id(started)}",
                    dataset_id=dataset_id,
                    status="skipped",
                    local_path="",
                    started_at=started,
                    completed_at=utc_now_iso(),
                    error="Explicit consent is required before downloading this dataset.",
                    provenance=_download_provenance(dataset_id, plan, "consent-required"),
                )
            )
        if accept_license:
            self.consent.accept(
                dataset_id=dataset_id,
                user=user,
                consent_text="User passed --accept-license for dataset download.",
                accepted_terms=[record.license or "unspecified license", *plan.urls],
            )
        destination = Path(plan.destination)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            _fetch_url(plan.urls[0], destination)
            sha256 = _sha256(destination)
            downloaded = destination.stat().st_size
            self.registry.update_local_path(dataset_id, destination)
            status = "downloaded"
            error = ""
        except Exception as exc:
            sha256 = ""
            downloaded = 0
            status = "failed"
            error = str(exc)
        return self._write_record(
            DatasetDownloadRecord(
                id=f"dataset-download-{dataset_id}-{_timestamp_id(started)}",
                dataset_id=dataset_id,
                status=status,
                local_path=str(destination) if status == "downloaded" else "",
                bytes_downloaded=downloaded,
                sha256=sha256,
                started_at=started,
                completed_at=utc_now_iso(),
                error=error,
                provenance=_download_provenance(dataset_id, plan, status),
            )
        )

    def _destination(self, record: DatasetRecord, urls: list[str]) -> Path:
        source = urls[0] if urls else record.local_path or record.name
        parsed = urllib.parse.urlparse(source)
        name = Path(parsed.path or source).name or f"{slugify(record.name)}.data"
        return dataset_cache_dir(self.config) / "downloads" / record.id / name

    def _write_record(self, record: DatasetDownloadRecord) -> DatasetDownloadRecord:
        records_dir = dataset_cache_dir(self.config) / "records"
        records_dir.mkdir(parents=True, exist_ok=True)
        (records_dir / f"{record.id}.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        return record


def render_dataset_download_plan(plan: DatasetDownloadPlan) -> str:
    lines = [
        f"# Dataset Download Plan `{plan.id}`",
        "",
        f"- Dataset ID: `{plan.dataset_id}`",
        f"- URLs: {', '.join(plan.urls) or 'none'}",
        f"- Estimated size: {plan.estimated_size_bytes} bytes",
        f"- License: {plan.license or 'unknown'}",
        f"- Requires auth: {str(plan.requires_auth).lower()}",
        f"- Requires manual download: {str(plan.requires_manual_download).lower()}",
        f"- Consent required: {str(plan.consent_required).lower()}",
        f"- Destination: `{plan.destination}`",
        "",
        "## Safety Warnings",
        "",
    ]
    lines.extend([f"- {item}" for item in plan.safety_warnings] or ["- none"])
    if plan.requires_manual_download:
        lines.extend(
            [
                "",
                "## Manual Download Instructions",
                "",
                "Download the dataset through the provider-approved workflow, then register or update the dataset with the local path.",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_dataset_download_record(record: DatasetDownloadRecord) -> str:
    return "\n".join(
        [
            f"# Dataset Download `{record.id}`",
            "",
            f"- Dataset ID: `{record.dataset_id}`",
            f"- Status: `{record.status}`",
            f"- Local path: `{record.local_path or 'none'}`",
            f"- Bytes downloaded: {record.bytes_downloaded}",
            f"- SHA256: `{record.sha256 or 'none'}`",
            f"- Started: {record.started_at or 'unknown'}",
            f"- Completed: {record.completed_at or 'unknown'}",
            f"- Error: {record.error or 'none'}",
            "",
        ]
    )


def _dataset_urls(record: DatasetRecord) -> list[str]:
    if not record.source_url:
        return []
    return [item.strip() for item in record.source_url.replace("\n", ",").split(",") if item.strip()]


def _estimate_size(record: DatasetRecord, urls: list[str]) -> int:
    for raw in [*urls, record.local_path]:
        path = _local_path_from_url(raw)
        if path is not None and path.exists():
            return path.stat().st_size
    return 0


def _manual_required(record: DatasetRecord, urls: list[str], requires_auth: bool) -> bool:
    text = " ".join([record.source, record.source_url, record.license]).lower()
    return not urls or requires_auth or "manual" in text or "restricted" in text


def _fetch_url(url: str, destination: Path) -> None:
    local = _local_path_from_url(url)
    if local is not None:
        shutil.copyfile(local, destination)
        return
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported dataset URL scheme: {parsed.scheme or 'none'}")
    with urllib.request.urlopen(url, timeout=30) as response, destination.open("wb") as handle:  # noqa: S310
        shutil.copyfileobj(response, handle)


def _local_path_from_url(raw: str) -> Path | None:
    if not raw:
        return None
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme == "file":
        return Path(urllib.request.url2pathname(parsed.path))
    if parsed.scheme == "" and Path(raw).exists():
        return Path(raw)
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _large_download_threshold() -> int:
    raw = os.environ.get("GAPFORGE_DATASET_LARGE_DOWNLOAD_BYTES", str(DEFAULT_LARGE_DOWNLOAD_BYTES))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_LARGE_DOWNLOAD_BYTES


def _timestamp_id(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace(".", "")


def _download_provenance(dataset_id: str, plan: DatasetDownloadPlan, status: str) -> Provenance:
    return Provenance(
        created_by_skill="dataset-download",
        source_ids=[dataset_id, plan.id, *plan.urls],
        timestamp=utc_now_iso(),
        reasoning_summary=(
            f"Dataset download finished with status `{status}`. Downloaded data remains cache-managed and unsafe to commit by default."
        ),
    )
