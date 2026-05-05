"""Optional LLM-assisted novelty dossiers with strict prior-work validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.claim_ledger import ClaimLedger
from gapforge.llm.base import LLMClient
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.json_guard import JSONGuard
from gapforge.llm.providers import ProviderLLMClient
from gapforge.llm.schemas import schema_for
from gapforge.models import Evidence, Gap, NoveltyAssessment, NoveltyDossier, Paper, ResearchRunState
from gapforge.novelty import LLMNoveltyComparator, NoveltyDossierBuilder, NoveltyQueryPlanner
from gapforge.retrieval.hybrid import retrieval_candidates_for_state
from gapforge.skills.base import Skill
from gapforge.skills.novelty_gate import NoveltyGate


class NoveltyGateLLM(Skill):
    """Refine deterministic novelty dossiers without loosening their gates."""

    name = "novelty-gate-llm"

    def __init__(self, client: LLMClient | None = None, runtime_config: LLMRuntimeConfig | None = None) -> None:
        self.client = client
        self.runtime_config = runtime_config
        self.query_planner = NoveltyQueryPlanner()
        self.dossier_builder = NoveltyDossierBuilder()
        self.llm_comparator = LLMNoveltyComparator()

    def run(self, state: ResearchRunState) -> ResearchRunState:
        return self.assess(state)

    def assess(
        self,
        state: ResearchRunState,
        *,
        gap_id: str | None = None,
        all_targets: bool = False,
        dry_run_prompts: bool = False,
        fake: bool = False,
        allow_deterministic_fallback: bool = True,
    ) -> ResearchRunState:
        runtime = self.runtime_config or LLMRuntimeConfig.from_env()
        mode = "fake" if fake else runtime.mode
        if mode == "off" and not dry_run_prompts:
            if allow_deterministic_fallback:
                return NoveltyGate().assess(state, gap_id=gap_id, deep=False)
            raise ValueError("LLM novelty requires GAPFORGE_LLM_MODE=provider|fake|prompt-pack, --fake, or --dry-run-prompts.")

        targets = _targets(state, gap_id=gap_id, all_targets=all_targets)
        prompt_paths: list[Path] = []
        if dry_run_prompts or mode == "prompt-pack":
            for target_id, idea_summary, gap in targets:
                deterministic_dossier, deterministic_assessment, candidates, retrieval_ran = self._deterministic_context(
                    state, target_id, idea_summary, gap
                )
                prompt = _build_prompt(state, target_id, idea_summary, deterministic_dossier, deterministic_assessment, candidates)
                prompt_paths.append(_write_prompt(state, target_id, prompt))
            _write_report(state, [f"Mode: {mode}", f"Prompt files written: {len(prompt_paths)}", "No model calls were made."], [], [])
            return state

        client = self.client or _client_for_mode(mode, runtime, state.run_dir, self.name)
        updated_dossiers: list[NoveltyDossier] = []
        updated_assessments: list[NoveltyAssessment] = []
        rejected_messages: list[str] = []
        contested_targets: list[str] = []
        for target_id, idea_summary, gap in targets:
            deterministic_dossier, deterministic_assessment, candidates, retrieval_ran = self._deterministic_context(
                state, target_id, idea_summary, gap
            )
            prompt = _build_prompt(state, target_id, idea_summary, deterministic_dossier, deterministic_assessment, candidates)
            prompt_path = _write_prompt(state, target_id, prompt)
            prompt_paths.append(prompt_path)
            if isinstance(client, (FakeLLMClient, ProviderLLMClient)):
                client.prompt_pack_id = prompt_path.name
            payload = client.complete_json(
                prompt,
                schema_name="novelty-comparison",
                system=_system_prompt(),
                temperature=0.0,
                max_tokens=runtime.max_tokens,
            )
            JSONGuard().validate(payload, schema_name="novelty-comparison")
            citation_expansion_ran = _citation_expansion_ran(state)
            result = self.llm_comparator.refine(
                state,
                target_id=target_id,
                idea_summary=idea_summary,
                deterministic_dossier=deterministic_dossier,
                deterministic_assessment=deterministic_assessment,
                payload=payload,
                candidates=candidates,
                retrieval_ran=retrieval_ran,
                citation_expansion_ran=citation_expansion_ran,
                gap=gap,
            )
            updated_dossiers.append(result.dossier)
            updated_assessments.append(result.assessment)
            rejected_messages.extend([f"{target_id}: {message}" for message in result.rejected_reasons])
            if result.contested:
                contested_targets.append(target_id)
            if gap is not None:
                gap.closest_prior_work = result.assessment.closest_prior_work
                gap.novelty_status = _gap_novelty_status(result.assessment)

        state.novelty_dossiers = _replace_dossiers(state.novelty_dossiers, updated_dossiers)
        state.novelty_assessments = _replace_assessments(state.novelty_assessments, updated_assessments)
        state.claims = _add_novelty_claims(state, updated_assessments, contested_targets).claims
        self.mark_complete(state)
        _write_report(
            state,
            [f"Mode: {mode}", f"Updated dossiers: {len(updated_dossiers)}", f"Contested targets: {len(contested_targets)}"],
            rejected_messages,
            prompt_paths,
        )
        return state

    def _deterministic_context(
        self,
        state: ResearchRunState,
        target_id: str,
        idea_summary: str,
        gap: Gap | None,
    ) -> tuple[NoveltyDossier, NoveltyAssessment, list[Paper], bool]:
        queries = self.query_planner.plan(state, target_id, idea_summary, gap)
        candidates, retrieval_ran = _retrieval_candidates(state, idea_summary)
        dossier, assessment = self.dossier_builder.build(
            state,
            target_id=target_id,
            idea_summary=idea_summary,
            query_plan=queries,
            candidates=candidates,
            gap=gap,
            source_search_ran=False,
        )
        existing_dossier = next((item for item in state.novelty_dossiers if item.target_id == target_id), None)
        existing_assessment = next((item for item in state.novelty_assessments if item.target_gap_or_hypothesis_id == target_id), None)
        return existing_dossier or dossier, existing_assessment or assessment, candidates, retrieval_ran


def _client_for_mode(mode: str, runtime: LLMRuntimeConfig, run_dir: str, skill_name: str) -> LLMClient:
    if mode == "fake":
        return FakeLLMClient(run_dir=run_dir, skill_name=skill_name, config=LLMRuntimeConfig(mode="fake"))
    if mode == "provider":
        return ProviderLLMClient(config=runtime, run_dir=run_dir, skill_name=skill_name)
    raise ValueError(f"LLM mode {mode!r} does not create a novelty client.")


def _retrieval_candidates(state: ResearchRunState, idea_summary: str) -> tuple[list[Paper], bool]:
    try:
        _results, paper_ids = retrieval_candidates_for_state(state, idea_summary, top_k=30)
    except (FileNotFoundError, ValueError, OSError, RuntimeError):
        return list(state.papers), False
    by_id = {paper.id: paper for paper in state.papers}
    ordered = [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]
    seen = {paper.id for paper in ordered}
    ordered.extend(paper for paper in state.papers if paper.id not in seen)
    return ordered, True


def _build_prompt(
    state: ResearchRunState,
    target_id: str,
    idea_summary: str,
    deterministic_dossier: NoveltyDossier,
    deterministic_assessment: NoveltyAssessment,
    candidates: list[Paper],
) -> str:
    payload = {
        "target_id": target_id,
        "topic": state.topic.text,
        "idea_summary": idea_summary,
        "deterministic_dossier": {
            "verdict": deterministic_dossier.verdict,
            "novelty_strength": deterministic_dossier.novelty_strength,
            "top_prior_work": deterministic_dossier.top_prior_work,
            "comparison_table": deterministic_dossier.comparison_table[:10],
            "missing_searches": deterministic_dossier.missing_searches,
            "decisive_difference_needed": deterministic_dossier.decisive_difference_needed,
        },
        "deterministic_assessment": {
            "verdict": deterministic_assessment.verdict,
            "novelty_strength": deterministic_assessment.novelty_strength,
            "closest_prior_work": deterministic_assessment.closest_prior_work,
        },
        "candidate_prior_work": [_paper_payload(state, paper) for paper in candidates[:20]],
        "citation_graph": _citation_payload(state),
        "source_coverage": _coverage_payload(state),
        "output_schema": schema_for("novelty-comparison"),
    }
    return (
        "You are GapForge Novelty Gate v3. Return JSON only for the provided schema.\n"
        "You may refine comparison language, but you must not invent prior work.\n"
        "Closest prior work must use known paper IDs from candidate_prior_work or recorded source search results.\n"
        "Any statement about prior work should cite paper IDs and EvidenceSpan locators when available.\n"
        "Do not mark strong novelty unless coverage, closest prior work, retrieval, citation expansion, and missing-search gates pass.\n"
        "If you disagree with the deterministic dossier, state the evidence-located basis. Do not store hidden chain-of-thought.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def _system_prompt() -> str:
    return "You are a conservative novelty auditor. Return valid JSON only and cite known paper IDs."


def _write_prompt(state: ResearchRunState, target_id: str, prompt: str) -> Path:
    prompt_dir = Path(state.run_dir) / "prompt_packs"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    path = prompt_dir / f"novelty-gate-llm-{_safe_id(target_id)}.md"
    path.write_text(f"# Novelty Gate LLM Prompt: {target_id}\n\n```text\n{prompt}\n```\n", encoding="utf-8")
    return path


def _write_report(state: ResearchRunState, summary_lines: list[str], rejected_messages: list[str], prompt_paths: list[Path]) -> None:
    lines = ["# LLM Novelty Gate", ""]
    lines.extend(summary_lines)
    lines.extend(["", "## Prompt Files"])
    lines.extend([f"- `{path}`" for path in prompt_paths] or ["- none"])
    lines.extend(["", "## Rejected Or Downgraded Model Claims"])
    lines.extend([f"- {message}" for message in rejected_messages] or ["- none"])
    lines.extend(
        [
            "",
            "## Evidence Discipline",
            "- LLM output can refine comparison text but cannot introduce unknown prior work.",
            "- Strong novelty is downgraded unless source coverage, retrieval, citation expansion, and missing-search gates pass.",
            "- Disagreement with the deterministic comparator is marked as contested unless locator-backed evidence supports it.",
        ]
    )
    Path(state.run_dir, "novelty_gate_llm.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _paper_payload(state: ResearchRunState, paper: Paper) -> dict[str, Any]:
    spans = [span for span in state.evidence_spans if span.paper_id == paper.id][:6]
    sections = [section for section in state.paper_sections if section.paper_id == paper.id][:5]
    note = next((item for item in state.paper_notes if item.paper_id == paper.id), None)
    return {
        "id": paper.id,
        "title": paper.title,
        "abstract": paper.abstract,
        "year": paper.year,
        "source": paper.source,
        "note_summary": note.one_sentence_summary if note else "",
        "sections": [
            {
                "id": section.id,
                "title": section.title,
                "section_type": section.section_type,
                "text": section.text[:1000],
            }
            for section in sections
        ],
        "evidence_locators": [
            {"id": span.id, "locator": span.locator, "evidence_type": span.evidence_type, "quote": span.quote[:500]} for span in spans
        ],
    }


def _citation_payload(state: ResearchRunState) -> dict[str, Any]:
    graph = state.citation_graph
    if graph is None:
        return {"edges": [], "unresolved_references": []}
    return {
        "edges": [
            {
                "source_paper_id": edge.source_paper_id,
                "target_paper_id": edge.target_paper_id,
                "edge_type": edge.edge_type,
                "source": edge.source,
            }
            for edge in graph.edges[:40]
        ],
        "unresolved_references": graph.unresolved_references[:20],
    }


def _coverage_payload(state: ResearchRunState) -> dict[str, Any]:
    coverage = state.source_coverage
    if coverage is None:
        return {"confidence": "low", "coverage_warnings": ["No source coverage report is available."]}
    return {
        "searched_sources": coverage.searched_sources,
        "papers_by_source": coverage.papers_by_source,
        "papers_with_full_text": coverage.papers_with_full_text,
        "papers_abstract_only": coverage.papers_abstract_only,
        "failed_sources": coverage.failed_sources,
        "coverage_warnings": coverage.coverage_warnings,
        "confidence": coverage.confidence,
    }


def _targets(state: ResearchRunState, *, gap_id: str | None, all_targets: bool) -> list[tuple[str, str, Gap | None]]:
    gaps = [gap for gap in state.gaps if all_targets or gap_id is None or gap.id == gap_id]
    if gap_id is not None and not all_targets:
        hypotheses = [hypothesis for hypothesis in state.hypotheses if hypothesis.id == gap_id or hypothesis.gap_id == gap_id]
    else:
        hypotheses = list(state.hypotheses) if all_targets else []
    gap_by_id = {gap.id: gap for gap in state.gaps}
    targets: list[tuple[str, str, Gap | None]] = [(gap.id, _gap_summary(gap), gap) for gap in gaps]
    targets.extend(
        (hypothesis.id, f"{hypothesis.text} {hypothesis.rationale}".strip(), gap_by_id.get(hypothesis.gap_id)) for hypothesis in hypotheses
    )
    if gap_id is not None and not targets:
        raise ValueError(f"No gap or hypothesis found for {gap_id}")
    return targets


def _citation_expansion_ran(state: ResearchRunState) -> bool:
    if state.citation_graph is not None and state.citation_graph.edges:
        return True
    return any(record.purpose == "citation_expansion" for record in state.search_queries)


def _add_novelty_claims(
    state: ResearchRunState,
    assessments: list[NoveltyAssessment],
    contested_targets: list[str],
) -> ClaimLedger:
    ledger = ClaimLedger(state.claims)
    contested = set(contested_targets)
    existing = {claim.notes for claim in state.claims if claim.created_by_skill == NoveltyGateLLM.name}
    for assessment in assessments:
        if not assessment.closest_prior_work:
            continue
        note_key = f"llm-novelty-assessment:{assessment.target_gap_or_hypothesis_id}"
        if note_key in existing:
            continue
        claim = ledger.add_claim(
            text=(
                f"LLM-assisted novelty verdict for {assessment.target_gap_or_hypothesis_id}: "
                f"{assessment.verdict} with {assessment.novelty_strength} novelty strength."
            ),
            claim_type="novelty",
            confidence=assessment.confidence,
            source_paper_ids=[item.split(":", 1)[0] for item in assessment.closest_prior_work],
            created_by_skill=NoveltyGateLLM.name,
            needs_verification=True,
            notes=note_key,
            closest_prior_work=assessment.closest_prior_work,
            reasoning_summary="LLM-assisted novelty claim created from validated closest-prior-work dossier.",
        )
        for item in assessment.closest_prior_work[:3]:
            paper_id = item.split(":", 1)[0]
            ledger.add_evidence(
                claim.id,
                Evidence(
                    source_id=paper_id,
                    source_paper_id=paper_id,
                    quote=item,
                    locator="validated-prior-work",
                    confidence=assessment.confidence,
                    notes=assessment.decisive_difference_needed,
                ),
            )
        if assessment.target_gap_or_hypothesis_id in contested or assessment.verdict in {"reject", "revise"}:
            ledger.mark_contested(claim.id, confidence=assessment.confidence)
        else:
            ledger.mark_uncertain(claim.id, confidence=assessment.confidence)
    return ledger


def _replace_dossiers(existing: list[NoveltyDossier], new_items: list[NoveltyDossier]) -> list[NoveltyDossier]:
    replacing = {item.target_id for item in new_items}
    return [item for item in existing if item.target_id not in replacing] + new_items


def _replace_assessments(existing: list[NoveltyAssessment], new_items: list[NoveltyAssessment]) -> list[NoveltyAssessment]:
    replacing = {item.target_gap_or_hypothesis_id for item in new_items}
    return [item for item in existing if item.target_gap_or_hypothesis_id not in replacing] + new_items


def _gap_summary(gap: Gap) -> str:
    return (
        " ".join(
            part for part in [gap.title, gap.description, gap.why_existing_work_does_not_solve_it, gap.minimum_experiment_needed] if part
        ).strip()
        or gap.id
    )


def _gap_novelty_status(assessment: NoveltyAssessment) -> str:
    if assessment.verdict == "reject":
        return "likely_not_new"
    if assessment.verdict == "revise":
        return "weak"
    if assessment.verdict == "pursue":
        return assessment.novelty_strength
    return "unchecked"


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value) or "target"
