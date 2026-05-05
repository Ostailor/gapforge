"""Prompt-pack generation for optional LLM-backed GapForge skills."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.llm.schemas import schema_for
from gapforge.models import EvidenceSpan, Gap, Paper, PaperSection, ResearchRunState, to_plain


@dataclass(slots=True)
class PromptPack:
    skill_name: str
    task: str
    inputs_summary: str
    required_schema: dict[str, Any]
    citation_rules: list[str] = field(default_factory=list)
    uncertainty_rules: list[str] = field(default_factory=list)
    output_contract: list[str] = field(default_factory=list)
    state_excerpt: dict[str, Any] = field(default_factory=dict)
    target_id: str = ""

    def render_markdown(self) -> str:
        lines = [
            f"# GapForge Prompt Pack: {self.skill_name}",
            "",
            f"Task: {self.task}",
            f"Target ID: `{self.target_id or 'none'}`",
            "",
            "## Inputs Summary",
            "",
            self.inputs_summary,
            "",
            "## Citation Rules",
            "",
        ]
        lines.extend([f"- {rule}" for rule in self.citation_rules])
        lines.extend(["", "## Uncertainty Rules", ""])
        lines.extend([f"- {rule}" for rule in self.uncertainty_rules])
        lines.extend(["", "## Output Contract", ""])
        lines.extend([f"- {item}" for item in self.output_contract])
        lines.extend(["", "## Required JSON Schema", "", "```json", json.dumps(self.required_schema, indent=2), "```", ""])
        lines.extend(["## State Excerpt", "", "```json", json.dumps(self.state_excerpt, indent=2), "```", ""])
        return "\n".join(lines).rstrip() + "\n"


class PromptPackBuilder:
    """Build Codex-readable prompt packs from persisted research state."""

    def build(self, state: ResearchRunState, *, skill_name: str, gap_id: str | None = None) -> PromptPack:
        normalized = _normalize_skill_name(skill_name)
        if normalized == "deep-reading":
            return self._deep_reading_pack(state)
        if normalized == "novelty-gate":
            return self._novelty_gate_pack(state, gap_id=gap_id)
        if normalized == "gap-mining":
            return self._gap_mining_pack(state)
        if normalized == "reviewer-simulation":
            return self._reviewer_simulation_pack(state)
        raise ValueError(f"Unsupported prompt-pack skill: {skill_name}")

    def _deep_reading_pack(self, state: ResearchRunState) -> PromptPack:
        selected_papers = _selected_deep_reading_papers(state)
        selected_ids = {paper.id for paper in selected_papers}
        sections = [section for section in state.paper_sections if section.paper_id in selected_ids]
        spans = [span for span in state.evidence_spans if span.paper_id in selected_ids]
        return PromptPack(
            skill_name="deep-reading",
            task=(
                "Produce structured paper notes that distinguish claims, demonstrations, assumptions, limitations, "
                "datasets, metrics, and topic connections without inventing results."
            ),
            inputs_summary=(
                f"Topic `{state.topic.text}` with {len(selected_papers)} selected paper(s), "
                f"{len(sections)} parsed section(s), and {len(spans)} existing evidence span(s)."
            ),
            required_schema=schema_for("deep-reading"),
            citation_rules=_citation_rules(),
            uncertainty_rules=_uncertainty_rules(),
            output_contract=_output_contract("deep-reading"),
            state_excerpt={
                "topic": state.topic.text,
                "papers": [_paper_excerpt(paper) for paper in selected_papers],
                "sections": [_section_excerpt(section) for section in sections[:24]],
                "evidence_spans": [_span_excerpt(span) for span in spans[:24]],
                "paper_notes": [to_plain(note) for note in state.paper_notes if note.paper_id in selected_ids],
            },
        )

    def _novelty_gate_pack(self, state: ResearchRunState, *, gap_id: str | None) -> PromptPack:
        target = _target_gap(state, gap_id)
        candidate_ids = set(target.supporting_paper_ids or target.linked_paper_ids or target.closest_prior_work)
        candidate_ids.update(
            note.paper_id for note in state.paper_notes if note.paper_id and _overlaps_gap(target, note.one_sentence_summary)
        )
        candidates = [paper for paper in state.papers if not candidate_ids or paper.id in candidate_ids]
        if len(candidates) < min(8, len(state.papers)):
            candidates = state.papers[:12]
        candidate_paper_ids = {paper.id for paper in candidates}
        spans = [span for span in state.evidence_spans if span.paper_id in {paper.id for paper in candidates}]
        return PromptPack(
            skill_name="novelty-gate",
            task=(
                "Try to kill or revise the target idea by identifying closest prior work and decisive differences. "
                "Do not claim novelty unless closest prior work is listed and compared."
            ),
            inputs_summary=(
                f"Target gap `{target.id}` for topic `{state.topic.text}` with {len(candidates)} candidate prior-work paper(s)."
            ),
            required_schema=schema_for("novelty-gate"),
            citation_rules=_citation_rules(),
            uncertainty_rules=_uncertainty_rules(),
            output_contract=_output_contract("novelty-gate"),
            state_excerpt={
                "topic": state.topic.text,
                "target_gap": to_plain(target),
                "candidate_prior_work": [_paper_excerpt(paper) for paper in candidates[:20]],
                "paper_notes": [to_plain(note) for note in state.paper_notes if note.paper_id in candidate_paper_ids],
                "evidence_spans": [_span_excerpt(span) for span in spans[:30]],
                "novelty_assessments": [
                    to_plain(item) for item in state.novelty_assessments if item.target_gap_or_hypothesis_id == target.id
                ],
                "novelty_dossiers": [to_plain(item) for item in state.novelty_dossiers if item.target_id == target.id],
                "search_queries": [
                    to_plain(record) for record in state.search_queries if record.purpose in {"novelty", "citation_expansion"}
                ],
                "source_coverage": to_plain(state.source_coverage),
            },
            target_id=target.id,
        )

    def _gap_mining_pack(self, state: ResearchRunState) -> PromptPack:
        return PromptPack(
            skill_name="gap-mining",
            task=(
                "Identify evidence-backed research gaps from repeated patterns, explicit limitations, missing metrics, and counterevidence."
            ),
            inputs_summary=(
                f"Topic `{state.topic.text}` with {len(state.paper_notes)} paper notes, "
                f"{len(state.evidence_spans)} evidence spans, and {len(state.claims)} ledger claims."
            ),
            required_schema=schema_for("gap-mining"),
            citation_rules=_citation_rules(),
            uncertainty_rules=_uncertainty_rules(),
            output_contract=_output_contract("gap-mining"),
            state_excerpt={
                "topic": state.topic.text,
                "field_map": to_plain(state.field_map),
                "paper_notes": [to_plain(note) for note in state.paper_notes[:20]],
                "claims": [to_plain(claim) for claim in state.claims[:40]],
                "evidence_spans": [_span_excerpt(span) for span in state.evidence_spans[:40]],
                "source_coverage": to_plain(state.source_coverage),
            },
        )

    def _reviewer_simulation_pack(self, state: ResearchRunState) -> PromptPack:
        return PromptPack(
            skill_name="reviewer-simulation",
            task="Attack proposed experiments like serious conference reviewers and produce concrete blocking fixes.",
            inputs_summary=f"Topic `{state.topic.text}` with {len(state.experiments)} experiment plan(s).",
            required_schema=schema_for("reviewer-simulation"),
            citation_rules=_citation_rules(),
            uncertainty_rules=_uncertainty_rules(),
            output_contract=_output_contract("reviewer-simulation"),
            state_excerpt={
                "topic": state.topic.text,
                "experiments": [to_plain(experiment) for experiment in state.experiments],
                "novelty_assessments": [to_plain(item) for item in state.novelty_assessments],
                "claims": [to_plain(claim) for claim in state.claims[:40]],
                "paper_notes": [to_plain(note) for note in state.paper_notes[:20]],
            },
        )


def write_prompt_pack(state: ResearchRunState, *, skill_name: str, gap_id: str | None = None) -> Path:
    pack = PromptPackBuilder().build(state, skill_name=skill_name, gap_id=gap_id)
    output_dir = Path(state.run_dir) / "prompt_packs"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = f"_{_safe_name(pack.target_id)}" if pack.target_id else ""
    path = output_dir / f"{_safe_name(pack.skill_name)}{target}.md"
    path.write_text(pack.render_markdown(), encoding="utf-8")
    return path


def _normalize_skill_name(skill_name: str) -> str:
    return skill_name.strip().lower().replace("_", "-")


def _citation_rules() -> list[str]:
    return [
        "Do not hallucinate citations, paper IDs, DOIs, URLs, page numbers, sections, or venues.",
        "Use only supplied paper IDs and EvidenceSpan locators when grounding claims.",
        "Cite EvidenceSpan locators for extracted claims, results, limitations, datasets, and metrics whenever available.",
        "If evidence is abstract-only or metadata-only, label it as such.",
    ]


def _uncertainty_rules() -> list[str]:
    return [
        "Mark uncertainty explicitly; use low confidence when source coverage or full text is weak.",
        "Never upgrade a novelty or result claim beyond the supplied evidence.",
        "Separate evidence-backed claims from hypotheses and reviewer-style speculation.",
        "Store concise public reasoning summaries only; do not include hidden chain-of-thought.",
    ]


def _output_contract(skill_name: str) -> list[str]:
    shared = [
        "Return valid JSON matching the required schema.",
        "Keep every nontrivial claim linked to a paper ID, EvidenceSpan locator, or an explicit uncertainty note.",
        "Prefer omissions and uncertainty over fabricated details.",
    ]
    if skill_name == "novelty-gate":
        shared.append("List closest prior work before any positive novelty verdict.")
    if skill_name == "deep-reading":
        shared.append("Do not include main_results unless the supplied text directly supports them.")
    return shared


def _selected_deep_reading_papers(state: ResearchRunState) -> list[Paper]:
    if state.paper_triage is not None:
        preferred = [decision.paper_id for decision in state.paper_triage.decisions if decision.tier in {"Tier 1", "Tier 2"}]
        selected = [paper for paper in state.papers if paper.id in set(preferred)]
        if selected:
            return selected[:12]
    return state.papers[:12]


def _target_gap(state: ResearchRunState, gap_id: str | None) -> Gap:
    if gap_id is None:
        if not state.gaps:
            raise ValueError("novelty-gate prompt pack requires a gap in state or --gap-id")
        return state.gaps[0]
    for gap in state.gaps:
        if gap.id == gap_id:
            return gap
    raise KeyError(f"Unknown gap: {gap_id}")


def _paper_excerpt(paper: Paper) -> dict[str, Any]:
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "year": paper.year,
        "venue": paper.venue,
        "source": paper.source,
        "doi": paper.doi,
        "arxiv_id": paper.arxiv_id,
        "citation_count": paper.citation_count,
        "roles": paper.roles,
        "abstract": paper.abstract[:2000],
    }


def _section_excerpt(section: PaperSection) -> dict[str, Any]:
    return {
        "id": section.id,
        "paper_id": section.paper_id,
        "title": section.title,
        "section_type": section.section_type,
        "page_start": section.page_start,
        "page_end": section.page_end,
        "confidence": section.confidence,
        "text": section.text[:2500],
    }


def _span_excerpt(span: EvidenceSpan) -> dict[str, Any]:
    return {
        "id": span.id,
        "paper_id": span.paper_id,
        "section_id": span.section_id,
        "locator": span.locator,
        "evidence_type": span.evidence_type,
        "confidence": span.confidence,
        "quote": span.quote,
    }


def _overlaps_gap(gap: Gap, text: str) -> bool:
    gap_terms = {term for term in f"{gap.title} {gap.description}".lower().split() if len(term) > 5}
    return bool(gap_terms & set(text.lower().split()))


def _safe_name(value: str) -> str:
    clean = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value.lower())
    while "--" in clean:
        clean = clean.replace("--", "-")
    return clean.strip("-") or "prompt-pack"
