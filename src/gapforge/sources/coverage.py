"""Search query ledger and source coverage reporting."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

from gapforge.models import ResearchRunState, SearchQueryRecord, SourceCoverageReport


def add_search_query_record(
    state: ResearchRunState,
    *,
    query: str,
    source_names: list[str],
    purpose: str,
    max_results: int,
    date_from: str | None,
    date_to: str | None,
    result_paper_ids: list[str],
    failure_messages: list[str],
) -> SearchQueryRecord:
    record = SearchQueryRecord(
        id=f"query-{len(state.search_queries) + 1:04d}",
        query=query,
        source_names=source_names,
        purpose=purpose,
        max_results=max_results,
        date_from=date_from or "",
        date_to=date_to or "",
        executed_at=_utc_now_iso(),
        result_paper_ids=_dedupe(result_paper_ids),
        failure_messages=list(failure_messages),
    )
    state.search_queries.append(record)
    return record


def refresh_source_coverage(state: ResearchRunState, warnings: list[str] | None = None) -> SourceCoverageReport:
    report = generate_source_coverage(state, extra_warnings=warnings or [])
    state.source_coverage = report
    return report


def generate_source_coverage(state: ResearchRunState, *, extra_warnings: list[str] | None = None) -> SourceCoverageReport:
    papers_by_source = Counter(paper.source or "unknown" for paper in state.papers)
    query_sources = {source for record in state.search_queries for source in record.source_names if source}
    paper_sources = {source for source in papers_by_source if source != "unknown"}
    failed_sources = _failed_sources(state.search_queries)
    fallback_papers = [paper for paper in state.papers if _is_fallback_paper(paper)]
    papers_with_pdf = sorted(
        {paper.id for paper in state.papers if paper.pdf_url}
        | {artifact.paper_id for artifact in state.paper_artifacts if artifact.artifact_type == "pdf" and artifact.status == "available"}
    )
    papers_with_full_text = sorted({section.paper_id for section in state.paper_sections if section.text.strip()})
    abstract_only = sorted({note.paper_id for note in state.paper_notes if note.source_basis == "metadata/abstract only"})
    if not abstract_only:
        abstract_only = sorted({paper.id for paper in state.papers if paper.id not in papers_with_full_text})
    failed_downloads = sorted(
        artifact.id for artifact in state.paper_artifacts if artifact.artifact_type == "pdf" and artifact.status == "failed"
    )
    warnings = _coverage_warnings(
        state,
        fallback_count=len(fallback_papers),
        failed_sources=failed_sources,
        full_text_count=len(papers_with_full_text),
        abstract_only_count=len(abstract_only),
        extra_warnings=extra_warnings or [],
    )
    return SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=sorted(query_sources | paper_sources),
        query_records=list(state.search_queries),
        papers_by_source=dict(sorted(papers_by_source.items())),
        papers_with_pdf=papers_with_pdf,
        papers_with_full_text=papers_with_full_text,
        papers_abstract_only=abstract_only,
        failed_downloads=failed_downloads,
        failed_sources=failed_sources,
        fallback_paper_count=len(fallback_papers),
        missing_source_types=_missing_source_types(query_sources | paper_sources),
        coverage_warnings=warnings,
        confidence=_coverage_confidence(state, len(papers_with_full_text), len(fallback_papers), failed_sources),
    )


def render_source_coverage_markdown(report: SourceCoverageReport) -> str:
    lines = [
        f"# Source Coverage: {report.topic}",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Confidence: {report.confidence}",
        f"- Sources searched: {', '.join(report.searched_sources) if report.searched_sources else 'none'}",
        f"- Failed sources: {', '.join(report.failed_sources) if report.failed_sources else 'none'}",
        f"- Papers retrieved: {sum(report.papers_by_source.values())}",
        f"- Papers with PDFs: {len(report.papers_with_pdf)}",
        f"- Papers with parsed full text: {len(report.papers_with_full_text)}",
        f"- Abstract-only papers: {len(report.papers_abstract_only)}",
        f"- Fallback/offline papers: {report.fallback_paper_count}",
        "",
        "## Queries",
        "",
    ]
    for record in report.query_records:
        lines.extend(
            [
                f"- `{record.id}` {record.purpose}: {record.query}",
                f"  - Sources: {', '.join(record.source_names) if record.source_names else 'none'}",
                f"  - Max results: {record.max_results}",
                f"  - Results: {len(record.result_paper_ids)}",
                f"  - Failures: {len(record.failure_messages)}",
            ]
        )
    if not report.query_records:
        lines.append("- none")
    lines.extend(["", "## Papers By Source", ""])
    lines.extend([f"- {source}: {count}" for source, count in sorted(report.papers_by_source.items())] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in report.coverage_warnings] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _failed_sources(records: list[SearchQueryRecord]) -> list[str]:
    failed: set[str] = set()
    for record in records:
        for message in record.failure_messages:
            match = re.match(r"([^ ]+) search failed", message)
            if match:
                failed.add(match.group(1))
            else:
                failed.add(message.split(":", 1)[0])
    return sorted(failed)


def _is_fallback_paper(paper) -> bool:
    return bool(paper.raw_metadata.get("fallback")) or "fallback" in paper.provenance.reasoning_summary.lower()


def _coverage_warnings(
    state: ResearchRunState,
    *,
    fallback_count: int,
    failed_sources: list[str],
    full_text_count: int,
    abstract_only_count: int,
    extra_warnings: list[str],
) -> list[str]:
    warnings = list(extra_warnings)
    warnings.extend(failure for record in state.search_queries for failure in record.failure_messages)
    if fallback_count:
        warnings.append(f"{fallback_count} paper(s) are deterministic fallback/offline records, not verified literature metadata.")
    if state.papers and fallback_count == len(state.papers):
        warnings.append("All papers are fallback/offline records; treat this run as a smoke test, not a literature conclusion.")
    if state.papers and full_text_count == 0:
        warnings.append("No parsed full text is available; conclusions are metadata/abstract-heavy.")
    if state.papers and abstract_only_count >= max(1, int(len(state.papers) * 0.75)):
        warnings.append("Most papers are abstract-only; evidence coverage is weak.")
    if failed_sources:
        warnings.append(f"One or more sources failed during search: {', '.join(failed_sources)}.")
    if state.config.get("source_mode") == "deterministic-fake":
        warnings.append("Run configuration indicates deterministic fake/offline source mode.")
    return _dedupe(warnings)


def _coverage_confidence(
    state: ResearchRunState,
    full_text_count: int,
    fallback_count: int,
    failed_sources: list[str],
) -> str:
    if not state.papers or fallback_count == len(state.papers):
        return "low"
    if not state.search_queries or failed_sources:
        return "low"
    if full_text_count >= max(1, len(state.papers) // 2):
        return "high"
    return "medium"


def _missing_source_types(seen_sources: set[str]) -> list[str]:
    normalized = {source.lower().replace(" ", "-") for source in seen_sources}
    expected = {"arxiv", "crossref", "dblp", "openreview", "semantic-scholar"}
    return sorted(expected - normalized)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
