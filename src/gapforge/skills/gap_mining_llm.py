"""Optional LLM-backed gap mining with retrieval-backed counterevidence."""

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
from gapforge.models import (
    Evidence,
    EvidenceSpan,
    Gap,
    GapEvidenceMatrix,
    GapEvidenceRow,
    PaperNote,
    Provenance,
    ResearchRunState,
    RetrievalResult,
)
from gapforge.retrieval.hybrid import retrieval_candidates_for_state
from gapforge.review.audit import is_rejected, locked_object_ids
from gapforge.skills.base import Skill
from gapforge.skills.gap_mining import GAP_TYPES, GapMining
from gapforge.state import utc_now_iso

COUNTEREVIDENCE_QUERIES = [
    "repeated limitations",
    "missing metrics",
    "missing datasets",
    "unrealistic assumptions",
    "counterevidence already solves proposed gap",
    "adjacent-field transfer mechanisms",
]


class GapMiningLLM(Skill):
    """LLM synthesis layer that accepts only evidence-linked gap candidates."""

    name = "gap-mining-llm"

    def __init__(self, client: LLMClient | None = None, runtime_config: LLMRuntimeConfig | None = None) -> None:
        self.client = client
        self.runtime_config = runtime_config

    def run(self, state: ResearchRunState, *, force: bool = False) -> ResearchRunState:
        return self.mine_with_llm(state, force=force)

    def mine_with_llm(
        self,
        state: ResearchRunState,
        *,
        dry_run_prompts: bool = False,
        fake: bool = False,
        force: bool = False,
        allow_deterministic_fallback: bool = True,
    ) -> ResearchRunState:
        runtime = self.runtime_config or LLMRuntimeConfig.from_env()
        mode = "fake" if fake else runtime.mode
        if mode == "off" and not dry_run_prompts:
            if allow_deterministic_fallback:
                return GapMining().run(state, force=force)
            raise ValueError("LLM gap mining requires GAPFORGE_LLM_MODE=provider|fake|prompt-pack, --fake, or --dry-run-prompts.")

        retrieval_bundle = _retrieve_gap_context(state)
        prompt = _build_prompt(state, retrieval_bundle)
        prompt_path = _write_prompt(state, prompt)
        if dry_run_prompts or mode == "prompt-pack":
            _write_report(
                state,
                [
                    f"Mode: {mode}",
                    "Prompt file written; no model calls were made.",
                    f"Retrieval context groups: {len(retrieval_bundle)}",
                ],
                prompt_path=prompt_path,
                accepted=[],
                rejected=[],
            )
            return state

        client = self.client or _client_for_mode(mode, runtime, state.run_dir, self.name)
        if isinstance(client, (FakeLLMClient, ProviderLLMClient)):
            client.prompt_pack_id = prompt_path.name
        payload = client.complete_json(
            prompt,
            schema_name="gap-mining",
            system=_system_prompt(),
            temperature=0.0,
            max_tokens=runtime.max_tokens,
        )
        JSONGuard().validate(payload, schema_name="gap-mining")
        accepted, matrices, rejected = _validated_gaps_from_payload(state, payload, retrieval_bundle)
        if not force:
            accepted, matrices = _respect_human_reviews(state, accepted, matrices)
        _merge_gap_outputs(state, accepted, matrices)
        state.claims = _add_gap_claims(state, accepted).claims
        self.mark_complete(state)
        _write_report(
            state,
            [f"Mode: {mode}", f"Accepted gaps: {len(accepted)}", f"Rejected/downgraded ideas: {len(rejected)}"],
            prompt_path,
            accepted,
            rejected,
        )
        return state


def _client_for_mode(mode: str, runtime: LLMRuntimeConfig, run_dir: str, skill_name: str) -> LLMClient:
    if mode == "fake":
        return FakeLLMClient(run_dir=run_dir, skill_name=skill_name, config=LLMRuntimeConfig(mode="fake"))
    if mode == "provider":
        return ProviderLLMClient(config=runtime, run_dir=run_dir, skill_name=skill_name)
    raise ValueError(f"LLM mode {mode!r} does not create a gap-mining client.")


def _retrieve_gap_context(state: ResearchRunState) -> dict[str, list[RetrievalResult]]:
    context: dict[str, list[RetrievalResult]] = {}
    for query in COUNTEREVIDENCE_QUERIES:
        full_query = f"{state.topic.text} {query}"
        try:
            results, _paper_ids = retrieval_candidates_for_state(state, full_query, top_k=8)
        except (FileNotFoundError, ValueError, OSError, RuntimeError):
            results = []
        context[query] = results
    return context


def _build_prompt(state: ResearchRunState, retrieval_bundle: dict[str, list[RetrievalResult]]) -> str:
    payload = {
        "topic": state.topic.text,
        "paper_notes": [_note_payload(note) for note in state.paper_notes[:30]],
        "evidence_spans": [_span_payload(span) for span in state.evidence_spans[:80]],
        "claim_ledger": [
            {
                "id": claim.id,
                "type": claim.type,
                "status": claim.status,
                "confidence": claim.confidence,
                "text": claim.text,
                "source_paper_ids": claim.source_paper_ids,
            }
            for claim in state.claims[:80]
        ],
        "source_coverage": _coverage_payload(state),
        "existing_gap_evidence_matrices": [
            {
                "gap_id": matrix.gap_id,
                "confidence": matrix.confidence,
                "papers_supporting": matrix.papers_supporting,
                "papers_countering": matrix.papers_countering,
            }
            for matrix in state.gap_evidence_matrices[:30]
        ],
        "retrieval_results": {query: [_retrieval_payload(result) for result in results] for query, results in retrieval_bundle.items()},
        "output_schema": schema_for("gap-mining"),
    }
    return (
        "You are GapForge Gap Mining v3. Return JSON only for the provided schema.\n"
        "Propose sharper research gaps, but every accepted gap must be grounded in EvidenceSpan locators "
        "or clearly labeled abstract-only.\n"
        "Use retrieval results to look for counterevidence and prior work that may dissolve the gap.\n"
        "Each gap must include risk_that_gap_is_fake and counterevidence_search_summary.\n"
        "High confidence is only allowed with multiple supporting papers or strong full-text evidence and a counterevidence search.\n"
        "Do not invent citations, paper IDs, locators, datasets, or results.\n"
        "Store concise public reasoning summaries only, not hidden chain-of-thought.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def _system_prompt() -> str:
    return "You are a skeptical research-gap auditor. Return valid JSON only and cite EvidenceSpan locators."


def _write_prompt(state: ResearchRunState, prompt: str) -> Path:
    prompt_dir = Path(state.run_dir) / "prompt_packs"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    path = prompt_dir / "gap-mining-llm.md"
    path.write_text(f"# Gap Mining LLM Prompt\n\n```text\n{prompt}\n```\n", encoding="utf-8")
    return path


def _validated_gaps_from_payload(
    state: ResearchRunState,
    payload: dict[str, Any],
    retrieval_bundle: dict[str, list[RetrievalResult]],
) -> tuple[list[Gap], list[GapEvidenceMatrix], list[str]]:
    accepted: list[Gap] = []
    matrices: list[GapEvidenceMatrix] = []
    rejected: list[str] = []
    for index, raw in enumerate(payload.get("gaps", []), start=1):
        if not isinstance(raw, dict):
            rejected.append("Skipped non-object gap payload.")
            continue
        title = str(raw.get("title", "")).strip()
        if not title:
            rejected.append("Skipped gap without title.")
            continue
        if _title_human_rejected(state, title):
            rejected.append(f"{title}: skipped because a human rejected the matching gap.")
            continue
        support_spans = _valid_spans(state, _list_strings(raw.get("supporting_locators") or raw.get("supporting_evidence")))
        counter_spans = _valid_spans(state, _list_strings(raw.get("counterevidence_locators") or raw.get("counterevidence")))
        explicit_reason = str(raw.get("explicit_reason", "")).strip()
        abstract_only = _abstract_only_reason_is_allowed(state, explicit_reason)
        if not support_spans and not abstract_only:
            rejected.append(f"{title}: rejected because no supporting locator or valid abstract-only reason was supplied.")
            continue
        if not str(raw.get("risk_that_gap_is_fake", "")).strip():
            rejected.append(f"{title}: rejected because risk_that_gap_is_fake is missing.")
            continue
        counter_summary = str(raw.get("counterevidence_search_summary", "")).strip()
        confidence = _validated_confidence(
            state,
            str(raw.get("confidence", "low")),
            support_spans,
            counter_spans,
            abstract_only,
            counter_summary,
        )
        if not counter_summary:
            counter_summary = "No counterevidence search summary supplied by model; confidence downgraded."
            confidence = "low"
            rejected.append(f"{title}: downgraded because counterevidence search summary was missing.")
        gap = Gap(
            id=_gap_id(title, index, state),
            title=title,
            type=str(raw.get("type", "evaluation gap")) if str(raw.get("type", "")) in GAP_TYPES else "evaluation gap",
            description=str(raw.get("description", "")).strip(),
            supporting_paper_ids=_dedupe([span.paper_id for span in support_spans] + _abstract_supporting_papers(state, abstract_only)),
            why_existing_work_does_not_solve_it=str(raw.get("why_existing_work_does_not_solve_it") or counter_summary),
            why_it_matters=str(raw.get("why_it_matters") or f"This candidate may affect research decisions for {state.topic.text}."),
            possible_research_questions=_list_strings(raw.get("possible_research_questions")),
            minimum_experiment_needed=str(raw.get("minimum_experiment_needed", "")).strip(),
            risk_that_gap_is_fake=_risk_with_counter_summary(str(raw.get("risk_that_gap_is_fake", "")).strip(), counter_summary),
            confidence=confidence,
            novelty_status=str(raw.get("novelty_status", "unchecked")) or "unchecked",
            linked_paper_ids=_dedupe([span.paper_id for span in support_spans + counter_spans]),
            explicit_reason=explicit_reason,
            provenance=Provenance(
                created_by_skill=GapMiningLLM.name,
                source_ids=[span.id for span in support_spans + counter_spans],
                timestamp=utc_now_iso(),
                reasoning_summary=str(raw.get("reasoning_summary") or "LLM gap accepted after locator and counterevidence validation."),
            ),
        )
        matrix = _matrix_for_gap(state, gap, support_spans, counter_spans, counter_summary, retrieval_bundle)
        if not matrix.evidence_rows and not explicit_reason:
            rejected.append(f"{title}: rejected because no evidence matrix rows could be built.")
            continue
        gap.confidence = _min_confidence(gap.confidence, matrix.confidence)
        accepted.append(gap)
        matrices.append(matrix)
    return accepted, matrices, rejected


def _matrix_for_gap(
    state: ResearchRunState,
    gap: Gap,
    support_spans: list[EvidenceSpan],
    counter_spans: list[EvidenceSpan],
    counter_summary: str,
    retrieval_bundle: dict[str, list[RetrievalResult]],
) -> GapEvidenceMatrix:
    section_by_id = {section.id: section for section in state.paper_sections}
    rows: list[GapEvidenceRow] = []
    for span in support_spans:
        rows.append(_row_from_span(span, "supports", section_by_id))
    for span in counter_spans:
        rows.append(_row_from_span(span, "counters", section_by_id))
    rows.extend(_retrieval_counter_rows(gap, retrieval_bundle, support_paper_ids={span.paper_id for span in support_spans}))
    if counter_summary:
        rows.append(
            GapEvidenceRow(
                paper_id="",
                claim_or_note_id="llm-counterevidence-summary",
                evidence_type="counterevidence-search",
                text=counter_summary,
                supports_or_counters="contextual",
                locator="gap-mining-llm",
            )
        )
    papers_supporting = _dedupe([row.paper_id for row in rows if row.paper_id and row.supports_or_counters == "supports"])
    papers_countering = _dedupe([row.paper_id for row in rows if row.paper_id and row.supports_or_counters == "counters"])
    confidence = _matrix_confidence(state, rows, papers_supporting, papers_countering)
    return GapEvidenceMatrix(
        gap_id=gap.id,
        evidence_rows=_dedupe_rows(rows),
        papers_supporting=papers_supporting,
        papers_countering=papers_countering,
        repeated_limitation_count=_row_paper_count(rows, "limitation"),
        missing_metric_count=_row_paper_count(rows, "missing-metric"),
        missing_dataset_count=_row_paper_count(rows, "missing-dataset"),
        assumption_pattern_count=_row_paper_count(rows, "assumption"),
        confidence=confidence,
        provenance=Provenance(
            created_by_skill=GapMiningLLM.name,
            source_ids=[row.evidence_span_id for row in rows if row.evidence_span_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Evidence matrix built from LLM-cited locators plus retrieval counterevidence context.",
        ),
    )


def _validated_confidence(
    state: ResearchRunState,
    requested: str,
    support_spans: list[EvidenceSpan],
    counter_spans: list[EvidenceSpan],
    abstract_only: bool,
    counter_summary: str,
) -> str:
    requested = requested if requested in {"low", "medium", "high"} else "low"
    support_papers = {span.paper_id for span in support_spans}
    strong_full_text = bool(support_spans) and all(_span_has_section(state, span) for span in support_spans)
    if abstract_only or not counter_summary:
        return "low"
    if requested == "high" and not (len(support_papers) >= 2 or strong_full_text):
        return "medium"
    if requested == "high" and counter_spans:
        return "medium"
    if requested == "medium" and not support_spans:
        return "low"
    return requested


def _matrix_confidence(state: ResearchRunState, rows: list[GapEvidenceRow], support_papers: list[str], counter_papers: list[str]) -> str:
    if counter_papers:
        return "low"
    span_rows = [row for row in rows if row.evidence_span_id and row.supports_or_counters == "supports"]
    if len(support_papers) >= 2 and len(span_rows) >= 2 and not _mostly_abstract_only(state, support_papers):
        return "high"
    if span_rows and not _mostly_abstract_only(state, support_papers):
        return "medium"
    return "low"


def _row_paper_count(rows: list[GapEvidenceRow], evidence_type: str) -> int:
    return len({row.paper_id for row in rows if row.evidence_type == evidence_type and row.supports_or_counters == "supports"})


def _row_from_span(span: EvidenceSpan, supports_or_counters: str, section_by_id: dict[str, Any]) -> GapEvidenceRow:
    section = section_by_id.get(span.section_id)
    return GapEvidenceRow(
        paper_id=span.paper_id,
        evidence_span_id=span.id,
        evidence_type=span.evidence_type,
        text=span.quote,
        supports_or_counters=supports_or_counters,
        section_type=getattr(section, "section_type", ""),
        locator=span.locator or span.id,
    )


def _retrieval_counter_rows(
    gap: Gap,
    retrieval_bundle: dict[str, list[RetrievalResult]],
    *,
    support_paper_ids: set[str],
) -> list[GapEvidenceRow]:
    rows: list[GapEvidenceRow] = []
    terms = set(_tokens(gap.title + " " + gap.description))
    for query, results in retrieval_bundle.items():
        for result in results:
            if not result.paper_id or result.paper_id in support_paper_ids:
                continue
            text = result.text_snippet.lower()
            if not (terms & set(_tokens(text))):
                continue
            if not any(marker in text for marker in ["already", "reports", "evaluates", "benchmark", "false-positive", "false positive"]):
                continue
            rows.append(
                GapEvidenceRow(
                    paper_id=result.paper_id,
                    claim_or_note_id=f"retrieval:{result.object_id}",
                    evidence_span_id=result.object_id if result.object_type == "evidence_span" else "",
                    evidence_type="counterevidence",
                    text=result.text_snippet,
                    supports_or_counters="counters",
                    section_type=str(result.metadata.get("section_type", "")),
                    locator=result.locator or result.document_id or query,
                )
            )
    return rows[:4]


def _merge_gap_outputs(state: ResearchRunState, accepted: list[Gap], matrices: list[GapEvidenceMatrix]) -> None:
    gap_by_id = {gap.id: gap for gap in state.gaps}
    for gap in accepted:
        gap_by_id[gap.id] = gap
    state.gaps = list(gap_by_id.values())
    matrix_by_id = {matrix.gap_id: matrix for matrix in state.gap_evidence_matrices}
    for matrix in matrices:
        matrix_by_id[matrix.gap_id] = matrix
    state.gap_evidence_matrices = list(matrix_by_id.values())


def _respect_human_reviews(
    state: ResearchRunState,
    gaps: list[Gap],
    matrices: list[GapEvidenceMatrix],
) -> tuple[list[Gap], list[GapEvidenceMatrix]]:
    locked_ids = locked_object_ids(state, "gap")
    allowed = [gap for gap in gaps if gap.id not in locked_ids and not is_rejected(state, "gap", gap.id)]
    allowed_ids = {gap.id for gap in allowed}
    return allowed, [matrix for matrix in matrices if matrix.gap_id in allowed_ids]


def _add_gap_claims(state: ResearchRunState, gaps: list[Gap]) -> ClaimLedger:
    ledger = ClaimLedger(state.claims)
    matrix_by_gap = {matrix.gap_id: matrix for matrix in state.gap_evidence_matrices}
    for gap in gaps:
        matrix = matrix_by_gap.get(gap.id)
        supporting_rows = [row for row in (matrix.evidence_rows if matrix else []) if row.supports_or_counters == "supports"]
        claim = ledger.add_claim(
            f"LLM candidate {gap.type}: {gap.title}",
            "gap",
            created_by_skill=GapMiningLLM.name,
            confidence=gap.confidence,
            source_paper_ids=gap.supporting_paper_ids,
            needs_verification=True,
            notes=f"Risk: {gap.risk_that_gap_is_fake}",
            reasoning_summary="LLM gap claim added after locator and evidence-matrix validation.",
        )
        for row in supporting_rows[:3]:
            ledger.add_evidence(
                claim.id,
                Evidence(
                    source_id=row.evidence_span_id or row.paper_id,
                    source_paper_id=row.paper_id,
                    quote=row.text,
                    locator=row.locator or row.paper_id,
                    confidence=gap.confidence,
                    notes="Evidence row from LLM gap evidence matrix.",
                ),
            )
        ledger.mark_uncertain(claim.id, confidence=gap.confidence if gap.confidence in {"low", "medium"} else "medium")
    return ledger


def _valid_spans(state: ResearchRunState, locators: list[str]) -> list[EvidenceSpan]:
    by_locator = {span.locator: span for span in state.evidence_spans if span.locator}
    by_id = {span.id: span for span in state.evidence_spans}
    spans: list[EvidenceSpan] = []
    seen: set[str] = set()
    for locator in locators:
        span = by_locator.get(locator) or by_id.get(locator)
        if span is not None and span.id not in seen:
            spans.append(span)
            seen.add(span.id)
    return spans


def _title_human_rejected(state: ResearchRunState, title: str) -> bool:
    normalized = _normalize_title(title)
    return any(_normalize_title(gap.title) == normalized and is_rejected(state, "gap", gap.id) for gap in state.gaps)


def _abstract_only_reason_is_allowed(state: ResearchRunState, explicit_reason: str) -> bool:
    if not explicit_reason:
        return False
    reason = explicit_reason.lower()
    if "abstract" not in reason and "metadata" not in reason:
        return False
    if state.source_coverage and state.source_coverage.papers_abstract_only:
        return True
    return any(note.source_basis != "full text" for note in state.paper_notes)


def _abstract_supporting_papers(state: ResearchRunState, abstract_only: bool) -> list[str]:
    if not abstract_only:
        return []
    return [note.paper_id for note in state.paper_notes if note.source_basis != "full text"][:3]


def _span_has_section(state: ResearchRunState, span: EvidenceSpan) -> bool:
    section_ids = {section.id for section in state.paper_sections}
    return span.section_id in section_ids


def _mostly_abstract_only(state: ResearchRunState, paper_ids: list[str]) -> bool:
    notes = [note for note in state.paper_notes if note.paper_id in set(paper_ids)]
    return bool(notes) and sum(1 for note in notes if note.source_basis != "full text") >= max(1, len(notes) // 2)


def _risk_with_counter_summary(risk: str, counter_summary: str) -> str:
    if not counter_summary:
        return risk
    return f"{risk} Counterevidence search: {counter_summary}".strip()


def _dedupe_rows(rows: list[GapEvidenceRow]) -> list[GapEvidenceRow]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[GapEvidenceRow] = []
    for row in rows:
        key = (row.paper_id, row.evidence_span_id, row.evidence_type, row.text[:120])
        if key not in seen:
            deduped.append(row)
            seen.add(key)
    return deduped


def _min_confidence(left: str, right: str) -> str:
    order = {"low": 1, "medium": 2, "high": 3}
    return left if order.get(left, 1) <= order.get(right, 1) else right


def _gap_id(title: str, index: int, state: ResearchRunState) -> str:
    base = f"gap-llm-{abs(hash(title.lower())) % 100000}"
    existing = {gap.id for gap in state.gaps}
    if base not in existing:
        return base
    return f"{base}-{index}"


def _note_payload(note: PaperNote) -> dict[str, Any]:
    return {
        "paper_id": note.paper_id,
        "source_basis": note.source_basis,
        "confidence": note.confidence,
        "summary": note.one_sentence_summary or note.summary,
        "metrics": note.metrics,
        "datasets": note.datasets,
        "stated_limitations": note.stated_limitations,
        "unstated_limitations": note.unstated_limitations,
        "what_it_cannot_answer": note.what_it_cannot_answer,
    }


def _span_payload(span: EvidenceSpan) -> dict[str, Any]:
    return {
        "id": span.id,
        "paper_id": span.paper_id,
        "section_id": span.section_id,
        "locator": span.locator,
        "evidence_type": span.evidence_type,
        "quote": span.quote,
        "confidence": span.confidence,
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
        "coverage_warnings": coverage.coverage_warnings,
        "confidence": coverage.confidence,
    }


def _retrieval_payload(result: RetrievalResult) -> dict[str, Any]:
    return {
        "document_id": result.document_id,
        "object_type": result.object_type,
        "object_id": result.object_id,
        "paper_id": result.paper_id,
        "score": result.score,
        "locator": result.locator,
        "snippet": result.text_snippet,
    }


def _write_report(
    state: ResearchRunState,
    summary_lines: list[str],
    prompt_path: Path,
    accepted: list[Gap],
    rejected: list[str],
) -> None:
    lines = ["# LLM Gap Mining", ""]
    lines.extend(summary_lines)
    lines.extend(["", f"- Prompt file: `{prompt_path}`", ""])
    lines.append("## Accepted Gaps")
    if accepted:
        for gap in accepted:
            lines.extend(
                [
                    f"### {gap.title}",
                    "",
                    f"- Gap ID: `{gap.id}`",
                    f"- Type: {gap.type}",
                    f"- Confidence: {gap.confidence}",
                    f"- Supporting papers: {', '.join(gap.supporting_paper_ids) if gap.supporting_paper_ids else 'none'}",
                    f"- Risk that gap is fake: {gap.risk_that_gap_is_fake}",
                    "",
                ]
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Rejected Or Downgraded Model Ideas"])
    lines.extend([f"- {item}" for item in rejected] or ["- none"])
    lines.extend(
        [
            "",
            "## Evidence Discipline",
            "- Unsupported model ideas are rejected or kept low-confidence when abstract-only.",
            "- Counterevidence search summaries are required for accepted candidates.",
            "- Gap evidence matrices are built from validated locators and retrieval context.",
        ]
    )
    Path(state.run_dir, "gap_mining_llm.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _tokens(text: str) -> list[str]:
    return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if len(token) > 3]


def _normalize_title(title: str) -> str:
    return " ".join(_tokens(title))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
