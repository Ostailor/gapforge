"""Aggregate live source diagnostics for real literature campaigns."""

from __future__ import annotations

import json
from collections.abc import Iterable

from gapforge.config import GapForgeConfig
from gapforge.models import LiveSourceDiagnostic, Provenance, SourceHealthCheck, to_plain
from gapforge.sources.base import ResearchSource
from gapforge.sources.health import check_source_by_name, source_display_name, source_name_key
from gapforge.sources.policies import get_source_policy_profile
from gapforge.state import slugify, utc_now_iso


def run_live_source_diagnostic(
    config: GapForgeConfig,
    *,
    topic: str,
    source_profile: str = "generic",
    sources: Iterable[ResearchSource] | None = None,
    max_results: int = 3,
) -> LiveSourceDiagnostic:
    """Check required/recommended sources for a topic and source policy."""

    profile = get_source_policy_profile(source_profile)
    required = [source_name_key(name) for name in profile.required_sources]
    recommended = [source_name_key(name) for name in profile.recommended_sources]
    names = _dedupe(required + recommended)
    checks = [
        _check_source_with_profile_fallback(
            config,
            name,
            topic_query=_health_query(topic, profile.must_include_query_patterns),
            fallback_query=_profile_health_query(profile.id, topic),
            max_results=max_results,
            sources=sources,
        )
        for name in names
    ]
    by_key = {source_name_key(check.source_name): check for check in checks}
    usable = [check.source_name for check in checks if check.status == "healthy"]
    degraded = [check.source_name for check in checks if check.status == "degraded"]
    unavailable = [check.source_name for check in checks if check.status in {"unavailable", "disabled"}]
    blocking: list[str] = []
    for required_name in required:
        check = by_key.get(required_name)
        if check is None:
            blocking.append(f"Required source {source_display_name(required_name)} was not checked.")
        elif check.status != "healthy":
            blocking.append(f"Required source {check.source_name} is {check.status}: {_status_detail(check)}")
    if not usable:
        blocking.append("No checked source returned live-looking non-fallback results.")
    recommended_fallbacks = _recommended_fallbacks(checks)
    checked_at = utc_now_iso()
    return LiveSourceDiagnostic(
        id=f"live-source-diagnostic-{slugify(source_profile)}-{slugify(topic)[:40]}",
        topic=topic,
        source_profile=profile.id,
        source_health_checks=checks,
        usable_sources=usable,
        degraded_sources=degraded,
        unavailable_sources=unavailable,
        minimum_coverage_met=not blocking,
        recommended_fallbacks=recommended_fallbacks,
        blocking_issues=blocking,
        provenance=Provenance(
            created_by_skill="live-source-diagnostic",
            source_ids=[profile.id],
            timestamp=checked_at,
            reasoning_summary="Checked live source readiness against a field-specific source policy profile.",
        ),
    )


def write_live_source_diagnostic(config: GapForgeConfig, diagnostic: LiveSourceDiagnostic) -> tuple[str, str]:
    out_dir = config.data_dir / "source_health"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{diagnostic.id}-{utc_now_iso().replace(':', '').replace('+', 'Z')}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    latest_json = out_dir / "live_source_diagnostic_latest.json"
    latest_md = out_dir / "live_source_diagnostic_latest.md"
    payload = json.dumps(to_plain(diagnostic), indent=2) + "\n"
    rendered = render_live_source_diagnostic_markdown(diagnostic)
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(rendered, encoding="utf-8")
    latest_json.write_text(payload, encoding="utf-8")
    latest_md.write_text(rendered, encoding="utf-8")
    return str(latest_json), str(latest_md)


def render_live_source_diagnostic_markdown(diagnostic: LiveSourceDiagnostic) -> str:
    lines = [
        f"# Live Source Diagnostic: {diagnostic.topic}",
        "",
        f"- Source profile: `{diagnostic.source_profile}`",
        f"- Minimum coverage met: {str(diagnostic.minimum_coverage_met).lower()}",
        f"- Usable sources: {', '.join(diagnostic.usable_sources) or 'none'}",
        f"- Degraded sources: {', '.join(diagnostic.degraded_sources) or 'none'}",
        f"- Unavailable sources: {', '.join(diagnostic.unavailable_sources) or 'none'}",
        "",
        "## Source Checks",
        "",
        "| Source | Status | Results | Latency | Warning | Error |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for check in diagnostic.source_health_checks:
        lines.append(
            f"| {check.source_name} | {check.status} | {check.result_count} | {check.latency_ms} ms | "
            f"{check.warning or '-'} | {check.error or '-'} |"
        )
    lines.extend(["", "## Blocking Issues", ""])
    lines.extend([f"- {issue}" for issue in diagnostic.blocking_issues] or ["- none"])
    lines.extend(["", "## Recommended Fallbacks", ""])
    lines.extend([f"- {item}" for item in diagnostic.recommended_fallbacks] or ["- none"])
    if not diagnostic.minimum_coverage_met:
        lines.extend(
            [
                "",
                "Real-literature campaign validation should not be claimed until blocking source issues are resolved "
                "or the campaign refuses recommendation because coverage is insufficient.",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _health_query(topic: str, patterns: list[str]) -> str:
    if patterns:
        return f"{topic} {patterns[0]}".strip()
    return topic.strip() or "machine learning survey"


def _check_source_with_profile_fallback(
    config: GapForgeConfig,
    source_name: str,
    *,
    topic_query: str,
    fallback_query: str,
    max_results: int,
    sources: Iterable[ResearchSource] | None,
) -> SourceHealthCheck:
    check = check_source_by_name(config, source_name, test_query=topic_query, max_results=max_results, sources=sources)
    if check.status != "degraded" or check.result_count != 0 or not fallback_query or fallback_query == topic_query:
        return check
    retry = check_source_by_name(config, source_name, test_query=fallback_query, max_results=max_results, sources=sources)
    if retry.status == "healthy":
        retry.warning = (
            f"Topic-specific health query returned no results (`{topic_query}`); "
            f"source reachability was verified with broader profile query (`{fallback_query}`)."
        )
        return retry
    return check


def _profile_health_query(profile_id: str, topic: str) -> str:
    profile_queries = {
        "ai_safety": "AI safety large language model agents evaluation survey",
        "machine_learning": "machine learning benchmark survey",
        "multi_agent_systems": "multi-agent systems game theory survey",
        "medicine": "medical screening specificity systematic review",
        "cybersecurity": "cybersecurity threat model benchmark survey",
        "economics": "cartel detection empirical survey",
        "biology": "biology dataset protocol review",
        "physics": "physics experiment review",
        "generic": "machine learning survey",
    }
    return profile_queries.get(profile_id, topic.strip() or "machine learning survey")


def _recommended_fallbacks(checks: list[SourceHealthCheck]) -> list[str]:
    fallbacks: list[str] = []
    for check in checks:
        if check.status == "disabled":
            fallbacks.append("Unset GAPFORGE_DISABLE_NETWORK for release-validation runs, or record the campaign as offline smoke only.")
        elif check.status == "unavailable":
            fallbacks.append(
                f"Retry {check.source_name}, check network/API status, or record source unavailability before refusing recommendation."
            )
        elif check.status == "degraded":
            fallbacks.append(
                f"Do not count {check.source_name} fallback-only results as live literature; retry or use another source family."
            )
    return _dedupe(fallbacks)


def _status_detail(check: SourceHealthCheck) -> str:
    detail = check.warning or check.error or "not healthy"
    return detail if detail.endswith((".", "!", "?")) else f"{detail}."


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
