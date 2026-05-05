"""Baseline candidate extraction and rendering."""

from __future__ import annotations

from gapforge.models import BaselineCandidate, Paper, Provenance, RelatedWorkMatrix
from gapforge.state import utc_now_iso


def baseline_candidates_from_matrix(matrix: RelatedWorkMatrix, papers: list[Paper]) -> list[BaselineCandidate]:
    paper_by_id = {paper.id: paper for paper in papers}
    candidates: list[BaselineCandidate] = []
    for entry in matrix.entries:
        if not entry.baseline_candidate:
            continue
        paper = paper_by_id.get(entry.paper_id)
        code_url = _code_url(paper)
        candidates.append(
            BaselineCandidate(
                paper_id=entry.paper_id,
                baseline_name=_baseline_name(paper, entry.paper_id),
                implementation_available=bool(code_url),
                code_url=code_url,
                why_required=entry.what_it_contributes or f"{entry.relationship} prior work should be compared.",
                risk_if_missing=entry.reviewer_risk_if_omitted
                or "Reviewer may object that a relevant baseline or dataset provider was omitted.",
                provenance=Provenance(
                    created_by_skill="experiment-protocol",
                    source_ids=[matrix.direction_id, entry.paper_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Baseline candidate selected from related-work matrix.",
                ),
            )
        )
    return _dedupe_candidates(candidates)


def baseline_candidates_from_strings(baselines: list[str]) -> list[BaselineCandidate]:
    return [
        BaselineCandidate(
            paper_id="",
            baseline_name=baseline,
            implementation_available=False,
            why_required="Baseline named by experiment plan.",
            risk_if_missing="Removing this baseline weakens empirical interpretation.",
            provenance=Provenance(
                created_by_skill="experiment-protocol",
                timestamp=utc_now_iso(),
                reasoning_summary="Baseline candidate converted from an existing experiment plan baseline string.",
            ),
        )
        for baseline in baselines
    ]


def has_strong_baseline(candidates: list[BaselineCandidate]) -> bool:
    return any(candidate.paper_id or candidate.implementation_available for candidate in candidates)


def render_baseline_candidates_markdown(candidates: list[BaselineCandidate]) -> str:
    lines = ["# Baseline Candidates", ""]
    if not candidates:
        lines.append("No baseline candidates generated yet.")
        return "\n".join(lines).rstrip() + "\n"
    for candidate in candidates:
        lines.extend(
            [
                f"## {candidate.baseline_name}",
                "",
                f"- Paper ID: `{candidate.paper_id or 'manual'}`",
                f"- Implementation available: {candidate.implementation_available}",
                f"- Code URL: {candidate.code_url or 'unknown'}",
                f"- Why required: {candidate.why_required or 'not specified'}",
                f"- Risk if missing: {candidate.risk_if_missing or 'not specified'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _baseline_name(paper: Paper | None, paper_id: str) -> str:
    if paper is None:
        return f"Baseline from {paper_id}"
    title = paper.title or paper.id
    return f"{title} baseline"


def _code_url(paper: Paper | None) -> str:
    if paper is None:
        return ""
    for key in ["code_url", "github", "repository", "repo_url"]:
        value = paper.raw_metadata.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return ""


def _dedupe_candidates(candidates: list[BaselineCandidate]) -> list[BaselineCandidate]:
    seen: set[tuple[str, str]] = set()
    result: list[BaselineCandidate] = []
    for candidate in candidates:
        key = (candidate.paper_id, candidate.baseline_name.lower())
        if key not in seen:
            result.append(candidate)
            seen.add(key)
    return result
