"""Live source health checks for real literature campaign readiness."""

from __future__ import annotations

import os
import time
from collections.abc import Iterable

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, SourceHealthCheck, to_plain
from gapforge.sources.arxiv_source import ArxivSource
from gapforge.sources.base import ResearchSource
from gapforge.sources.crossref_source import CrossrefSource
from gapforge.sources.dblp_source import DblpSource
from gapforge.sources.http_client import CachedHttpClient
from gapforge.sources.openreview_source import OpenReviewSource
from gapforge.sources.semantic_scholar_source import SemanticScholarSource
from gapforge.sources.web_source import WebSource
from gapforge.state import slugify, utc_now_iso

DEFAULT_HEALTH_QUERY = "machine learning survey"


def default_health_sources(config: GapForgeConfig) -> list[ResearchSource]:
    """Return built-in sources for health probing."""

    http = CachedHttpClient(config.cache_dir)
    return [
        ArxivSource(http),
        CrossrefSource(http),
        DblpSource(http),
        OpenReviewSource(http),
        SemanticScholarSource(http),
        WebSource(),
    ]


def source_name_key(name: str) -> str:
    """Normalize source names for policy/profile matching."""

    key = slugify(name).replace("_", "-")
    aliases = {
        "semantic-scholar": "semantic-scholar",
        "semanticscholar": "semantic-scholar",
        "s2": "semantic-scholar",
        "arxiv": "arxiv",
        "ar-xiv": "arxiv",
        "openreview": "openreview",
        "open-review": "openreview",
        "crossref": "crossref",
        "cross-ref": "crossref",
        "dblp": "dblp",
        "db-lp": "dblp",
        "web": "web",
        "pubmed": "pubmed",
    }
    return aliases.get(key, key)


def source_display_name(name: str) -> str:
    mapping = {
        "arxiv": "arXiv",
        "openreview": "OpenReview",
        "semantic-scholar": "Semantic Scholar",
        "crossref": "Crossref",
        "dblp": "DBLP",
        "web": "Web",
        "pubmed": "PubMed",
    }
    return mapping.get(source_name_key(name), name)


def source_map(config: GapForgeConfig, sources: Iterable[ResearchSource] | None = None) -> dict[str, ResearchSource]:
    return {source_name_key(source.name): source for source in (list(sources) if sources is not None else default_health_sources(config))}


def check_source_health(
    source: ResearchSource,
    *,
    test_query: str = DEFAULT_HEALTH_QUERY,
    max_results: int = 3,
) -> SourceHealthCheck:
    """Probe one source with a tiny query and classify real usefulness."""

    checked_at = utc_now_iso()
    provenance = _health_provenance(source.name, checked_at, "Checked source reachability with a small query.")
    if os.environ.get("GAPFORGE_DISABLE_NETWORK") == "1":
        return SourceHealthCheck(
            source_name=source.name,
            status="disabled",
            test_query=test_query,
            checked_at=checked_at,
            warning="Network disabled by GAPFORGE_DISABLE_NETWORK=1; live source readiness cannot be validated.",
            provenance=provenance,
        )

    start = time.perf_counter()
    try:
        papers = source.search(test_query, max_results=max_results, sort="relevance", date_from=None, date_to=None)
    except Exception as exc:  # pragma: no cover - exercised through tests with fake source
        return SourceHealthCheck(
            source_name=source.name,
            status="unavailable",
            test_query=test_query,
            latency_ms=_elapsed_ms(start),
            error=str(exc),
            checked_at=checked_at,
            provenance=provenance,
        )

    latency_ms = _elapsed_ms(start)
    result_count = len(papers)
    fallback_count = sum(1 for paper in papers if _is_fallback_paper(paper))
    if result_count == 0:
        return SourceHealthCheck(
            source_name=source.name,
            status="degraded",
            test_query=test_query,
            result_count=0,
            latency_ms=latency_ms,
            warning="Source returned no results for the health query.",
            checked_at=checked_at,
            provenance=provenance,
        )
    if fallback_count == result_count:
        return SourceHealthCheck(
            source_name=source.name,
            status="degraded",
            test_query=test_query,
            result_count=result_count,
            latency_ms=latency_ms,
            warning="Source returned only fallback metadata; this is not sufficient for live-literature validation.",
            checked_at=checked_at,
            provenance=provenance,
        )
    if fallback_count:
        return SourceHealthCheck(
            source_name=source.name,
            status="degraded",
            test_query=test_query,
            result_count=result_count,
            latency_ms=latency_ms,
            warning=f"Source returned {fallback_count} fallback result(s) mixed with live metadata.",
            checked_at=checked_at,
            provenance=provenance,
        )
    return SourceHealthCheck(
        source_name=source.name,
        status="healthy",
        test_query=test_query,
        result_count=result_count,
        latency_ms=latency_ms,
        checked_at=checked_at,
        provenance=provenance,
    )


