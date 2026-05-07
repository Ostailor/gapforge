"""Typed manuscript project models."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.models import Provenance, RebuttalPlan, ReviewerReview

MANUSCRIPT_STATUSES = {"planned", "drafting", "review_ready", "submission_ready", "camera_ready", "archived"}
MANUSCRIPT_SECTION_TYPES = {
    "abstract",
    "introduction",
    "related_work",
    "method",
    "experiments",
    "results",
    "limitations",
    "ethics",
    "conclusion",
    "appendix",
}
MANUSCRIPT_SECTION_STATUSES = {"missing", "drafted", "needs_review", "approved"}
MANUSCRIPT_CLAIM_USE_TYPES = {"background", "novelty", "method", "result", "limitation", "future_work"}
VENUE_TYPES = {"conference", "journal", "workshop", "preprint", "internal"}
VENUE_FORMATS = {"markdown", "latex"}
SUBMISSION_CHECKLIST_STATUSES = {"not_ready", "review_ready", "submission_ready"}
SUBMISSION_PACKAGE_TYPES = {"review", "camera_ready", "arxiv", "internal"}
IDENTITY_LEAK_TYPES = {"author_name", "affiliation", "repository_url", "self_citation", "path", "metadata", "unknown"}
ANONYMIZATION_STATUSES = {"pass", "warning", "fail"}


@dataclass(slots=True)
class ManuscriptProject:
    id: str
    project_id: str
    campaign_id: str
    direction_id: str
    workspace_id: str
    title: str
    short_title: str = ""
    target_venue: str = ""
    status: str = "planned"
    created_at: str = ""
    updated_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-project"))


@dataclass(slots=True)
class ManuscriptSection:
    id: str
    manuscript_id: str
    section_type: str
    title: str
    content_path: str
    source_claim_ids: list[str] = field(default_factory=list)
    source_paper_ids: list[str] = field(default_factory=list)
    source_result_ids: list[str] = field(default_factory=list)
    source_artifact_ids: list[str] = field(default_factory=list)
    status: str = "missing"
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-section"))


@dataclass(slots=True)
class ManuscriptClaimUse:
    id: str
    manuscript_id: str
    section_id: str
    claim_id: str
    claim_text: str
    use_type: str = "background"
    support_status: str = "unsupported"
    evidence_locators: list[str] = field(default_factory=list)
    citation_keys: list[str] = field(default_factory=list)
    requires_softening: bool = False
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-claim-use"))


@dataclass(slots=True)
class CitationEntry:
    id: str
    paper_id: str
    citation_key: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int = 0
    venue: str = ""
    doi: str = ""
    arxiv_id: str = ""
    url: str = ""
    bibtex: str = ""
    metadata_completeness: dict[str, str] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-citation"))


@dataclass(slots=True)
class CitationUse:
    id: str
    manuscript_id: str
    section_id: str
    paper_id: str
    citation_key: str
    use_context: str = ""
    required: bool = True
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-citation-use"))


@dataclass(slots=True)
class BibliographyRecord:
    id: str
    manuscript_id: str
    entries: list[CitationEntry] = field(default_factory=list)
    missing_metadata: dict[str, list[str]] = field(default_factory=dict)
    duplicate_entries: dict[str, str] = field(default_factory=dict)
    generated_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-bibliography"))


@dataclass(slots=True)
class ManuscriptOverclaimWarning:
    id: str
    manuscript_id: str
    section_id: str
    text: str
    warning_type: str
    suggested_fix: str
    severity: str = "warning"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-traceability"))


@dataclass(slots=True)
class ManuscriptTraceabilityReport:
    manuscript_id: str
    claim_count: int = 0
    supported_claim_count: int = 0
    unsupported_claim_count: int = 0
    empirical_claim_count: int = 0
    novelty_claim_count: int = 0
    limitation_claim_count: int = 0
    unsupported_claims: list[str] = field(default_factory=list)
    overclaim_warnings: list[ManuscriptOverclaimWarning] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-traceability"))


@dataclass(slots=True)
class ManuscriptFigure:
    id: str
    manuscript_id: str
    title: str
    caption: str
    source_artifact_ids: list[str] = field(default_factory=list)
    path: str = ""
    figure_type: str = "custom"
    status: str = "generated"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-figure"))


@dataclass(slots=True)
class ManuscriptTable:
    id: str
    manuscript_id: str
    title: str
    caption: str
    source_result_ids: list[str] = field(default_factory=list)
    source_artifact_ids: list[str] = field(default_factory=list)
    path: str = ""
    table_type: str = "custom"
    status: str = "generated"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-table"))


@dataclass(slots=True)
class VenueTemplate:
    id: str
    name: str
    venue_type: str
    format: str
    sections_required: list[str] = field(default_factory=list)
    page_limit: int = 0
    anonymization_required: bool = False
    artifact_policy: str = ""
    ethics_required: bool = False
    reproducibility_required: bool = False
    citation_style: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="venue-template"))


@dataclass(slots=True)
class SubmissionChecklist:
    manuscript_id: str
    venue_template_id: str
    checks: dict[str, str] = field(default_factory=dict)
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "not_ready"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="submission-checklist"))


@dataclass(slots=True)
class SubmissionPackage:
    id: str
    manuscript_id: str
    venue_template_id: str
    package_type: str
    files: list[str] = field(default_factory=list)
    checklist_id: str = ""
    anonymization_report_id: str = ""
    artifact_package_id: str = ""
    status: str = "blocked"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="submission-package"))


@dataclass(slots=True)
class IdentityLeak:
    id: str
    path: str
    text_snippet: str
    leak_type: str
    severity: str
    suggested_fix: str
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-anonymization"))


@dataclass(slots=True)
class AnonymizationReport:
    manuscript_id: str
    anonymized_paths: list[str] = field(default_factory=list)
    detected_identity_leaks: list[IdentityLeak] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "pass"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-anonymization"))


@dataclass(slots=True)
class ManuscriptReviewPanel:
    manuscript_id: str
    reviewer_reports: list[ReviewerReview] = field(default_factory=list)
    area_chair_summary: str = ""
    meta_review: str = ""
    decision_risk: str = "unknown"
    required_fixes: list[str] = field(default_factory=list)
    fatal_flaws: list[str] = field(default_factory=list)
    rebuttal_plan: list[RebuttalPlan] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-review-panel"))


@dataclass(slots=True)
class RebuttalItem:
    id: str
    manuscript_id: str
    reviewer_id: str
    objection: str
    response_strategy: str
    evidence_needed: list[str] = field(default_factory=list)
    experiments_needed: list[str] = field(default_factory=list)
    citations_needed: list[str] = field(default_factory=list)
    claim_softening_needed: list[str] = field(default_factory=list)
    status: str = "open"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-rebuttal"))


@dataclass(slots=True)
class RevisionPlan:
    id: str
    manuscript_id: str
    rebuttal_items: list[RebuttalItem] = field(default_factory=list)
    section_edits: list[str] = field(default_factory=list)
    required_experiments: list[str] = field(default_factory=list)
    required_searches: list[str] = field(default_factory=list)
    required_citations: list[str] = field(default_factory=list)
    status: str = "open"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-revisions"))


@dataclass(slots=True)
class ManuscriptState:
    manuscript: ManuscriptProject
    sections: list[ManuscriptSection] = field(default_factory=list)
    claim_uses: list[ManuscriptClaimUse] = field(default_factory=list)
    bibliography_id: str = ""
    citation_uses: list[CitationUse] = field(default_factory=list)
    figure_ids: list[str] = field(default_factory=list)
    table_ids: list[str] = field(default_factory=list)
    review_ids: list[str] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
