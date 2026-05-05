"""Produce structured abstract-grounded paper notes."""

from __future__ import annotations

import re

from gapforge.claim_ledger import ClaimLedger
from gapforge.fulltext.sectionizer import create_evidence_span_from_quote
from gapforge.models import Evidence, EvidenceSpan, Paper, PaperNote, PaperSection, Provenance, ResearchRunState
from gapforge.retrieval.hybrid import retrieval_candidates_for_state
from gapforge.skills.base import Skill
from gapforge.state import utc_now_iso

METHOD_TERMS = {
    "graph neural network",
    "graph neural",
    "gnn",
    "embedding",
    "representation learning",
    "classification",
    "anomaly detection",
    "calibration",
    "abstention",
    "benchmark",
    "framework",
    "algorithm",
}

DATASET_TERMS = {
    "dataset",
    "benchmark",
    "corpus",
    "synthetic",
    "real-world",
    "transaction",
    "network",
    "graph",
    "labels",
    "ground truth",
}

METRIC_TERMS = {
    "accuracy",
    "precision",
    "recall",
    "auc",
    "f1",
    "false positive",
    "false-positive",
    "calibration error",
    "specificity",
}

LIMITATION_MARKERS = {
    "limitation",
    "limitations",
    "future work",
    "challenge",
    "open problem",
    "fails",
    "failure",
    "cannot",
}

RESULT_MARKERS = {
    "we show",
    "we demonstrate",
    "results show",
    "we find",
    "outperform",
    "improves",
    "achieves",
    "reduces",
    "increases",
}

CLAIM_MARKERS = {"we propose", "we present", "we introduce", "this paper", "we study", "we investigate"}


class DeepReading(Skill):
    name = "deep-reading"

    def run(self, state: ResearchRunState) -> ResearchRunState:
        return self.read_papers(state, self._selected_papers(state))

    def read_papers(
        self,
        state: ResearchRunState,
        papers: list[Paper],
        *,
        fulltext_only: bool = False,
        allow_abstract_only: bool = True,
    ) -> ResearchRunState:
        notes: list[PaperNote] = []
        spans: list[EvidenceSpan] = []
        sections_by_paper = _sections_by_paper(state.paper_sections)
        for paper in papers:
            sections = sections_by_paper.get(paper.id, [])
            if sections:
                sections = _retrieval_ordered_sections(state, paper.id, sections)
                note, note_spans = self.read_paper_sections(state.topic.text, paper, sections)
                notes.append(note)
                spans.extend(note_spans)
            elif allow_abstract_only and not fulltext_only:
                notes.append(self.read_paper(state.topic.text, paper))
        state.paper_notes = _merge_notes(state.paper_notes, notes)
        state.evidence_spans = _merge_spans(state.evidence_spans, spans)
        state.claims = self._add_note_claims(state, notes).claims
        self.mark_complete(state)
        return state

    def read_paper(self, topic: str, paper: Paper, *, full_text: str | None = None) -> PaperNote:
        source_text = full_text or paper.abstract or ""
        abstract_only = full_text is None
        evidence = _evidence_snippets(paper, source_text)
        sentences = _sentences(source_text)
        core_claims = _sentences_with_markers(sentences, CLAIM_MARKERS) or ([paper.title] if paper.title else [])
        main_results = _sentences_with_markers(sentences, RESULT_MARKERS)
        stated_limitations = _sentences_with_markers(sentences, LIMITATION_MARKERS)
        method = _terms_present(source_text, METHOD_TERMS)
        datasets = _terms_present(source_text, DATASET_TERMS)
        metrics = _terms_present(source_text, METRIC_TERMS)
        assumptions = _assumptions(paper, source_text, abstract_only)
        unstated_limitations = _unstated_limitations(paper, source_text, abstract_only, main_results)
        cannot_answer = _cannot_answer(topic, paper, abstract_only, metrics, datasets)

        return PaperNote(
            paper_id=paper.id,
            citation_key=_citation_key(paper),
            one_sentence_summary=_one_sentence_summary(paper, abstract_only),
            core_claims=core_claims,
            method=method,
            datasets=datasets,
            metrics=metrics,
            main_results=main_results,
            assumptions=assumptions,
            stated_limitations=stated_limitations,
            unstated_limitations=unstated_limitations,
            what_it_cannot_answer=cannot_answer,
            useful_technical_tools=_technical_tools(method, datasets, metrics),
            possible_connections=_possible_connections(topic, paper, method, metrics),
            relevance_to_topic=_relevance_to_topic(topic, paper),
            confidence="medium" if paper.abstract and not full_text else ("high" if full_text else "low"),
            quotes_or_evidence_snippets=evidence,
            created_by_skill=self.name,
            source_basis="full text" if full_text else "metadata/abstract only",
            summary=_one_sentence_summary(paper, abstract_only),
            methods=method,
            limitations=stated_limitations + unstated_limitations,
            evidence=evidence,
            sections_used=[],
            missing_sections=["full text", "method", "experiments/evaluation/results", "limitations/discussion/conclusion"]
            if abstract_only
            else [],
            provenance=Provenance(
                created_by_skill=self.name,
                source_ids=[paper.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Structured paper note extracted deterministically from full text or metadata/abstract text.",
            ),
        )

    def read_paper_sections(self, topic: str, paper: Paper, sections: list[PaperSection]) -> tuple[PaperNote, list[EvidenceSpan]]:
        sections_by_type = _sections_by_type(sections)
        sections_used = [f"{section.section_type}:{section.title or section.id}" for section in sections]
        missing_sections = _missing_section_groups(sections_by_type)
        evidence_spans: list[EvidenceSpan] = []

        claim_sections = _typed_sections(sections_by_type, {"abstract", "introduction"})
        method_sections = _typed_sections(sections_by_type, {"method"})
        experiment_sections = _typed_sections(sections_by_type, {"experiments", "results"})
        result_sections = _typed_sections(sections_by_type, {"results", "experiments", "conclusion"})
        limitation_sections = _typed_sections(sections_by_type, {"limitations", "discussion", "conclusion"})

        core_claims = _section_sentences_with_markers(claim_sections, CLAIM_MARKERS)
        if not core_claims and claim_sections:
            core_claims = _first_sentences(claim_sections, limit=1)
        for statement in core_claims[:3]:
            span = _span_for_statement(claim_sections, statement, evidence_type="claim")
            if span is not None:
                evidence_spans.append(span)

        main_results = _section_sentences_with_markers(result_sections, RESULT_MARKERS)
        result_spans: list[EvidenceSpan] = []
        for statement in main_results[:4]:
            span = _span_for_statement(result_sections, statement, evidence_type="result")
            if span is not None:
                result_spans.append(span)
        main_results = [span.quote for span in result_spans]
        evidence_spans.extend(result_spans)

        stated_limitations = _section_sentences_with_markers(limitation_sections, LIMITATION_MARKERS)
        if not stated_limitations and sections_by_type.get("limitations"):
            stated_limitations = _first_sentences(sections_by_type["limitations"], limit=2)
        for statement in stated_limitations[:3]:
            span = _span_for_statement(limitation_sections, statement, evidence_type="limitation")
            if span is not None:
                evidence_spans.append(span)

        full_text = "\n".join(section.text for section in sections)
        method_text = "\n".join(section.text for section in method_sections)
        experiment_text = "\n".join(section.text for section in experiment_sections)
        method = _terms_present(method_text, METHOD_TERMS)
        datasets = _terms_present(experiment_text, DATASET_TERMS)
        metrics = _terms_present(experiment_text, METRIC_TERMS)
        assumptions = _assumptions(paper, full_text, abstract_only=False)
        unstated_limitations = _unstated_limitations(paper, full_text, abstract_only=False, main_results=main_results)
        cannot_answer = _cannot_answer(topic, paper, False, metrics, datasets)
        for missing in missing_sections:
            cannot_answer.append(f"{missing} section is missing from parsed full text.")
        evidence = [_evidence_from_span(span) for span in evidence_spans]
        confidence = _full_text_confidence(sections_by_type, evidence_spans)

        return (
            PaperNote(
                paper_id=paper.id,
                citation_key=_citation_key(paper),
                one_sentence_summary=_one_sentence_summary(paper, abstract_only=False),
                core_claims=core_claims,
                method=method,
                datasets=datasets,
                metrics=metrics,
                main_results=main_results,
                assumptions=assumptions,
                stated_limitations=stated_limitations,
                unstated_limitations=unstated_limitations,
                what_it_cannot_answer=cannot_answer,
                useful_technical_tools=_technical_tools(method, datasets, metrics),
                possible_connections=_possible_connections(topic, paper, method, metrics),
                relevance_to_topic=_relevance_to_topic(topic, paper),
                confidence=confidence,
                quotes_or_evidence_snippets=evidence,
                created_by_skill=self.name,
                source_basis="full text",
                summary=_one_sentence_summary(paper, abstract_only=False),
                methods=method,
                limitations=stated_limitations + unstated_limitations,
                evidence=evidence,
                sections_used=sections_used,
                missing_sections=missing_sections,
                provenance=Provenance(
                    created_by_skill=self.name,
                    source_ids=[paper.id] + [section.id for section in sections],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Structured paper note extracted deterministically from parsed full-text sections.",
                ),
            ),
            evidence_spans,
        )

    def _selected_papers(self, state: ResearchRunState) -> list[Paper]:
        by_id = {paper.id: paper for paper in state.papers}
        if state.paper_triage is None:
            return state.papers[:5]
        selected_ids = [decision.paper_id for decision in state.paper_triage.decisions if decision.tier in {"Tier 1", "Tier 2"}]
        return [by_id[paper_id] for paper_id in selected_ids if paper_id in by_id]

    def _add_note_claims(self, state: ResearchRunState, notes: list[PaperNote]) -> ClaimLedger:
        ledger = ClaimLedger(state.claims)
        for note in notes:
            for statement in note.core_claims[:2]:
                statement_evidence = _evidence_for_statement(note, statement)
                confidence = note.confidence if statement_evidence else "low"
                claim = ledger.add_claim(
                    text=f"{note.citation_key or note.paper_id}: {statement}",
                    claim_type="method",
                    created_by_skill=self.name,
                    confidence=confidence,
                    source_paper_ids=[note.paper_id],
                    needs_verification=not bool(statement_evidence),
                    notes=f"Extracted from {note.source_basis}.",
                    reasoning_summary="Converted a source-grounded paper claim into the claim ledger.",
                )
                for snippet in statement_evidence[:2]:
                    ledger.add_evidence(claim.id, snippet)
                if statement_evidence:
                    ledger.mark_supported(claim.id, confidence=confidence)
                else:
                    ledger.mark_uncertain(claim.id, confidence="low")

            for limitation in (note.stated_limitations + note.unstated_limitations)[:2]:
                limitation_evidence = _evidence_for_statement(note, limitation)
                claim = ledger.add_claim(
                    text=f"{note.citation_key or note.paper_id} limitation: {limitation}",
                    claim_type="limitation",
                    created_by_skill=self.name,
                    confidence=("medium" if limitation in note.stated_limitations and limitation_evidence else "low"),
                    source_paper_ids=[note.paper_id],
                    needs_verification=limitation not in note.stated_limitations or not limitation_evidence,
                    notes="Unstated limitations are heuristic and should be verified before use."
                    if limitation in note.unstated_limitations
                    else "",
                    reasoning_summary="Converted stated or clearly scoped limitation into the claim ledger.",
                )
                for snippet in limitation_evidence[:1]:
                    ledger.add_evidence(claim.id, snippet)
                if limitation in note.stated_limitations and limitation_evidence:
                    ledger.mark_supported(claim.id, confidence="medium")
                else:
                    ledger.mark_uncertain(claim.id, confidence="low")
        return ledger


def _merge_notes(existing: list[PaperNote], new_notes: list[PaperNote]) -> list[PaperNote]:
    by_id = {note.paper_id: note for note in existing}
    for note in new_notes:
        by_id[note.paper_id] = note
    return list(by_id.values())


def _merge_spans(existing: list[EvidenceSpan], new_spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    by_id = {span.id: span for span in existing}
    for span in new_spans:
        by_id[span.id] = span
    return list(by_id.values())


def _sections_by_paper(sections: list[PaperSection]) -> dict[str, list[PaperSection]]:
    by_paper: dict[str, list[PaperSection]] = {}
    for section in sections:
        by_paper.setdefault(section.paper_id, []).append(section)
    for paper_sections in by_paper.values():
        paper_sections.sort(key=lambda section: (section.page_start, section.char_start, section.id))
    return by_paper


def _retrieval_ordered_sections(state: ResearchRunState, paper_id: str, sections: list[PaperSection]) -> list[PaperSection]:
    try:
        results, _paper_ids = retrieval_candidates_for_state(state, state.topic.text, top_k=40)
    except (FileNotFoundError, ValueError, OSError, RuntimeError):
        return sections
    section_by_id = {section.id: section for section in sections}
    ranked_ids = [
        result.object_id
        for result in results
        if result.object_type == "paper_section" and result.paper_id == paper_id and result.object_id in section_by_id
    ]
    if not ranked_ids:
        return sections
    used = set(ranked_ids)
    return [section_by_id[section_id] for section_id in ranked_ids] + [section for section in sections if section.id not in used]


def _sections_by_type(sections: list[PaperSection]) -> dict[str, list[PaperSection]]:
    by_type: dict[str, list[PaperSection]] = {}
    for section in sections:
        by_type.setdefault(section.section_type, []).append(section)
    return by_type


def _typed_sections(sections_by_type: dict[str, list[PaperSection]], section_types: set[str]) -> list[PaperSection]:
    sections: list[PaperSection] = []
    for section_type in section_types:
        sections.extend(sections_by_type.get(section_type, []))
    return sorted(sections, key=lambda section: (section.page_start, section.char_start, section.id))


def _missing_section_groups(sections_by_type: dict[str, list[PaperSection]]) -> list[str]:
    groups = [
        ("abstract/introduction", {"abstract", "introduction"}),
        ("method/approach", {"method"}),
        ("experiments/evaluation/results", {"experiments", "results"}),
        ("limitations/discussion/conclusion", {"limitations", "discussion", "conclusion"}),
    ]
    return [label for label, section_types in groups if not any(sections_by_type.get(section_type) for section_type in section_types)]


def _section_sentences_with_markers(sections: list[PaperSection], markers: set[str]) -> list[str]:
    matches: list[str] = []
    for section in sections:
        matches.extend(_sentences_with_markers(_sentences(section.text), markers))
    return _dedupe(matches)


def _first_sentences(sections: list[PaperSection], *, limit: int) -> list[str]:
    sentences: list[str] = []
    for section in sections:
        sentences.extend(_sentences(section.text)[:limit])
        if len(sentences) >= limit:
            break
    return _dedupe(sentences[:limit])


def _span_for_statement(sections: list[PaperSection], statement: str, *, evidence_type: str) -> EvidenceSpan | None:
    for section in sections:
        if statement in section.text:
            return create_evidence_span_from_quote(section, statement, evidence_type=evidence_type)
    return None


def _evidence_from_span(span: EvidenceSpan) -> Evidence:
    return Evidence(
        source_id=span.id,
        source_paper_id=span.paper_id,
        quote=span.quote,
        locator=span.locator,
        confidence=span.confidence,
        notes=f"EvidenceSpan {span.id} from parsed full text.",
    )


def _evidence_for_statement(note: PaperNote, statement: str) -> list[Evidence]:
    lower_statement = statement.lower()
    exact = [item for item in note.quotes_or_evidence_snippets if item.quote == statement]
    if exact:
        return exact
    partial = [
        item for item in note.quotes_or_evidence_snippets if lower_statement in item.quote.lower() or item.quote.lower() in lower_statement
    ]
    if partial:
        return partial
    if note.source_basis == "metadata/abstract only":
        return note.quotes_or_evidence_snippets[:1]
    return []


def _full_text_confidence(sections_by_type: dict[str, list[PaperSection]], evidence_spans: list[EvidenceSpan]) -> str:
    if not evidence_spans:
        return "low"
    coverage_groups = [
        {"abstract", "introduction"},
        {"method"},
        {"experiments", "results"},
        {"limitations", "discussion", "conclusion"},
    ]
    covered = sum(1 for group in coverage_groups if any(sections_by_type.get(section_type) for section_type in group))
    return "high" if covered >= 3 and len(evidence_spans) >= 3 else "medium"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text.strip()) if sentence.strip()]


def _sentences_with_markers(sentences: list[str], markers: set[str]) -> list[str]:
    matches = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(marker in lower for marker in markers):
            matches.append(sentence)
    return matches


def _terms_present(text: str, terms: set[str]) -> list[str]:
    lower = text.lower()
    return sorted(term for term in terms if term in lower)


def _evidence_snippets(paper: Paper, source_text: str) -> list[Evidence]:
    quote = source_text.strip() or paper.title
    if not quote:
        return []
    return [
        Evidence(
            source_id=paper.id,
            source_paper_id=paper.id,
            quote=quote[:700],
            locator=paper.url or paper.id,
            confidence="medium" if paper.abstract else "low",
            notes="Abstract/full-text snippet used by deterministic deep reading.",
        )
    ]


def _assumptions(paper: Paper, source_text: str, abstract_only: bool) -> list[str]:
    assumptions = []
    lower = source_text.lower()
    if "dataset" in lower or "benchmark" in lower:
        assumptions.append("Available datasets or benchmarks are representative of the target problem.")
    if "graph" in lower or "network" in lower:
        assumptions.append("The relevant behavior can be represented as graph or network structure.")
    if abstract_only:
        assumptions.append("Only metadata/abstract text is available; unstated methods and results may be missing.")
    return assumptions


def _unstated_limitations(paper: Paper, source_text: str, abstract_only: bool, main_results: list[str]) -> list[str]:
    limitations = []
    lower = source_text.lower()
    if abstract_only:
        limitations.append("Full-text evidence is unavailable, so method details and caveats may be incomplete.")
    if "false positive" not in lower and "false-positive" not in lower:
        limitations.append("False-positive behavior is not visible in the available text.")
    if not main_results:
        limitations.append("No concrete result statement is visible in the available text.")
    return limitations


def _cannot_answer(topic: str, paper: Paper, abstract_only: bool, metrics: list[str], datasets: list[str]) -> list[str]:
    answers = []
    if abstract_only:
        answers.append("Cannot verify detailed experimental setup without full text.")
    if not metrics:
        answers.append("Cannot assess metric validity from available text.")
    if not datasets:
        answers.append("Cannot assess dataset realism from available text.")
    if _topic_overlap(topic, paper) < 0.4:
        answers.append("Cannot establish direct relevance to the user topic without deeper context.")
    return answers


def _technical_tools(method: list[str], datasets: list[str], metrics: list[str]) -> list[str]:
    return method + datasets + metrics


def _possible_connections(topic: str, paper: Paper, method: list[str], metrics: list[str]) -> list[str]:
    connections = []
    if _topic_overlap(topic, paper) >= 0.4:
        connections.append("Shares terminology with the user topic.")
    if any("calibration" in item or "false" in item for item in method + metrics):
        connections.append("May inform low false-positive evaluation or calibration.")
    if any("graph" in item or "network" in item for item in method + paper.keywords):
        connections.append("May transfer to graph-structured collusion settings.")
    return connections or ["Connection is weak from metadata/abstract alone."]


def _relevance_to_topic(topic: str, paper: Paper) -> str:
    overlap = _topic_overlap(topic, paper)
    if overlap >= 0.7:
        return "high"
    if overlap >= 0.4:
        return "medium"
    return "low"


def _topic_overlap(topic: str, paper: Paper) -> float:
    topic_tokens = set(_tokens(topic))
    if not topic_tokens:
        return 0.0
    paper_tokens = set(_tokens(" ".join([paper.title, paper.abstract, " ".join(paper.keywords)])))
    return len(topic_tokens & paper_tokens) / len(topic_tokens)


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z][a-z0-9]{2,}", text.lower()) if token not in {"the", "and", "for", "with"}]


def _one_sentence_summary(paper: Paper, abstract_only: bool) -> str:
    basis = "metadata/abstract-only" if abstract_only else "full-text"
    return f"{paper.title} ({basis}) is represented as a structured note without adding unsupported details."


def _citation_key(paper: Paper) -> str:
    author = paper.authors[0].split()[-1].lower() if paper.authors else "unknown"
    return f"{author}{paper.year or 'nd'}"
