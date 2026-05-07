"""First-class manuscript project state."""

from gapforge.manuscript.anonymization import ManuscriptAnonymizer
from gapforge.manuscript.figures import ManuscriptFigureGenerator
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import (
    AnonymizationReport,
    BibliographyRecord,
    CitationEntry,
    CitationUse,
    IdentityLeak,
    ManuscriptClaimUse,
    ManuscriptFigure,
    ManuscriptOverclaimWarning,
    ManuscriptProject,
    ManuscriptReviewPanel,
    ManuscriptSection,
    ManuscriptState,
    ManuscriptTable,
    ManuscriptTraceabilityReport,
    RebuttalItem,
    RevisionPlan,
    SubmissionChecklist,
    SubmissionPackage,
    VenueTemplate,
)
from gapforge.manuscript.sections import MANUSCRIPT_SECTION_STATUSES, MANUSCRIPT_SECTION_TYPES
from gapforge.manuscript.submission_checklist import SubmissionChecklistManager
from gapforge.manuscript.tables import ManuscriptTableGenerator
from gapforge.manuscript.venues import ManuscriptVenueManager

__all__ = [
    "MANUSCRIPT_SECTION_STATUSES",
    "MANUSCRIPT_SECTION_TYPES",
    "AnonymizationReport",
    "BibliographyRecord",
    "CitationEntry",
    "CitationUse",
    "IdentityLeak",
    "ManuscriptClaimUse",
    "ManuscriptAnonymizer",
    "ManuscriptFigure",
    "ManuscriptFigureGenerator",
    "ManuscriptManager",
    "ManuscriptOverclaimWarning",
    "ManuscriptProject",
    "ManuscriptReviewPanel",
    "ManuscriptSection",
    "ManuscriptState",
    "ManuscriptTable",
    "ManuscriptTableGenerator",
    "ManuscriptTraceabilityReport",
    "ManuscriptVenueManager",
    "RebuttalItem",
    "RevisionPlan",
    "SubmissionChecklist",
    "SubmissionChecklistManager",
    "SubmissionPackage",
    "VenueTemplate",
]
