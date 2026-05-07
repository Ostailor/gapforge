"""Section helpers for manuscript projects."""

from __future__ import annotations

from pathlib import Path

from gapforge.manuscript.models import MANUSCRIPT_SECTION_STATUSES, MANUSCRIPT_SECTION_TYPES, ManuscriptSection
from gapforge.models import Provenance
from gapforge.state import slugify, utc_now_iso

SECTION_TITLES = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "related_work": "Related Work",
    "method": "Method",
    "experiments": "Experiments",
    "results": "Results",
    "limitations": "Limitations",
    "ethics": "Ethics",
    "conclusion": "Conclusion",
    "appendix": "Appendix",
}


def validate_section_type(section_type: str) -> str:
    if section_type not in MANUSCRIPT_SECTION_TYPES:
        allowed = ", ".join(sorted(MANUSCRIPT_SECTION_TYPES))
        raise ValueError(f"Unsupported manuscript section type: {section_type}. Expected one of: {allowed}")
    return section_type


def validate_section_status(status: str) -> str:
    if status not in MANUSCRIPT_SECTION_STATUSES:
        allowed = ", ".join(sorted(MANUSCRIPT_SECTION_STATUSES))
        raise ValueError(f"Unsupported manuscript section status: {status}. Expected one of: {allowed}")
    return status


def default_section_title(section_type: str) -> str:
    return SECTION_TITLES.get(validate_section_type(section_type), section_type.replace("_", " ").title())


def next_section_id(existing: list[ManuscriptSection], section_type: str) -> str:
    base = slugify(section_type)
    ids = {section.id for section in existing}
    candidate = base
    suffix = 2
    while candidate in ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def build_section(
    *,
    manuscript_id: str,
    section_id: str,
    section_type: str,
    title: str = "",
    status: str = "missing",
    source_claim_ids: list[str] | None = None,
    source_paper_ids: list[str] | None = None,
    source_result_ids: list[str] | None = None,
    source_artifact_ids: list[str] | None = None,
    warnings: list[str] | None = None,
) -> ManuscriptSection:
    now = utc_now_iso()
    normalized_type = validate_section_type(section_type)
    normalized_status = validate_section_status(status)
    return ManuscriptSection(
        id=section_id,
        manuscript_id=manuscript_id,
        section_type=normalized_type,
        title=title or default_section_title(normalized_type),
        content_path=str(Path("sections") / f"{section_id}.md"),
        source_claim_ids=_unique(source_claim_ids or []),
        source_paper_ids=_unique(source_paper_ids or []),
        source_result_ids=_unique(source_result_ids or []),
        source_artifact_ids=_unique(source_artifact_ids or []),
        status=normalized_status,
        warnings=_unique(warnings or []),
        provenance=Provenance(
            created_by_skill="manuscript-section",
            source_ids=[manuscript_id, *_unique(source_claim_ids or []), *_unique(source_paper_ids or [])],
            timestamp=now,
            reasoning_summary="Created a manuscript section that references evidence state by ID.",
        ),
    )


def render_section_stub(section: ManuscriptSection) -> str:
    lines = [
        f"# {section.title}",
        "",
        "<!-- Manuscript section draft. Keep claims traceable through manuscript.json. -->",
        "",
        f"- Section type: `{section.section_type}`",
        f"- Status: `{section.status}`",
        f"- Source claims: {', '.join(section.source_claim_ids) if section.source_claim_ids else 'none'}",
        f"- Source papers: {', '.join(section.source_paper_ids) if section.source_paper_ids else 'none'}",
        f"- Source results: {', '.join(section.source_result_ids) if section.source_result_ids else 'none'}",
        f"- Source artifacts: {', '.join(section.source_artifact_ids) if section.source_artifact_ids else 'none'}",
        "",
    ]
    if section.warnings:
        lines.append("## Warnings")
        lines.append("")
        lines.extend(f"- {warning}" for warning in section.warnings)
        lines.append("")
    return "\n".join(lines)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
