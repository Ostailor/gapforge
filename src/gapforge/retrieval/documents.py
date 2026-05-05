"""Build retrieval documents from run and project-memory state."""

from __future__ import annotations

import hashlib

from gapforge.models import (
    Claim,
    EvidenceSpan,
    Gap,
    NoveltyDossier,
    Paper,
    PaperNote,
    PaperSection,
    ProjectMemoryRecord,
    Provenance,
    ResearchProgramState,
    ResearchRunState,
    RetrievalDocument,
)
from gapforge.state import utc_now_iso


def documents_from_state(state: ResearchRunState) -> list[RetrievalDocument]:
    """Flatten a run state into auditable retrieval documents."""

    documents: list[RetrievalDocument] = []
    paper_by_id = {paper.id: paper for paper in state.papers}
    for paper in state.papers:
        documents.append(_paper_document(state.run_id, paper))
    for section in state.paper_sections:
        documents.append(_section_document(state.run_id, section, paper_by_id.get(section.paper_id)))
    for span in state.evidence_spans:
        documents.append(_span_document(state.run_id, span, paper_by_id.get(span.paper_id)))
    for note in state.paper_notes:
        documents.append(_note_document(state.run_id, note, paper_by_id.get(note.paper_id)))
    for claim in state.claims:
        documents.append(_claim_document(state.run_id, claim))
    for gap in state.gaps:
        documents.append(_gap_document(state.run_id, gap))
    for dossier in state.novelty_dossiers:
        documents.append(_dossier_document(state.run_id, dossier))
    return documents


def documents_from_program(program: ResearchProgramState) -> list[RetrievalDocument]:
    """Flatten project memory into retrieval documents."""

    documents: list[RetrievalDocument] = []
    for record in program.memory_records:
        documents.append(_project_memory_document(program.project.id, record))
    for direction in program.research_directions:
        text = " ".join(
            [
                direction.title,
                direction.summary,
                " ".join(direction.blocking_issues),
                " ".join(direction.next_actions),
            ]
        )
        documents.append(
            RetrievalDocument(
                id=_doc_id("research_direction", direction.id, text),
                object_type="research_direction",
                object_id=direction.id,
                project_id=program.project.id,
                title=direction.title,
                text=text,
                metadata={
                    "maturity": direction.maturity,
                    "readiness_score": direction.readiness_score,
                    "supporting_paper_ids": direction.supporting_paper_ids,
                    "counterevidence_paper_ids": direction.counterevidence_paper_ids,
                },
                locator=f"project:{program.project.id}:direction:{direction.id}",
                provenance=_provenance([direction.id], "Research direction indexed from project memory."),
            )
        )
    return documents


def _paper_document(run_id: str, paper: Paper) -> RetrievalDocument:
    text = " ".join([paper.title, " ".join(paper.authors), paper.abstract, paper.venue, " ".join(paper.keywords)])
    return RetrievalDocument(
        id=_doc_id("paper", paper.id, text),
        object_type="paper",
        object_id=paper.id,
        run_id=run_id,
        paper_id=paper.id,
        title=paper.title,
        text=text,
        metadata={
            "year": paper.year,
            "source": paper.source,
            "doi": paper.doi,
            "arxiv_id": paper.arxiv_id,
            "citation_count": paper.citation_count,
            "roles": paper.roles,
            "has_pdf": bool(paper.pdf_url or paper.arxiv_id),
        },
        locator=paper.url or paper.id,
        provenance=_provenance([paper.id], "Paper metadata indexed for hybrid retrieval."),
    )


def _section_document(run_id: str, section: PaperSection, paper: Paper | None) -> RetrievalDocument:
    title = section.title or f"{section.section_type} section"
    return RetrievalDocument(
        id=_doc_id("paper_section", section.id, section.text),
        object_type="paper_section",
        object_id=section.id,
        run_id=run_id,
        paper_id=section.paper_id,
        title=f"{paper.title if paper else section.paper_id}: {title}",
        text=section.text,
        metadata={
            "section_type": section.section_type,
            "page_start": section.page_start,
            "page_end": section.page_end,
            "confidence": section.confidence,
        },
        locator=f"{section.paper_id}:{section.title or section.section_type}:p{section.page_start or '?'}",
        provenance=_provenance([section.paper_id, section.id], "Paper section indexed for full-text retrieval."),
    )


def _span_document(run_id: str, span: EvidenceSpan, paper: Paper | None) -> RetrievalDocument:
    return RetrievalDocument(
        id=_doc_id("evidence_span", span.id, span.quote),
        object_type="evidence_span",
        object_id=span.id,
        run_id=run_id,
        paper_id=span.paper_id,
        title=f"{paper.title if paper else span.paper_id}: {span.evidence_type}",
        text=span.quote,
        metadata={
            "evidence_type": span.evidence_type,
            "page_start": span.page_start,
            "page_end": span.page_end,
            "confidence": span.confidence,
            "section_id": span.section_id,
        },
        locator=span.locator,
        provenance=_provenance([span.paper_id, span.id], "Evidence span indexed for locator-backed retrieval."),
    )


