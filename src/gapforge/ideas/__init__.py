"""First-class v2 idea discovery state."""

from gapforge.ideas.agenda import ResearchAgendaManager, render_research_agenda_markdown
from gapforge.ideas.codex_tasks import IDEA_CODEX_TASK_TYPES, IdeaCodexTask, IdeaCodexTaskManager
from gapforge.ideas.constructive_gap import (
    ConstructiveGapGenerator,
    ConstructiveGapResult,
    render_constructive_gap_report,
    validate_constructive_gap_candidate,
)
from gapforge.ideas.controller import IdeaSearchController, IdeaSearchRunResult
from gapforge.ideas.cross_domain_transfer import (
    CrossDomainIdeaTransferEngine,
    IdeaTransferResult,
    render_transfer_report,
    validate_transfer_pattern,
)
from gapforge.ideas.decision_policy import IdeaSearchAction, IdeaSearchAssessment, IdeaSearchDecisionPolicy
from gapforge.ideas.feedback import IdeaFeedbackManager
from gapforge.ideas.generator import IdeaGenerationResult, IdeaSeedGenerator, is_generic_idea_title
from gapforge.ideas.metrics import IdeaYieldMetricCalculator, IdeaYieldMetrics, render_idea_yield_report
from gapforge.ideas.models import (
    AGENDA_STEP_TYPES,
    CONTRIBUTION_TYPES,
    IDEA_FEEDBACK_ACTIONS,
    IDEA_LINK_TYPES,
    IDEA_MATURITIES,
    IDEA_MUTATION_STRATEGIES,
    IDEA_NOVELTY_STATUSES,
    IDEA_NOVELTY_VERDICTS,
    IDEA_REVIEW_STATUSES,
    IDEA_SEARCH_DECISION_TYPES,
    AgendaStep,
    ConstructiveGapCandidate,
    IdeaBank,
    IdeaCandidate,
    IdeaEvidenceLink,
    IdeaFeedbackRecord,
    IdeaMutationRecord,
    IdeaNoveltyAssessment,
    IdeaPreferenceProfile,
    IdeaReviewRecord,
    IdeaScoreRecord,
    IdeaSearchDecision,
    IdeaTournament,
    IdeaTransferCandidate,
    ResearchAgenda,
)
from gapforge.ideas.mutation import IdeaMutationEngine, IdeaMutationResult, available_mutation_strategies, render_mutation_report
from gapforge.ideas.novelty_loop import (
    IdeaNoveltyLoop,
    IdeaNoveltyRunResult,
    generate_idea_prior_work_queries,
)
from gapforge.ideas.preferences import IdeaPreferenceManager
from gapforge.ideas.reports import render_idea_bank_markdown, render_idea_discovery_report, render_idea_report_markdown
from gapforge.ideas.selected_project import (
    SelectedIdeaLock,
    SelectedIdeaProject,
    SelectedIdeaProjectManager,
    render_selected_idea_status,
    validate_selected_idea_project_status,
)
from gapforge.ideas.store import IdeaStore
from gapforge.ideas.topic_portfolio import TopicPortfolio, TopicPortfolioGenerator, TopicVariant, render_topic_portfolio_markdown
from gapforge.ideas.tournament import IdeaTournamentRunner

__all__ = [
    "CONTRIBUTION_TYPES",
    "AGENDA_STEP_TYPES",
    "AgendaStep",
    "ConstructiveGapCandidate",
    "ConstructiveGapGenerator",
    "ConstructiveGapResult",
    "CrossDomainIdeaTransferEngine",
    "IDEA_CODEX_TASK_TYPES",
    "IDEA_FEEDBACK_ACTIONS",
    "IDEA_LINK_TYPES",
    "IDEA_MATURITIES",
    "IDEA_MUTATION_STRATEGIES",
    "IDEA_NOVELTY_STATUSES",
    "IDEA_NOVELTY_VERDICTS",
    "IDEA_REVIEW_STATUSES",
    "IDEA_SEARCH_DECISION_TYPES",
    "IdeaBank",
    "IdeaCodexTask",
    "IdeaCodexTaskManager",
    "IdeaCandidate",
    "IdeaEvidenceLink",
    "IdeaFeedbackManager",
    "IdeaFeedbackRecord",
    "IdeaMutationEngine",
    "IdeaMutationRecord",
    "IdeaMutationResult",
    "IdeaNoveltyAssessment",
    "IdeaNoveltyLoop",
    "IdeaNoveltyRunResult",
    "IdeaPreferenceManager",
    "IdeaPreferenceProfile",
    "IdeaReviewRecord",
    "IdeaScoreRecord",
    "IdeaSearchAction",
    "IdeaSearchAssessment",
    "IdeaSearchController",
    "IdeaSearchDecision",
    "IdeaSearchDecisionPolicy",
    "IdeaSearchRunResult",
    "IdeaTournament",
    "IdeaTournamentRunner",
    "IdeaTransferCandidate",
    "IdeaTransferResult",
    "IdeaGenerationResult",
    "IdeaSeedGenerator",
    "IdeaStore",
    "IdeaYieldMetricCalculator",
    "IdeaYieldMetrics",
    "ResearchAgenda",
    "ResearchAgendaManager",
    "SelectedIdeaLock",
    "SelectedIdeaProject",
    "SelectedIdeaProjectManager",
    "TopicPortfolio",
    "TopicPortfolioGenerator",
    "TopicVariant",
    "available_mutation_strategies",
    "generate_idea_prior_work_queries",
    "is_generic_idea_title",
    "render_idea_bank_markdown",
    "render_idea_discovery_report",
    "render_idea_report_markdown",
    "render_idea_yield_report",
    "render_research_agenda_markdown",
    "render_selected_idea_status",
    "render_constructive_gap_report",
    "render_mutation_report",
    "render_topic_portfolio_markdown",
    "render_transfer_report",
    "validate_constructive_gap_candidate",
    "validate_transfer_pattern",
    "validate_selected_idea_project_status",
]