def check_source_by_name(
    config: GapForgeConfig,
    source_name: str,
    *,
    test_query: str = DEFAULT_HEALTH_QUERY,
    max_results: int = 3,
    sources: Iterable[ResearchSource] | None = None,
) -> SourceHealthCheck:
    sources_by_name = source_map(config, sources)
    key = source_name_key(source_name)
    if key not in sources_by_name:
        checked_at = utc_now_iso()
        return SourceHealthCheck(
            source_name=source_display_name(source_name),
            status="unavailable",
            test_query=test_query,
            error="No GapForge connector is configured for this source.",
            checked_at=checked_at,
            provenance=_health_provenance(source_name, checked_at, "No connector exists for requested source."),
        )
    return check_source_health(sources_by_name[key], test_query=test_query, max_results=max_results)


def check_sources(
    config: GapForgeConfig,
    *,
    source_name: str | None = None,
    test_query: str = DEFAULT_HEALTH_QUERY,
    max_results: int = 3,
    sources: Iterable[ResearchSource] | None = None,
) -> list[SourceHealthCheck]:
    if source_name:
        return [check_source_by_name(config, source_name, test_query=test_query, max_results=max_results, sources=sources)]
    return [check_source_health(source, test_query=test_query, max_results=max_results) for source in source_map(config, sources).values()]


def write_source_health_artifacts(
    config: GapForgeConfig, checks: list[SourceHealthCheck], *, stem: str = "source_health_latest"
) -> tuple[str, str]:
    out_dir = config.data_dir / "source_health"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    import json

    json_path.write_text(json.dumps([to_plain(check) for check in checks], indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_source_health_markdown(checks), encoding="utf-8")
    return str(json_path), str(md_path)


def render_source_health_markdown(checks: list[SourceHealthCheck]) -> str:
    lines = ["# Source Health", ""]
    if not checks:
        lines.append("No source health checks were run.")
        return "\n".join(lines) + "\n"
    lines.extend(["| Source | Status | Results | Latency | Warning | Error |", "| --- | --- | ---: | ---: | --- | --- |"])
    for check in checks:
        lines.append(
            f"| {check.source_name} | {check.status} | {check.result_count} | {check.latency_ms} ms | "
            f"{check.warning or '-'} | {check.error or '-'} |"
        )
    lines.append("")
    if any(check.status in {"disabled", "unavailable"} for check in checks):
        lines.append(
            "Live-literature campaign validation is blocked or incomplete until unavailable/disabled required sources are addressed."
        )
    elif any(check.status == "degraded" for check in checks):
        lines.append("Some sources are degraded. A real-literature campaign may need fallback searches, retries, or explicit refusal.")
    else:
        lines.append("All checked sources returned live-looking results.")
    return "\n".join(lines).rstrip() + "\n"


def _is_fallback_paper(paper: Paper) -> bool:
    if bool(paper.raw_metadata.get("fallback")):
        return True
    return "fallback" in (paper.provenance.reasoning_summary or "").lower()


def _elapsed_ms(start: float) -> int:
    return max(0, int((time.perf_counter() - start) * 1000))


def _health_provenance(source_name: str, checked_at: str, summary: str) -> Provenance:
    return Provenance(
        created_by_skill="source-health",
        source_ids=[source_name],
        timestamp=checked_at,
        reasoning_summary=summary,
    )
