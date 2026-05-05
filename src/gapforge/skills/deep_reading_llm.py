"""Optional LLM-backed deep reading with strict evidence-locator grounding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.claim_ledger import VALID_CLAIM_TYPES, ClaimLedger
from gapforge.llm.base import LLMClient
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.json_guard import JSONGuard
from gapforge.llm.providers import ProviderLLMClient
from gapforge.llm.schemas import schema_for
from gapforge.models import Evidence, EvidenceSpan, Paper, PaperNote, PaperSection, Provenance, ResearchRunState
from gapforge.skills.base import Skill
from gapforge.skills.deep_reading import DeepReading
from gapforge.state import utc_now_iso

RESULT_SECTION_TYPES = {"results", "experiments", "conclusion"}
METHOD_SECTION_TYPES = {"method"}
LIMITATION_SECTION_TYPES = {"limitations", "discussion", "conclusion"}


class DeepReadingLLM(Skill):
    """Use an opt-in LLM to improve paper notes without trusting unsupported output."""

    name = "deep-reading-llm"

    def __init__(self, client: LLMClient | None = None, runtime_config: LLMRuntimeConfig | None = None) -> None:
        self.client = client
        self.runtime_config = runtime_config
        self._last_report: list[str] = []

    def run(self, state: ResearchRunState) -> ResearchRunState:
        return self.read_papers(state, self._selected_papers(state))

    def read_papers(
        self,
        state: ResearchRunState,
        papers: list[Paper],
        *,
        dry_run_prompts: bool = False,
        fake: bool = False,
        allow_deterministic_fallback: bool = True,
    ) -> ResearchRunState:
        runtime = self.runtime_config or LLMRuntimeConfig.from_env()
        mode = "fake" if fake else runtime.mode
        if mode == "off" and not dry_run_prompts:
            if allow_deterministic_fallback:
                return DeepReading().read_papers(state, papers)
            raise ValueError("LLM deep reading requires GAPFORGE_LLM_MODE=provider|fake|prompt-pack, --fake, or --dry-run-prompts.")

        selected = papers or []
        prompt_paths: list[Path] = []
        prompts: list[tuple[Paper, str, str]] = []
        for paper in selected:
            prompt = _build_prompt(state, paper)
            prompt_path = _write_prompt(state, paper, prompt)
            prompt_paths.append(prompt_path)
            prompts.append((paper, prompt, prompt_path.name))

        if dry_run_prompts or mode == "prompt-pack":
            self._last_report = [
                f"Mode: {mode}",
                f"Papers selected: {len(selected)}",
                f"Prompt files written: {len(prompt_paths)}",
                "No model calls were made; run with GAPFORGE_LLM_MODE=fake/provider or --fake to update notes.",
            ]
            _write_report(state, self._last_report, prompt_paths)
            return state

        client = self.client or _client_for_mode(mode, runtime, state.run_dir, self.name)
        accepted_notes: list[PaperNote] = []
        dropped_items: list[str] = []
        ledger = ClaimLedger(state.claims)
        for paper, prompt, prompt_pack_id in prompts:
            if isinstance(client, (FakeLLMClient, ProviderLLMClient)):
                client.prompt_pack_id = prompt_pack_id
            payload = client.complete_json(
                prompt,
                schema_name="deep-reading",
                system=_system_prompt(),
                temperature=0.0,
                max_tokens=runtime.max_tokens,
            )
            JSONGuard().validate(payload, schema_name="deep-reading")
            note, drops = _note_from_payload(state, paper, payload)
            if note is None:
                note = _safe_low_confidence_note(state, paper, "LLM response did not contain an acceptable note for this paper.")
            accepted_notes.append(note)
            dropped_items.extend(drops)
            _add_grounded_claims(ledger, state, paper, payload)

        state.paper_notes = _merge_notes(state.paper_notes, accepted_notes)
        state.claims = ledger.claims
        self.mark_complete(state)
        self._last_report = [
            f"Mode: {mode}",
            f"Papers selected: {len(selected)}",
            f"Notes updated: {len(accepted_notes)}",
            f"Dropped or downgraded unsupported items: {len(dropped_items)}",
        ] + [f"- {item}" for item in dropped_items[:20]]
        _write_report(state, self._last_report, prompt_paths)
        return state

    def _selected_papers(self, state: ResearchRunState) -> list[Paper]:
        by_id = {paper.id: paper for paper in state.papers}
        if state.paper_triage is None:
            return state.papers[:5]
        selected_ids = [decision.paper_id for decision in state.paper_triage.decisions if decision.tier in {"Tier 1", "Tier 2"}]
        return [by_id[paper_id] for paper_id in selected_ids if paper_id in by_id]


def _client_for_mode(mode: str, runtime: LLMRuntimeConfig, run_dir: str, skill_name: str) -> LLMClient:
    if mode == "fake":
        return FakeLLMClient(run_dir=run_dir, skill_name=skill_name, config=LLMRuntimeConfig(mode="fake"))
    if mode == "provider":
        return ProviderLLMClient(config=runtime, run_dir=run_dir, skill_name=skill_name)
    raise ValueError(f"LLM mode {mode!r} does not create a deep-reading client.")


def _build_prompt(state: ResearchRunState, paper: Paper) -> str:
    sections = _sections_for_paper(state, paper.id)
    spans = _spans_for_paper(state, paper.id)
    retrieval_context = _retrieval_context(state, paper.id)
    payload = {
        "topic": state.topic.text,
        "paper": {
            "id": paper.id,
            "title": paper.title,
            "authors": paper.authors,
            "year": paper.year,
            "venue": paper.venue,
            "source": paper.source,
            "doi": paper.doi,
            "arxiv_id": paper.arxiv_id,
            "url": paper.url,
            "abstract": paper.abstract,
        },
        "section_excerpts": [_section_excerpt(section) for section in sections],
        "existing_evidence_span_locators": [_span_payload(span) for span in spans],
        "retrieval_context": retrieval_context,
        "output_schema": schema_for("deep-reading"),
    }
    return (
        "You are GapForge Deep Reading v3. Produce JSON only for the provided schema.\n"
        "Every claim, result, method, dataset, metric, or limitation must cite an existing EvidenceSpan locator.\n"
        "If a field is unsupported by the provided locators, use an empty list or mark it unknown in limitations.\n"
        "Main results require result/evaluation/conclusion evidence. Methods require method/approach evidence.\n"
        "Limitations require limitation/discussion/conclusion evidence or must be explicitly labeled inferred.\n"
        "Do not invent citations, papers, numbers, datasets, metrics, or results.\n"
        "Store only concise public reasoning summaries, not hidden chain-of-thought.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def _system_prompt() -> str:
    return (
        "You are a citation-grounded research assistant. Return valid JSON only. "
        "Do not provide hidden chain-of-thought. Use uncertainty when evidence is missing."
    )


def _write_prompt(state: ResearchRunState, paper: Paper, prompt: str) -> Path:
    prompt_dir = Path(state.run_dir) / "prompt_packs"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    path = prompt_dir / f"deep-reading-llm-{_safe_id(paper.id)}.md"
    path.write_text(f"# Deep Reading LLM Prompt: {paper.id}\n\n```text\n{prompt}\n```\n", encoding="utf-8")
    return path


def _note_from_payload(state: ResearchRunState, paper: Paper, payload: dict[str, Any]) -> tuple[PaperNote | None, list[str]]:
    notes = [item for item in payload.get("paper_notes", []) if isinstance(item, dict) and item.get("paper_id") == paper.id]
    if not notes:
        return None, [f"{paper.id}: missing paper_note in LLM payload"]
    raw = notes[0]
    valid_spans = _valid_spans(state, paper.id, raw.get("evidence_locators", []))
    drops: list[str] = []
    if not valid_spans:
        drops.append(f"{paper.id}: note had no valid EvidenceSpan locators; substantive fields were dropped")
        return _safe_low_confidence_note(state, paper, "LLM note had no valid EvidenceSpan locators."), drops

    result_spans = _spans_in_allowed_sections(state, valid_spans, RESULT_SECTION_TYPES, evidence_types={"result"})
    method_spans = _spans_in_allowed_sections(state, valid_spans, METHOD_SECTION_TYPES, title_terms={"approach", "method"})
    limitation_spans = _spans_in_allowed_sections(
        state,
        valid_spans,
        LIMITATION_SECTION_TYPES,
        evidence_types={"limitation"},
        title_terms={"limitation", "discussion", "conclusion"},
    )

    main_results = _list_strings(raw.get("main_results"))
    if main_results and not result_spans:
        drops.append(f"{paper.id}: dropped main_results without result/evaluation/conclusion locator")
        main_results = []
    method = _list_strings(raw.get("method"))
    if method and not method_spans:
        drops.append(f"{paper.id}: dropped method statements without method/approach locator")
        method = []
    limitations = _list_strings(raw.get("limitations"))
    stated_limitations: list[str] = []
    unstated_limitations: list[str] = []
    if limitations and limitation_spans:
        stated_limitations = limitations
    elif limitations:
        unstated_limitations = [f"Inferred/unsupported by limitation section: {item}" for item in limitations]
        drops.append(f"{paper.id}: downgraded limitations without limitation/discussion/conclusion locator")

    confidence = str(raw.get("confidence", "low"))
    if confidence == "high" and not _has_full_text_support(state, paper.id, valid_spans):
        confidence = "medium"
        drops.append(f"{paper.id}: downgraded high confidence because full-text locator coverage was insufficient")
    elif not valid_spans:
        confidence = "low"

    source_basis = "llm full text" if _sections_for_paper(state, paper.id) else "llm metadata/abstract only"
    note = PaperNote(
        paper_id=paper.id,
        citation_key=_citation_key(paper),
        one_sentence_summary=_summary_from_note(paper, raw),
        core_claims=_list_strings(raw.get("core_claims")),
        method=method,
        datasets=_list_strings(raw.get("datasets")),
        metrics=_list_strings(raw.get("metrics")),
        main_results=main_results,
        stated_limitations=stated_limitations,
        unstated_limitations=unstated_limitations,
        what_it_cannot_answer=_missing_to_cannot_answer(_list_strings(raw.get("missing_sections")), payload),
        relevance_to_topic="LLM-assisted note; verify against evidence locators before using as a conclusion.",
        confidence=confidence if confidence in {"low", "medium", "high"} else "low",
        quotes_or_evidence_snippets=[_evidence_from_span(span) for span in valid_spans],
        created_by_skill=DeepReadingLLM.name,
        source_basis=source_basis,
        summary=_summary_from_note(paper, raw),
        methods=method,
        limitations=stated_limitations + unstated_limitations,
        evidence=[_evidence_from_span(span) for span in valid_spans],
        sections_used=_list_strings(raw.get("sections_used")),
        missing_sections=_list_strings(raw.get("missing_sections")),
        provenance=Provenance(
            created_by_skill=DeepReadingLLM.name,
            source_ids=[paper.id] + [span.id for span in valid_spans],
            timestamp=utc_now_iso(),
            reasoning_summary=str(raw.get("reasoning_summary") or "LLM note accepted after EvidenceSpan locator validation."),
        ),
    )
    return note, drops


def _safe_low_confidence_note(state: ResearchRunState, paper: Paper, reason: str) -> PaperNote:
    source_basis = "llm full text" if _sections_for_paper(state, paper.id) else "llm metadata/abstract only"
    return PaperNote(
        paper_id=paper.id,
        citation_key=_citation_key(paper),
        one_sentence_summary=f"{paper.title}: LLM reading produced no supported substantive update.",
        what_it_cannot_answer=[reason],
        confidence="low",
        created_by_skill=DeepReadingLLM.name,
        source_basis=source_basis,
        summary=f"{paper.title}: LLM reading produced no supported substantive update.",
        provenance=Provenance(
            created_by_skill=DeepReadingLLM.name,
            source_ids=[paper.id],
            timestamp=utc_now_iso(),
            reasoning_summary="No substantive LLM fields were accepted because citation grounding was insufficient.",
        ),
    )


def _add_grounded_claims(ledger: ClaimLedger, state: ResearchRunState, paper: Paper, payload: dict[str, Any]) -> None:
    for raw_claim in payload.get("claims", []):
        if not isinstance(raw_claim, dict):
            continue
        text = str(raw_claim.get("text", "")).strip()
        if not text:
            continue
        claim_type = str(raw_claim.get("type") or raw_claim.get("claim_type") or "background")
        if claim_type not in VALID_CLAIM_TYPES:
            claim_type = "background"
        valid_spans = _valid_spans(state, paper.id, raw_claim.get("evidence_locators", []))
        if not valid_spans:
            continue
        evidence = [_evidence_from_span(span) for span in valid_spans]
        confidence = str(raw_claim.get("confidence", "medium"))
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"
        claim = ledger.add_claim(
            text=text,
            claim_type=claim_type,
            created_by_skill=DeepReadingLLM.name,
            confidence=confidence,
            source_paper_ids=[paper.id],
            needs_verification=False,
            notes="LLM-backed claim accepted only because all cited EvidenceSpan locators exist in this run.",
            reasoning_summary="Validated LLM claim against EvidenceSpan locator references before adding support.",
        )
        for item in evidence:
            ledger.add_evidence(claim.id, item)
        ledger.mark_supported(claim.id, confidence=confidence)


def _valid_spans(state: ResearchRunState, paper_id: str, raw_locators: Any) -> list[EvidenceSpan]:
    locators = _list_strings(raw_locators)
    by_locator = {span.locator: span for span in state.evidence_spans if span.paper_id == paper_id and span.locator}
    by_id = {span.id: span for span in state.evidence_spans if span.paper_id == paper_id}
    spans: list[EvidenceSpan] = []
    seen: set[str] = set()
    for locator in locators:
        span = by_locator.get(locator) or by_id.get(locator)
        if span is not None and span.id not in seen:
            spans.append(span)
            seen.add(span.id)
    return spans


def _spans_in_allowed_sections(
    state: ResearchRunState,
    spans: list[EvidenceSpan],
    section_types: set[str],
    *,
    evidence_types: set[str] | None = None,
    title_terms: set[str] | None = None,
) -> list[EvidenceSpan]:
    section_by_id = {section.id: section for section in state.paper_sections}
    matches = []
    for span in spans:
        section = section_by_id.get(span.section_id)
        section_type = section.section_type if section else ""
        title = f"{section.title if section else ''} {section.normalized_title if section else ''}".lower()
        if section_type in section_types:
            matches.append(span)
            continue
        if evidence_types and span.evidence_type in evidence_types:
            matches.append(span)
            continue
        if title_terms and any(term in title for term in title_terms):
            matches.append(span)
    return matches


def _has_full_text_support(state: ResearchRunState, paper_id: str, spans: list[EvidenceSpan]) -> bool:
    section_ids = {section.id for section in state.paper_sections if section.paper_id == paper_id}
    return bool(spans) and any(span.section_id in section_ids for span in spans)


def _evidence_from_span(span: EvidenceSpan) -> Evidence:
    return Evidence(
        source_id=span.id,
        source_paper_id=span.paper_id,
        quote=span.quote,
        locator=span.locator,
        confidence=span.confidence,
        notes=f"LLM-backed deep reading cited EvidenceSpan {span.id}.",
    )


def _sections_for_paper(state: ResearchRunState, paper_id: str) -> list[PaperSection]:
    return sorted(
        [section for section in state.paper_sections if section.paper_id == paper_id],
        key=lambda section: (section.page_start, section.char_start, section.id),
    )


def _spans_for_paper(state: ResearchRunState, paper_id: str) -> list[EvidenceSpan]:
    return [span for span in state.evidence_spans if span.paper_id == paper_id]


def _section_excerpt(section: PaperSection) -> dict[str, Any]:
    return {
        "id": section.id,
        "title": section.title,
        "section_type": section.section_type,
        "page_start": section.page_start,
        "page_end": section.page_end,
        "locator_hint": f"{section.paper_id}:{section.title or section.section_type}:p{section.page_start or '?'}",
        "text": section.text[:2500],
    }


def _span_payload(span: EvidenceSpan) -> dict[str, Any]:
    return {
        "id": span.id,
        "locator": span.locator,
        "evidence_type": span.evidence_type,
        "section_id": span.section_id,
        "page_start": span.page_start,
        "page_end": span.page_end,
        "quote": span.quote[:800],
    }


def _retrieval_context(state: ResearchRunState, paper_id: str) -> list[dict[str, Any]]:
    try:
        from gapforge.retrieval.hybrid import retrieval_candidates_for_state
    except ImportError:
        return []
    try:
        results, _paper_ids = retrieval_candidates_for_state(state, state.topic.text, top_k=10)
    except (FileNotFoundError, ValueError, OSError, RuntimeError):
        return []
    return [
        {
            "object_type": result.object_type,
            "object_id": result.object_id,
            "paper_id": result.paper_id,
            "locator": result.locator,
            "score": result.score,
            "snippet": result.text_snippet,
        }
        for result in results
        if result.paper_id == paper_id
    ]


def _merge_notes(existing: list[PaperNote], new_notes: list[PaperNote]) -> list[PaperNote]:
    by_id = {note.paper_id: note for note in existing}
    for note in new_notes:
        by_id[note.paper_id] = note
    return list(by_id.values())


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _summary_from_note(paper: Paper, raw: dict[str, Any]) -> str:
    claims = _list_strings(raw.get("core_claims"))
    if claims:
        return claims[0]
    return f"{paper.title}: LLM-backed note accepted only where evidence locators were valid."


def _missing_to_cannot_answer(missing_sections: list[str], payload: dict[str, Any]) -> list[str]:
    cannot = [f"{section} section is missing or was not provided to the LLM." for section in missing_sections]
    cannot.extend(_list_strings(payload.get("limitations")))
    return cannot


def _citation_key(paper: Paper) -> str:
    if paper.authors:
        first_author = paper.authors[0].split()[-1].lower().strip(",")
    else:
        first_author = "paper"
    return f"{first_author}{paper.year or ''}"


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value) or "paper"


def _write_report(state: ResearchRunState, report_lines: list[str], prompt_paths: list[Path]) -> None:
    lines = ["# LLM Deep Reading", ""]
    lines.extend(report_lines)
    lines.append("")
    lines.append("## Prompt Files")
    if prompt_paths:
        lines.extend(f"- `{path}`" for path in prompt_paths)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Evidence Discipline",
            "- Model output is accepted only after JSON schema validation.",
            "- Supported claims require valid EvidenceSpan locators from this run.",
            "- Main results, methods, and limitations are dropped or downgraded when locators point to the wrong section type.",
        ]
    )
    Path(state.run_dir, "deep_reading_llm.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
