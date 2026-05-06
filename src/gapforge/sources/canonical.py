"""Paper canonicalization and conservative duplicate merging."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import CanonicalPaperIdentity, Paper, PaperMergeDecision, Provenance, ResearchRunState, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso


def canonicalize_run(config: GapForgeConfig, run_id: str) -> tuple[list[CanonicalPaperIdentity], list[PaperMergeDecision]]:
    manager = ResearchStateManager(config)
    state = manager.load_run(run_id)
    identities, decisions = canonicalize_run_state(state)
    manager.save_run(state)
    write_merge_artifacts(Path(state.run_dir), identities, decisions)
    return identities, decisions


def canonicalize_project(config: GapForgeConfig, project_id: str) -> tuple[list[CanonicalPaperIdentity], list[PaperMergeDecision]]:
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(project_id)
    all_identities: list[CanonicalPaperIdentity] = []
    all_decisions: list[PaperMergeDecision] = []
    for run_id in program.run_ids or program.project.run_ids:
        identities, decisions = canonicalize_run(config, run_id)
        all_identities.extend(identities)
        all_decisions.extend(decisions)
    project_dir = Path(program.project.root_dir)
    write_merge_artifacts(project_dir, all_identities, all_decisions)
    return all_identities, all_decisions


def canonicalize_run_state(state: ResearchRunState) -> tuple[list[CanonicalPaperIdentity], list[PaperMergeDecision]]:
    papers = list(state.papers)
    identities = [identity_for_paper(paper) for paper in papers]
    groups, reasons = _duplicate_groups(papers, identities)
    if not groups:
        return identities, []

    by_id = {paper.id: paper for paper in papers}
    decisions: list[PaperMergeDecision] = []
    id_map: dict[str, str] = {}
    retained: list[Paper] = []
    grouped_ids = {paper_id for group in groups for paper_id in group}
    for paper in papers:
        if paper.id not in grouped_ids:
            retained.append(paper)
            continue
        group = next(group for group in groups if paper.id in group)
        if paper.id != _best_paper_id([by_id[item] for item in group]):
            continue
        kept = by_id[paper.id]
        merged_ids = [item for item in group if item != kept.id]
        fields_preserved: list[str] = []
        fields_rejected: list[str] = []
        for merged_id in merged_ids:
            _merge_paper(kept, by_id[merged_id], fields_preserved, fields_rejected)
            id_map[merged_id] = kept.id
        retained.append(kept)
        decisions.append(
            PaperMergeDecision(
                kept_paper_id=kept.id,
                merged_paper_ids=merged_ids,
                merge_reason="; ".join(reasons.get(tuple(sorted(group)), [])) or "high-confidence duplicate",
                fields_preserved=_unique(fields_preserved),
                fields_rejected=_unique(fields_rejected),
                confidence="high",
                provenance=_canonical_provenance([kept.id, *merged_ids], "Merged high-confidence duplicate paper records."),
            )
        )
    state.papers = retained
    _rewrite_paper_references(state, id_map)
    return [identity_for_paper(paper) for paper in retained], decisions


def identity_for_paper(paper: Paper) -> CanonicalPaperIdentity:
    doi = normalize_doi(paper.doi or str(paper.raw_metadata.get("doi", "")))
    arxiv_id = normalize_arxiv_id(paper.arxiv_id or _extract_arxiv_id(" ".join([paper.url, paper.pdf_url])))
    openreview_id = paper.openreview_id or _extract_openreview_id(paper.url)
    semantic_scholar_id = paper.semantic_scholar_id or str(paper.raw_metadata.get("paperId", "") or paper.raw_metadata.get("paper_id", ""))
    normalized_title = normalize_title(paper.title)
    canonical_id = _canonical_id(doi, arxiv_id, openreview_id, semantic_scholar_id, normalized_title)
    urls = _unique([paper.url, paper.pdf_url])
    return CanonicalPaperIdentity(
        canonical_id=canonical_id,
        title=paper.title,
        normalized_title=normalized_title,
        doi=doi,
        arxiv_id=arxiv_id,
        openreview_id=openreview_id,
        semantic_scholar_id=semantic_scholar_id,
        urls=urls,
        source_paper_ids=_unique([paper.id, str(paper.raw_metadata.get("source_paper_id", ""))]),
        confidence="high" if any([doi, arxiv_id, openreview_id, semantic_scholar_id]) else "medium",
        provenance=_canonical_provenance([paper.id], "Derived canonical identity fields from paper metadata."),
    )


def normalize_title(title: str) -> str:
    text = title.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_doi(doi: str) -> str:
    text = doi.strip().lower()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    return text.strip().rstrip(".")


def normalize_arxiv_id(arxiv_id: str) -> str:
    text = arxiv_id.strip()
    text = re.sub(r"^arxiv:", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", text, flags=re.IGNORECASE)
    text = text.removesuffix(".pdf")
    return text.strip()


def render_merge_report(identities: list[CanonicalPaperIdentity], decisions: list[PaperMergeDecision]) -> str:
    lines = [
        "# Paper Merge Report",
        "",
        f"- Canonical papers: {len(identities)}",
        f"- Merge decisions: {len(decisions)}",
        "",
        "## Decisions",
        "",
    ]
    if not decisions:
        lines.append("No high-confidence duplicate paper records were merged.")
    for decision in decisions:
        lines.extend(
            [
                f"### Kept `{decision.kept_paper_id}`",
                "",
                f"- Merged: {', '.join(decision.merged_paper_ids)}",
                f"- Reason: {decision.merge_reason}",
                f"- Confidence: {decision.confidence}",
                f"- Fields preserved: {', '.join(decision.fields_preserved) or 'none'}",
                f"- Fields rejected: {', '.join(decision.fields_rejected) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_merge_artifacts(
    root_dir: Path, identities: list[CanonicalPaperIdentity], decisions: list[PaperMergeDecision]
) -> tuple[Path, Path, Path]:
    root_dir.mkdir(parents=True, exist_ok=True)
    identities_path = root_dir / "canonical_paper_identities.json"
    decisions_path = root_dir / "paper_merge_decisions.json"
    report_path = root_dir / "paper_merge_report.md"
    identities_path.write_text(json.dumps([to_plain(identity) for identity in identities], indent=2) + "\n", encoding="utf-8")
    decisions_path.write_text(json.dumps([to_plain(decision) for decision in decisions], indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_merge_report(identities, decisions), encoding="utf-8")
    return identities_path, decisions_path, report_path


def load_merge_report_for_run(config: GapForgeConfig, run_id: str) -> str:
    state = ResearchStateManager(config).load_run(run_id)
    report_path = Path(state.run_dir) / "paper_merge_report.md"
    if not report_path.exists():
        return "# Paper Merge Report\n\nNo merge report has been generated for this run.\n"
    return report_path.read_text(encoding="utf-8")


def _duplicate_groups(
    papers: list[Paper], identities: list[CanonicalPaperIdentity]
) -> tuple[list[list[str]], dict[tuple[str, ...], list[str]]]:
    parent = {paper.id: paper.id for paper in papers}
    reasons_by_pair: dict[tuple[str, str], str] = {}
    identities_by_id = {paper.id: identity for paper, identity in zip(papers, identities, strict=True)}
    for index, left in enumerate(papers):
        for right in papers[index + 1 :]:
            reason = _merge_reason(left, right, identities_by_id[left.id], identities_by_id[right.id])
            if reason:
                _union(parent, left.id, right.id)
                pair_key = (left.id, right.id) if left.id <= right.id else (right.id, left.id)
                reasons_by_pair[pair_key] = reason
    grouped: dict[str, list[str]] = defaultdict(list)
    for paper in papers:
        grouped[_find(parent, paper.id)].append(paper.id)
    groups = [group for group in grouped.values() if len(group) > 1]
    reasons: dict[tuple[str, ...], list[str]] = {}
    for group in groups:
        key = tuple(sorted(group))
        reasons[key] = [reason for pair, reason in reasons_by_pair.items() if pair[0] in group and pair[1] in group]
    return groups, reasons


def _merge_reason(left: Paper, right: Paper, left_id: CanonicalPaperIdentity, right_id: CanonicalPaperIdentity) -> str:
    if left_id.doi and left_id.doi == right_id.doi:
        return f"matching DOI `{left_id.doi}`"
    if left_id.arxiv_id and left_id.arxiv_id == right_id.arxiv_id:
        return f"matching arXiv ID `{left_id.arxiv_id}`"
    if left_id.openreview_id and left_id.openreview_id == right_id.openreview_id:
        return f"matching OpenReview ID `{left_id.openreview_id}`"
    if left_id.normalized_title and left_id.normalized_title == right_id.normalized_title:
        return "exact normalized title match"
    title_similarity = SequenceMatcher(None, left_id.normalized_title, right_id.normalized_title).ratio()
    if title_similarity >= 0.94 and _author_overlap(left.authors, right.authors) and _year_compatible(left.year, right.year):
        return f"high title similarity ({title_similarity:.2f}) with overlapping authors/year"
    return ""


def _merge_paper(kept: Paper, incoming: Paper, fields_preserved: list[str], fields_rejected: list[str]) -> None:
    _fill_text_field(kept, incoming, "title", fields_preserved, fields_rejected)
    _fill_text_field(kept, incoming, "venue", fields_preserved, fields_rejected)
    _fill_text_field(kept, incoming, "published_date", fields_preserved, fields_rejected)
    _fill_text_field(kept, incoming, "url", fields_preserved, fields_rejected)
    _fill_text_field(kept, incoming, "pdf_url", fields_preserved, fields_rejected)
    _fill_text_field(kept, incoming, "doi", fields_preserved, fields_rejected, normalize=normalize_doi)
    _fill_text_field(kept, incoming, "arxiv_id", fields_preserved, fields_rejected, normalize=normalize_arxiv_id)
    _fill_text_field(kept, incoming, "openreview_id", fields_preserved, fields_rejected)
    _fill_text_field(kept, incoming, "semantic_scholar_id", fields_preserved, fields_rejected)
    if len(incoming.abstract or "") > len(kept.abstract or ""):
        kept.abstract = incoming.abstract
        fields_preserved.append(f"abstract:{incoming.id}")
    if not kept.authors and incoming.authors:
        kept.authors = incoming.authors
        fields_preserved.append(f"authors:{incoming.id}")
    if not kept.year and incoming.year:
        kept.year = incoming.year
        fields_preserved.append(f"year:{incoming.id}")
    if incoming.citation_count > kept.citation_count:
        kept.citation_count = incoming.citation_count
        fields_preserved.append(f"citation_count:{incoming.id}")
    kept.keywords = _unique([*kept.keywords, *incoming.keywords])
    kept.roles = _unique([*kept.roles, *incoming.roles])
    kept.source = "; ".join(_unique([kept.source, incoming.source]))
    _merge_raw_metadata(kept, incoming, fields_preserved, fields_rejected)


def _fill_text_field(
    kept: Paper,
    incoming: Paper,
    field_name: str,
    fields_preserved: list[str],
    fields_rejected: list[str],
    *,
    normalize=None,
) -> None:
    kept_value = str(getattr(kept, field_name) or "")
    incoming_value = str(getattr(incoming, field_name) or "")
    if not incoming_value:
        return
    comparable_kept = normalize(kept_value) if normalize else kept_value
    comparable_incoming = normalize(incoming_value) if normalize else incoming_value
    if not kept_value:
        setattr(kept, field_name, incoming_value)
        fields_preserved.append(f"{field_name}:{incoming.id}")
    elif comparable_kept != comparable_incoming and field_name in {"url", "pdf_url"}:
        _append_raw_list(kept, f"alternate_{field_name}s", incoming_value)
        fields_preserved.append(f"alternate_{field_name}:{incoming.id}")
    elif comparable_kept != comparable_incoming:
        fields_rejected.append(f"{field_name}:{incoming.id}")


def _merge_raw_metadata(kept: Paper, incoming: Paper, fields_preserved: list[str], fields_rejected: list[str]) -> None:
    kept.raw_metadata.setdefault("source_paper_ids", [])
    if isinstance(kept.raw_metadata["source_paper_ids"], list):
        kept.raw_metadata["source_paper_ids"] = _unique([*kept.raw_metadata["source_paper_ids"], kept.id, incoming.id])
    kept.raw_metadata.setdefault("merged_raw_metadata", {})
    if isinstance(kept.raw_metadata["merged_raw_metadata"], dict):
        kept.raw_metadata["merged_raw_metadata"][incoming.id] = incoming.raw_metadata
    for key, value in incoming.raw_metadata.items():
        if key not in kept.raw_metadata:
            kept.raw_metadata[key] = value
            fields_preserved.append(f"raw_metadata.{key}:{incoming.id}")
        elif kept.raw_metadata[key] != value:
            fields_rejected.append(f"raw_metadata.{key}:{incoming.id}")


def _append_raw_list(paper: Paper, key: str, value: str) -> None:
    existing = paper.raw_metadata.get(key, [])
    values = existing if isinstance(existing, list) else [str(existing)]
    paper.raw_metadata[key] = _unique([*values, value])


def _rewrite_paper_references(state: ResearchRunState, id_map: dict[str, str]) -> None:
    if not id_map:
        return
    for collection_name in [
        "paper_artifacts",
        "paper_sections",
        "evidence_spans",
        "paper_notes",
        "references",
        "tables",
        "equations",
        "captions",
        "ocr_attempts",
        "claims",
        "gap_evidence_matrices",
        "related_work_matrices",
        "baseline_candidates",
    ]:
        for item in getattr(state, collection_name, []):
            if hasattr(item, "paper_id") and getattr(item, "paper_id") in id_map:
                setattr(item, "paper_id", id_map[getattr(item, "paper_id")])
            if hasattr(item, "paper_ids"):
                setattr(item, "paper_ids", _rewrite_ids(getattr(item, "paper_ids"), id_map))
            if hasattr(item, "source_paper_ids"):
                setattr(item, "source_paper_ids", _rewrite_ids(getattr(item, "source_paper_ids"), id_map))
            if hasattr(item, "supporting_paper_ids"):
                setattr(item, "supporting_paper_ids", _rewrite_ids(getattr(item, "supporting_paper_ids"), id_map))
            if hasattr(item, "counterevidence_paper_ids"):
                setattr(item, "counterevidence_paper_ids", _rewrite_ids(getattr(item, "counterevidence_paper_ids"), id_map))
    for query in state.search_queries:
        query.result_paper_ids = _rewrite_ids(query.result_paper_ids, id_map)
    if state.source_coverage is not None:
        state.source_coverage.papers_with_pdf = _rewrite_ids(state.source_coverage.papers_with_pdf, id_map)
        state.source_coverage.papers_with_full_text = _rewrite_ids(state.source_coverage.papers_with_full_text, id_map)
        state.source_coverage.papers_abstract_only = _rewrite_ids(state.source_coverage.papers_abstract_only, id_map)


def _rewrite_ids(values: list[str], id_map: dict[str, str]) -> list[str]:
    return _unique([id_map.get(value, value) for value in values])


def _best_paper_id(papers: list[Paper]) -> str:
    return sorted(papers, key=lambda paper: (-_richness_score(paper), paper.id))[0].id


def _richness_score(paper: Paper) -> float:
    score = len(paper.abstract or "") / 1000
    score += paper.citation_count / 1000
    score += 2 if paper.doi else 0
    score += 2 if paper.arxiv_id else 0
    score += 2 if paper.openreview_id else 0
    score += 1 if paper.semantic_scholar_id else 0
    score += 1 if paper.url else 0
    score += 1 if paper.pdf_url else 0
    score += min(len(paper.raw_metadata), 20) / 10
    return score


def _canonical_id(doi: str, arxiv_id: str, openreview_id: str, semantic_scholar_id: str, normalized_title: str) -> str:
    if doi:
        return f"doi:{doi}"
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    if openreview_id:
        return f"openreview:{openreview_id}"
    if semantic_scholar_id:
        return f"semantic-scholar:{semantic_scholar_id}"
    return f"title:{slugify(normalized_title)[:80]}"


def _extract_arxiv_id(text: str) -> str:
    match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", text)
    return match.group(1) if match else ""


def _extract_openreview_id(url: str) -> str:
    match = re.search(r"[?&]id=([^&#]+)", url)
    return match.group(1) if match and "openreview.net" in url else ""


def _author_overlap(left: list[str], right: list[str]) -> bool:
    left_norm = {_normalize_author(author) for author in left}
    right_norm = {_normalize_author(author) for author in right}
    return bool(left_norm & right_norm)


def _normalize_author(author: str) -> str:
    return re.sub(r"[^a-z]", "", author.lower())


def _year_compatible(left: int, right: int) -> bool:
    return bool(left and right and abs(left - right) <= 1)


def _find(parent: dict[str, str], value: str) -> str:
    while parent[value] != value:
        parent[value] = parent[parent[value]]
        value = parent[value]
    return value


def _union(parent: dict[str, str], left: str, right: str) -> None:
    left_root = _find(parent, left)
    right_root = _find(parent, right)
    if left_root != right_root:
        parent[right_root] = left_root


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _canonical_provenance(source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill="paper-canonicalization",
        source_ids=source_ids,
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )
