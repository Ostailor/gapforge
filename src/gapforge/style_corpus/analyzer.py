"""Venue style analysis over feature-only TeX corpus records."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.manuscript import ManuscriptManager
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.state import slugify, utc_now_iso
from gapforge.style_corpus.ingest import StyleCorpusManager
from gapforge.style_corpus.style_features import StyleCorpusPaper
from gapforge.venues.profiles import get_venue_profile, is_venue_profile

MIN_STYLE_CORPUS_SIZE = 3


@dataclass(slots=True)
class VenueStyleProfile:
    id: str
    venue_profile_id: str
    corpus_paper_ids: list[str] = field(default_factory=list)
    section_order_distribution: dict[str, Any] = field(default_factory=dict)
    abstract_length_stats: dict[str, Any] = field(default_factory=dict)
    intro_pattern_summary: dict[str, Any] = field(default_factory=dict)
    related_work_placement: dict[str, Any] = field(default_factory=dict)
    experiment_section_patterns: dict[str, Any] = field(default_factory=dict)
    limitation_section_patterns: dict[str, Any] = field(default_factory=dict)
    figure_table_density: dict[str, Any] = field(default_factory=dict)
    claim_language_patterns: dict[str, Any] = field(default_factory=dict)
    contribution_framing_patterns: dict[str, Any] = field(default_factory=dict)
    caveat_patterns: dict[str, Any] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="venue-style-analyzer"))


@dataclass(slots=True)
class StyleRecommendation:
    id: str
    manuscript_id: str
    venue_profile_id: str
    recommendation_type: str
    description: str
    evidence_from_style_corpus: str
    risk: str
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="venue-style-recommend"))


class VenueStyleAnalyzer:
    """Analyze venue-specific style patterns without carrying source prose forward."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.corpus = StyleCorpusManager(config)
        self.manuscripts = ManuscriptManager(config)

    def analyze(self, venue_profile_id: str) -> VenueStyleProfile:
        profile = get_venue_profile(venue_profile_id)
        papers = [paper for paper in self.corpus.list_papers() if paper.venue == profile.id and paper.license_status != "restricted"]
        style_profile = VenueStyleProfile(
            id=f"venue-style-{slugify(profile.id)}",
            venue_profile_id=profile.id,
            corpus_paper_ids=[paper.id for paper in papers],
            section_order_distribution=_section_order_distribution(papers),
            abstract_length_stats=_abstract_length_stats(papers),
            intro_pattern_summary=_intro_pattern_summary(papers),
            related_work_placement=_section_placement(papers, ["related"]),
            experiment_section_patterns=_section_placement(papers, ["experiment", "evaluation", "result"]),
            limitation_section_patterns=_section_placement(papers, ["limitation", "threat", "validity"]),
            figure_table_density=_figure_table_density(papers),
            claim_language_patterns=_claim_language_patterns(papers),
            contribution_framing_patterns=_contribution_framing_patterns(papers),
            caveat_patterns=_caveat_patterns(papers),
            provenance=_provenance(
                "venue-style-analyze",
                [profile.id, *[paper.id for paper in papers]],
                "Aggregated venue style features from stored corpus metadata only; no source prose was copied.",
            ),
        )
        self._write_profile(style_profile)
        return style_profile

    def load_or_analyze(self, venue_profile_id: str) -> VenueStyleProfile:
        profile_id = get_venue_profile(venue_profile_id).id
        path = self._profile_path(profile_id)
        if path.exists():
            return from_dict(VenueStyleProfile, json.loads(path.read_text(encoding="utf-8")))
        return self.analyze(profile_id)

    def recommend(self, manuscript_id: str) -> list[StyleRecommendation]:
        state = self.manuscripts.load_state(manuscript_id)
        venue_profile_id = _resolve_venue_profile_id(state.manuscript.target_venue)
        profile = self.analyze(venue_profile_id)
        manuscript_sections = [section.section_type for section in state.sections]
        manuscript_section_titles = [section.title for section in state.sections]
        weak_corpus = len(profile.corpus_paper_ids) < MIN_STYLE_CORPUS_SIZE
        risk_prefix = "high" if weak_corpus else "medium"
        caveat = _style_caveat(profile)
        risk_base = f"{risk_prefix}: {caveat}"
        recommendations = [
            StyleRecommendation(
                id=_recommendation_id(manuscript_id, venue_profile_id, "section_order"),
                manuscript_id=manuscript_id,
                venue_profile_id=venue_profile_id,
                recommendation_type="section_order",
                description=_section_order_recommendation(profile, manuscript_sections),
                evidence_from_style_corpus=_order_evidence(profile),
                risk=f"{risk_base} Style guidance must not override evidence, validity, or result gates.",
                provenance=_recommendation_provenance(manuscript_id, venue_profile_id, profile, "section_order"),
            ),
            StyleRecommendation(
                id=_recommendation_id(manuscript_id, venue_profile_id, "abstract_length"),
                manuscript_id=manuscript_id,
                venue_profile_id=venue_profile_id,
                recommendation_type="abstract_length",
                description=_abstract_recommendation(profile),
                evidence_from_style_corpus=_abstract_evidence(profile),
                risk=f"{risk_base} Abstract-length guidance is descriptive corpus evidence, not a venue rule.",
                provenance=_recommendation_provenance(manuscript_id, venue_profile_id, profile, "abstract_length"),
            ),
            StyleRecommendation(
                id=_recommendation_id(manuscript_id, venue_profile_id, "contribution_framing"),
                manuscript_id=manuscript_id,
                venue_profile_id=venue_profile_id,
                recommendation_type="contribution_framing",
                description=_contribution_recommendation(profile),
                evidence_from_style_corpus=_contribution_evidence(profile),
                risk=f"{risk_base} Use only supported contribution language; do not add novelty, validity, or acceptance claims.",
                provenance=_recommendation_provenance(manuscript_id, venue_profile_id, profile, "contribution_framing"),
            ),
            StyleRecommendation(
                id=_recommendation_id(manuscript_id, venue_profile_id, "limitations"),
                manuscript_id=manuscript_id,
                venue_profile_id=venue_profile_id,
                recommendation_type="limitations",
                description=_limitations_recommendation(profile, manuscript_sections, manuscript_section_titles),
                evidence_from_style_corpus=_limitations_evidence(profile),
                risk=f"{risk_base} Limitations should expose harsh objections and should feed evidence gates, not soften them.",
                provenance=_recommendation_provenance(manuscript_id, venue_profile_id, profile, "limitations"),
            ),
            StyleRecommendation(
                id=_recommendation_id(manuscript_id, venue_profile_id, "figures_tables"),
                manuscript_id=manuscript_id,
                venue_profile_id=venue_profile_id,
                recommendation_type="figures_tables",
                description=_figure_table_recommendation(profile),
                evidence_from_style_corpus=_figure_table_evidence(profile),
                risk=f"{risk_base} Add figures or tables only when backed by existing artifacts and labeled evidence.",
                provenance=_recommendation_provenance(manuscript_id, venue_profile_id, profile, "figures_tables"),
            ),
        ]
        self._write_recommendations(manuscript_id, recommendations)
        return recommendations

    def render_report(self, venue_profile_id: str) -> str:
        profile = self.analyze(venue_profile_id)
        report = render_venue_style_profile(profile)
        self._report_path(profile.venue_profile_id).write_text(report, encoding="utf-8")
        return report

    def render_recommendations(self, manuscript_id: str) -> str:
        recommendations = self.recommend(manuscript_id)
        report = render_style_recommendations(recommendations)
        self._recommendation_report_path(manuscript_id).write_text(report, encoding="utf-8")
        return report

    def _root_dir(self) -> Path:
        path = self.config.data_dir / "style_corpus" / "analysis"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _profile_path(self, venue_profile_id: str) -> Path:
        return self._root_dir() / f"{slugify(venue_profile_id)}.style_profile.json"

    def _report_path(self, venue_profile_id: str) -> Path:
        return self._root_dir() / f"{slugify(venue_profile_id)}.style_report.md"

    def _recommendation_path(self, manuscript_id: str) -> Path:
        path = self._root_dir() / "recommendations"
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{slugify(manuscript_id)}.style_recommendations.json"

    def _recommendation_report_path(self, manuscript_id: str) -> Path:
        path = self._root_dir() / "recommendations"
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{slugify(manuscript_id)}.style_recommendations.md"

    def _write_profile(self, profile: VenueStyleProfile) -> None:
        self._profile_path(profile.venue_profile_id).write_text(json.dumps(to_plain(profile), indent=2) + "\n", encoding="utf-8")
        self._report_path(profile.venue_profile_id).write_text(render_venue_style_profile(profile), encoding="utf-8")

    def _write_recommendations(self, manuscript_id: str, recommendations: list[StyleRecommendation]) -> None:
        self._recommendation_path(manuscript_id).write_text(json.dumps(to_plain(recommendations), indent=2) + "\n", encoding="utf-8")
        self._recommendation_report_path(manuscript_id).write_text(render_style_recommendations(recommendations), encoding="utf-8")


def render_venue_style_profile(profile: VenueStyleProfile) -> str:
    weak = len(profile.corpus_paper_ids) < MIN_STYLE_CORPUS_SIZE
    lines = [
        f"# Venue Style Report `{profile.venue_profile_id}`",
        "",
        "## Safety Boundary",
        "",
        (
            "This report summarizes structural and rhetorical patterns extracted from corpus features only. It must not be used to "
            "copy source text, invent evidence, or bypass evidence gates."
        ),
        "",
        f"- Corpus papers: {len(profile.corpus_paper_ids)}",
        f"- Evidence strength: {'weak' if weak else 'usable'}",
    ]
    if weak:
        lines.append(
            f"- Warning: corpus is too small for strong venue-style inference; minimum recommended size is {MIN_STYLE_CORPUS_SIZE}."
        )
    lines.extend(
        [
            "",
            "## Section Order",
            "",
            _json_block(profile.section_order_distribution),
            "",
            "## Abstract Length",
            "",
            _json_block(profile.abstract_length_stats),
            "",
            "## Placement Patterns",
            "",
            f"- Related work: {_compact(profile.related_work_placement)}",
            f"- Experiments/results: {_compact(profile.experiment_section_patterns)}",
            f"- Limitations/caveats: {_compact(profile.limitation_section_patterns)}",
            "",
            "## Rhetorical Features",
            "",
            f"- Claim language: {_compact(profile.claim_language_patterns)}",
            f"- Contribution framing: {_compact(profile.contribution_framing_patterns)}",
            f"- Caveats: {_compact(profile.caveat_patterns)}",
            f"- Figure/table density: {_compact(profile.figure_table_density)}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_style_recommendations(recommendations: list[StyleRecommendation]) -> str:
    if not recommendations:
        return "# Venue Style Recommendations\n\nNo recommendations generated.\n"
    manuscript_id = recommendations[0].manuscript_id
    venue_profile_id = recommendations[0].venue_profile_id
    lines = [
        f"# Venue Style Recommendations `{manuscript_id}`",
        "",
        f"- Venue profile: `{venue_profile_id}`",
        "- Boundary: recommendations are structural/rhetorical only and must not override evidence gates.",
        "",
    ]
    for recommendation in recommendations:
        lines.extend(
            [
                f"## {recommendation.recommendation_type.replace('_', ' ').title()}",
                "",
                recommendation.description,
                "",
                f"Evidence: {recommendation.evidence_from_style_corpus}",
                "",
                f"Risk: {recommendation.risk}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _section_order_distribution(papers: list[StyleCorpusPaper]) -> dict[str, Any]:
    order_counts = Counter(" > ".join(_normalized_sections(paper.section_titles)) for paper in papers if paper.section_titles)
    first_section_counts = Counter(_normalized_sections(paper.section_titles)[0] for paper in papers if paper.section_titles)
    return {
        "paper_count": len(papers),
        "orders": dict(order_counts.most_common()),
        "common_first_sections": dict(first_section_counts.most_common()),
        "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
    }


def _abstract_length_stats(papers: list[StyleCorpusPaper]) -> dict[str, Any]:
    lengths = [paper.abstract_length for paper in papers if paper.abstract_length > 0]
    if not lengths:
        return {
            "count": len(papers),
            "with_abstract_count": 0,
            "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
            "warning": "No abstract lengths available in the corpus.",
        }
    return {
        "count": len(papers),
        "with_abstract_count": len(lengths),
        "min": min(lengths),
        "max": max(lengths),
        "mean": round(statistics.fmean(lengths), 2),
        "median": round(statistics.median(lengths), 2),
        "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
    }


def _intro_pattern_summary(papers: list[StyleCorpusPaper]) -> dict[str, Any]:
    intro_first_or_second = 0
    early_section_counts: Counter[str] = Counter()
    for paper in papers:
        normalized = _normalized_sections(paper.section_titles)
        if any("introduction" in section for section in normalized[:2]):
            intro_first_or_second += 1
        early_section_counts.update(normalized[:3])
    return {
        "paper_count": len(papers),
        "intro_first_or_second_count": intro_first_or_second,
        "common_early_sections": dict(early_section_counts.most_common(10)),
        "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
    }


def _section_placement(papers: list[StyleCorpusPaper], keywords: list[str]) -> dict[str, Any]:
    placement_counts: Counter[str] = Counter()
    title_counts: Counter[str] = Counter()
    present_count = 0
    for paper in papers:
        normalized = _normalized_sections(paper.section_titles)
        matched_indices = [index for index, title in enumerate(normalized) if any(keyword in title for keyword in keywords)]
        if matched_indices:
            present_count += 1
            placement_counts.update(str(index + 1) for index in matched_indices)
            title_counts.update(normalized[index] for index in matched_indices)
    return {
        "paper_count": len(papers),
        "present_count": present_count,
        "position_counts_1_indexed": dict(placement_counts.most_common()),
        "matched_title_counts": dict(title_counts.most_common(10)),
        "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
    }


def _figure_table_density(papers: list[StyleCorpusPaper]) -> dict[str, Any]:
    figures = [paper.figure_table_counts.get("figure", 0) for paper in papers]
    tables = [paper.figure_table_counts.get("table", 0) for paper in papers]
    totals = [figure + table for figure, table in zip(figures, tables, strict=True)]
    return {
        "paper_count": len(papers),
        "mean_figures": round(statistics.fmean(figures), 2) if figures else 0.0,
        "mean_tables": round(statistics.fmean(tables), 2) if tables else 0.0,
        "mean_total_figures_tables": round(statistics.fmean(totals), 2) if totals else 0.0,
        "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
    }


def _claim_language_patterns(papers: list[StyleCorpusPaper]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    for paper in papers:
        counter.update(paper.contribution_statement_patterns)
    return {
        "paper_count": len(papers),
        "pattern_counts": dict(counter.most_common()),
        "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
    }


def _contribution_framing_patterns(papers: list[StyleCorpusPaper]) -> dict[str, Any]:
    explicit_contribution_sections = 0
    benchmark_or_dataset_framing = 0
    for paper in papers:
        sections = _normalized_sections(paper.section_titles)
        if any("contribution" in section for section in sections):
            explicit_contribution_sections += 1
        if "benchmark_or_dataset_framing" in paper.contribution_statement_patterns:
            benchmark_or_dataset_framing += 1
    return {
        "paper_count": len(papers),
        "explicit_contribution_section_count": explicit_contribution_sections,
        "benchmark_or_dataset_framing_count": benchmark_or_dataset_framing,
        "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
    }


def _caveat_patterns(papers: list[StyleCorpusPaper]) -> dict[str, Any]:
    limitation_count = sum(1 for paper in papers if paper.limitations_presence)
    unknown_license_count = sum(1 for paper in papers if paper.license_status == "unknown")
    return {
        "paper_count": len(papers),
        "limitations_present_count": limitation_count,
        "unknown_license_count": unknown_license_count,
        "too_small_corpus": len(papers) < MIN_STYLE_CORPUS_SIZE,
        "caveat": "Style patterns are descriptive and cannot validate manuscript claims.",
    }


def _section_order_recommendation(profile: VenueStyleProfile, manuscript_sections: list[str]) -> str:
    venue_profile = get_venue_profile(profile.venue_profile_id)
    missing = [section for section in venue_profile.common_section_order if section not in manuscript_sections]
    if missing:
        return (
            "Align the manuscript outline with the venue profile's expected section sequence and add missing structural sections: "
            f"{', '.join(missing)}. Keep content claim-scoped and evidence-backed."
        )
    return "Review section order against the corpus distribution and venue profile; keep the current outline if evidence flow is clearer."


def _abstract_recommendation(profile: VenueStyleProfile) -> str:
    stats = profile.abstract_length_stats
    if not stats.get("with_abstract_count"):
        return "Do not infer abstract length from this corpus; no usable abstract-length features were available."
    return (
        "Use the observed abstract-length range as a rough pacing signal while prioritizing accurate problem, method, evidence, and "
        f"limitation coverage. Observed median: {stats.get('median')} words."
    )


def _contribution_recommendation(profile: VenueStyleProfile) -> str:
    claim_patterns = profile.claim_language_patterns.get("pattern_counts", {})
    if claim_patterns:
        return (
            "Frame contributions explicitly in the introduction, but keep verbs calibrated to supported evidence. Separate protocol, "
            "benchmark, and empirical claims when their evidence sources differ."
        )
    return (
        "Use conservative contribution framing; this corpus does not provide enough structural evidence for stronger rhetorical guidance."
    )


def _limitations_recommendation(profile: VenueStyleProfile, manuscript_sections: list[str], manuscript_section_titles: list[str]) -> str:
    has_limitations = "limitations" in manuscript_sections or any("limitation" in title.lower() for title in manuscript_section_titles)
    if has_limitations:
        return (
            "Keep the limitations section visible and connect it to benchmark-fit, dataset-validity, and unsupported-claim boundaries. "
            "Do not hide harsh reviewer objections."
        )
    return (
        "Add a visible limitations or caveats section before submission. It should distinguish style polish from evidence strength and "
        "state where benchmark grounding remains auxiliary or synthetic."
    )


def _figure_table_recommendation(profile: VenueStyleProfile) -> str:
    density = profile.figure_table_density
    mean_total = density.get("mean_total_figures_tables", 0)
    if not mean_total:
        return "Do not infer figure/table expectations from this corpus; no figure or table features were observed."
    return (
        "Use artifact-backed figures or tables where they clarify benchmark protocol, adapters, or error analysis. Avoid decorative tables "
        f"added only to match corpus density; observed mean figure/table count is {mean_total}."
    )


def _order_evidence(profile: VenueStyleProfile) -> str:
    orders = profile.section_order_distribution.get("orders", {})
    top_order = next(iter(orders), "no observed section orders")
    return f"{len(profile.corpus_paper_ids)} corpus papers; most common observed order: {top_order}."


def _abstract_evidence(profile: VenueStyleProfile) -> str:
    stats = profile.abstract_length_stats
    return (
        f"{stats.get('with_abstract_count', 0)} abstracts with lengths; median={stats.get('median', 'n/a')}, "
        f"range={stats.get('min', 'n/a')} to {stats.get('max', 'n/a')} words."
    )


def _contribution_evidence(profile: VenueStyleProfile) -> str:
    return f"Contribution pattern counts: {profile.claim_language_patterns.get('pattern_counts', {})}."


def _limitations_evidence(profile: VenueStyleProfile) -> str:
    caveats = profile.caveat_patterns
    return (
        f"Limitations present in {caveats.get('limitations_present_count', 0)} of {caveats.get('paper_count', 0)} corpus papers; "
        f"matched section placements: {profile.limitation_section_patterns.get('position_counts_1_indexed', {})}."
    )


def _figure_table_evidence(profile: VenueStyleProfile) -> str:
    density = profile.figure_table_density
    return (
        f"Mean figures={density.get('mean_figures', 0.0)}, mean tables={density.get('mean_tables', 0.0)}, "
        f"mean total={density.get('mean_total_figures_tables', 0.0)}."
    )


def _style_caveat(profile: VenueStyleProfile) -> str:
    if len(profile.corpus_paper_ids) < MIN_STYLE_CORPUS_SIZE:
        return f"corpus too small for strong style inference ({len(profile.corpus_paper_ids)}/{MIN_STYLE_CORPUS_SIZE})."
    return "style evidence is descriptive and venue-specific, not proof of paper quality."


def _resolve_venue_profile_id(target_venue: str) -> str:
    if target_venue and is_venue_profile(target_venue):
        return target_venue
    return "generic_ml_conference"


def _recommendation_id(manuscript_id: str, venue_profile_id: str, recommendation_type: str) -> str:
    return f"style-rec-{slugify(manuscript_id)}-{slugify(venue_profile_id)}-{slugify(recommendation_type)}"


def _recommendation_provenance(
    manuscript_id: str, venue_profile_id: str, profile: VenueStyleProfile, recommendation_type: str
) -> Provenance:
    return _provenance(
        "venue-style-recommend",
        [manuscript_id, venue_profile_id, profile.id, recommendation_type],
        "Generated a structural/rhetorical recommendation from aggregate style features only; no source text was copied.",
    )


def _provenance(skill: str, source_ids: list[str], summary: str) -> Provenance:
    return Provenance(created_by_skill=skill, source_ids=source_ids, timestamp=utc_now_iso(), reasoning_summary=summary)


def _normalized_sections(section_titles: list[str]) -> list[str]:
    return [title.strip().lower().replace("_", " ") for title in section_titles if title.strip()]


def _compact(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True)


def _json_block(value: dict[str, Any]) -> str:
    return "```json\n" + json.dumps(value, indent=2, sort_keys=True) + "\n```"
