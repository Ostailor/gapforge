"""Style corpus ingestion for TeX sources."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.state import slugify, utc_now_iso
from gapforge.style_corpus.license_check import check_tex_license
from gapforge.style_corpus.style_features import StyleCorpusPaper, render_style_corpus_report
from gapforge.style_corpus.tex_parser import parse_tex_file
from gapforge.venues.profiles import get_venue_profile


@dataclass(slots=True)
class StyleCorpusIngestRecord:
    id: str
    source: str
    status: str
    papers_ingested: list[str] = field(default_factory=list)
    rejected_sources: list[str] = field(default_factory=list)
    license_warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="style-corpus-ingest"))


class StyleCorpusManager:
    """Ingest public or allowed TeX sources as structural features only."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()

    def add_tex(self, path: str | Path, venue: str, *, source_url: str = "", year: int = 0) -> StyleCorpusIngestRecord:
        profile = get_venue_profile(venue)
        source_path = Path(path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"No TeX source found at {source_path}")
        license_check = check_tex_license(source_path, source_url=source_url)
        if license_check.status == "restricted":
            record = StyleCorpusIngestRecord(
                id=_unique_ingest_id(self._records_dir(), "style-corpus-ingest-rejected"),
                source=str(source_path),
                status="rejected",
                rejected_sources=[str(source_path)],
                license_warnings=license_check.warnings,
                provenance=_provenance("style-corpus-add-tex", [str(source_path), profile.id], "Rejected restricted TeX source."),
            )
            self._write_ingest_record(record)
            return record
        features = parse_tex_file(source_path)
        paper = StyleCorpusPaper(
            id=_unique_paper_id(self._papers_dir(), features["title"], source_path),
            title=features["title"],
            venue=profile.id,
            year=year,
            source_url=source_url,
            local_source_path=str(source_path),
            license_status=license_check.status,
            section_titles=features["section_titles"],
            macro_summary=features["macro_summary"],
            environment_summary=features["environment_summary"],
            citation_density=features["citation_density"],
            figure_table_counts=features["figure_table_counts"],
            abstract_length=features["abstract_length"],
            contribution_statement_patterns=features["contribution_statement_patterns"],
            limitations_presence=features["limitations_presence"],
            provenance=_provenance(
                "style-corpus-add-tex",
                [str(source_path), profile.id],
                "Extracted structural TeX style features only; source prose was not stored.",
            ),
        )
        self._write_paper(paper)
        record = StyleCorpusIngestRecord(
            id=_unique_ingest_id(self._records_dir(), "style-corpus-ingest"),
            source=str(source_path),
            status="complete" if license_check.status == "allowed" else "warning",
            papers_ingested=[paper.id],
            license_warnings=license_check.warnings,
            provenance=_provenance(
                "style-corpus-add-tex",
                [str(source_path), paper.id, profile.id],
                "Ingested a TeX source into the style corpus as structural features only.",
            ),
        )
        self._write_ingest_record(record)
        self._write_report()
        return record

    def ingest_source(self, source: str, *, dry_run: bool = False) -> StyleCorpusIngestRecord:
        if dry_run:
            record = StyleCorpusIngestRecord(
                id=_unique_ingest_id(self._records_dir(), f"style-corpus-ingest-{source}"),
                source=source,
                status="dry_run",
                license_warnings=["Dry run only: remote TeX source ingestion must verify license before storing any structural features."],
                provenance=_provenance(
                    "style-corpus-ingest",
                    [source],
                    "Dry-run checked a remote style corpus source without downloading or storing paper source.",
                ),
            )
            self._write_ingest_record(record)
            return record
        record = StyleCorpusIngestRecord(
            id=_unique_ingest_id(self._records_dir(), f"style-corpus-ingest-{source}"),
            source=source,
            status="rejected",
            rejected_sources=[source],
            license_warnings=["Remote ingestion is disabled unless source licenses are explicitly verified."],
            provenance=_provenance("style-corpus-ingest", [source], "Rejected non-dry-run remote ingestion without license verification."),
        )
        self._write_ingest_record(record)
        return record

    def list_papers(self) -> list[StyleCorpusPaper]:
        return [
            from_dict(StyleCorpusPaper, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._papers_dir().glob("style-paper-*.json"))
        ]

    def list_ingest_records(self) -> list[StyleCorpusIngestRecord]:
        return [
            from_dict(StyleCorpusIngestRecord, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._records_dir().glob("style-corpus-ingest*.json"))
        ]

    def render_report(self) -> str:
        return self._write_report()

    def _write_paper(self, paper: StyleCorpusPaper) -> None:
        self._papers_dir().mkdir(parents=True, exist_ok=True)
        (self._papers_dir() / f"{paper.id}.json").write_text(json.dumps(to_plain(paper), indent=2) + "\n", encoding="utf-8")

    def _write_ingest_record(self, record: StyleCorpusIngestRecord) -> None:
        self._records_dir().mkdir(parents=True, exist_ok=True)
        (self._records_dir() / f"{record.id}.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")

    def _write_report(self) -> str:
        ingest_sections = [_render_ingest_record(record) for record in self.list_ingest_records()]
        report = render_style_corpus_report(self.list_papers(), ingest_sections)
        (self._root_dir() / "style_corpus_report.md").write_text(report, encoding="utf-8")
        return report

    def _root_dir(self) -> Path:
        path = self.config.data_dir / "style_corpus"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _papers_dir(self) -> Path:
        path = self._root_dir() / "papers"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _records_dir(self) -> Path:
        path = self._root_dir() / "ingest_records"
        path.mkdir(parents=True, exist_ok=True)
        return path


def _render_ingest_record(record: StyleCorpusIngestRecord) -> str:
    lines = [
        f"### `{record.id}`",
        "",
        f"- Source: {record.source}",
        f"- Status: `{record.status}`",
        f"- Papers ingested: {', '.join(record.papers_ingested) if record.papers_ingested else 'none'}",
        f"- Rejected sources: {', '.join(record.rejected_sources) if record.rejected_sources else 'none'}",
    ]
    if record.license_warnings:
        lines.extend(["", "License warnings:", "", *[f"- {warning}" for warning in record.license_warnings]])
    return "\n".join(lines).rstrip()


def _provenance(skill: str, source_ids: list[str], summary: str) -> Provenance:
    return Provenance(created_by_skill=skill, source_ids=source_ids, timestamp=utc_now_iso(), reasoning_summary=summary)


def _unique_paper_id(papers_dir: Path, title: str, path: Path) -> str:
    base = f"style-paper-{slugify(title or path.stem)}"
    digest = hashlib.sha1(f"{title}:{path}".encode()).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (papers_dir / f"{candidate}.json").exists():
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate


def _unique_ingest_id(records_dir: Path, source: str) -> str:
    digest = hashlib.sha1(f"{source}:{utc_now_iso()}".encode()).hexdigest()[:6]
    candidate = f"{slugify(source)}-{digest}"
    suffix = 2
    while (records_dir / f"{candidate}.json").exists():
        candidate = f"{slugify(source)}-{digest}-{suffix}"
        suffix += 1
    return candidate