def _note_document(run_id: str, note: PaperNote, paper: Paper | None) -> RetrievalDocument:
    text = " ".join(
        [
            note.one_sentence_summary,
            " ".join(note.core_claims),
            " ".join(note.method),
            " ".join(note.datasets),
            " ".join(note.metrics),
            " ".join(note.main_results),
            " ".join(note.stated_limitations),
            " ".join(note.unstated_limitations),
            " ".join(note.what_it_cannot_answer),
            " ".join(note.possible_connections),
        ]
    )
    return RetrievalDocument(
        id=_doc_id("paper_note", note.paper_id, text),
        object_type="paper_note",
        object_id=note.paper_id,
        run_id=run_id,
        paper_id=note.paper_id,
        title=f"Paper note: {paper.title if paper else note.paper_id}",
        text=text,
        metadata={
            "source_basis": note.source_basis,
            "confidence": note.confidence,
            "sections_used": note.sections_used,
            "missing_sections": note.missing_sections,
        },
        locator=f"paper_notes:{note.paper_id}",
        provenance=_provenance([note.paper_id], "Paper note indexed for retrieval."),
    )


def _claim_document(run_id: str, claim: Claim) -> RetrievalDocument:
    text = " ".join([claim.text, claim.notes, " ".join(claim.closest_prior_work)])
    return RetrievalDocument(
        id=_doc_id("claim", claim.id, text),
        object_type="claim",
        object_id=claim.id,
        run_id=run_id,
        paper_id=claim.source_paper_ids[0] if claim.source_paper_ids else "",
        title=f"Claim: {claim.type}",
        text=text,
        metadata={
            "claim_type": claim.type,
            "status": claim.status,
            "confidence": claim.confidence,
            "needs_verification": claim.needs_verification,
            "source_paper_ids": claim.source_paper_ids,
        },
        locator=f"claim:{claim.id}",
        provenance=_provenance([claim.id, *claim.source_paper_ids], "Claim ledger entry indexed for retrieval."),
    )


def _gap_document(run_id: str, gap: Gap) -> RetrievalDocument:
    text = " ".join(
        [
            gap.title,
            gap.description,
            gap.why_existing_work_does_not_solve_it,
            gap.why_it_matters,
            " ".join(gap.possible_research_questions),
            gap.minimum_experiment_needed,
            gap.risk_that_gap_is_fake,
            " ".join(gap.closest_prior_work),
        ]
    )
    return RetrievalDocument(
        id=_doc_id("gap", gap.id, text),
        object_type="gap",
        object_id=gap.id,
        run_id=run_id,
        paper_id=gap.supporting_paper_ids[0] if gap.supporting_paper_ids else "",
        title=gap.title or gap.id,
        text=text,
        metadata={
            "gap_type": gap.type,
            "confidence": gap.confidence,
            "novelty_status": gap.novelty_status,
            "supporting_paper_ids": gap.supporting_paper_ids,
            "linked_paper_ids": gap.linked_paper_ids,
        },
        locator=f"gap:{gap.id}",
        provenance=_provenance([gap.id, *gap.supporting_paper_ids], "Gap indexed for retrieval."),
    )


def _dossier_document(run_id: str, dossier: NoveltyDossier) -> RetrievalDocument:
    text = " ".join(
        [
            dossier.idea_summary,
            " ".join(dossier.query_plan),
            " ".join(dossier.top_prior_work),
            dossier.decisive_difference_needed,
            " ".join(dossier.missing_searches),
            dossier.reviewer_objection,
            dossier.recommended_action,
        ]
    )
    return RetrievalDocument(
        id=_doc_id("novelty_dossier", dossier.target_id, text),
        object_type="novelty_dossier",
        object_id=dossier.target_id,
        run_id=run_id,
        title=f"Novelty dossier: {dossier.target_id}",
        text=text,
        metadata={
            "verdict": dossier.verdict,
            "novelty_strength": dossier.novelty_strength,
            "confidence": dossier.confidence,
            "candidate_count": len(dossier.candidates_considered),
        },
        locator=f"novelty_dossier:{dossier.target_id}",
        provenance=_provenance([dossier.target_id], "Novelty dossier indexed for retrieval."),
    )


def _project_memory_document(project_id: str, record: ProjectMemoryRecord) -> RetrievalDocument:
    return RetrievalDocument(
        id=_doc_id("project_memory", record.id, record.text),
        object_type="project_memory",
        object_id=record.id,
        project_id=project_id,
        run_id=record.linked_run_ids[0] if record.linked_run_ids else "",
        paper_id=record.linked_paper_ids[0] if record.linked_paper_ids else "",
        title=f"Project memory: {record.record_type}",
        text=record.text,
        metadata={
            "record_type": record.record_type,
            "status": record.status,
            "confidence": record.confidence,
            "linked_run_ids": record.linked_run_ids,
            "linked_object_ids": record.linked_object_ids,
            "linked_paper_ids": record.linked_paper_ids,
        },
        locator=f"project:{project_id}:memory:{record.id}",
        provenance=_provenance([record.id, *record.linked_run_ids], "Project memory record indexed for retrieval."),
    )


def _doc_id(object_type: str, object_id: str, text: str) -> str:
    digest = hashlib.sha1(f"{object_type}:{object_id}:{text[:256]}".encode()).hexdigest()[:16]
    return f"doc-{digest}"


def _provenance(source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill="retrieval-index",
        source_ids=[source_id for source_id in source_ids if source_id],
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )
