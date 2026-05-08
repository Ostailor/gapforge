"""Generate v2 idea seed banks from topic portfolios and project memory."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.config import GapForgeConfig
from gapforge.ideas.models import IdeaBank, IdeaCandidate
from gapforge.ideas.store import IdeaStore
from gapforge.ideas.topic_portfolio import TopicPortfolio, TopicPortfolioGenerator, TopicVariant
from gapforge.models import (
    HumanReviewRecord,
    NoveltyDossier,
    ProjectMemoryRecord,
    Provenance,
    RelatedWorkMatrix,
    ResearchCampaign,
    ResearchDirection,
    ResearchRunState,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso

GENERATION_SOURCES = {
    "topic_variant",
    "repeated_literature_gap",
    "unresolved_novelty_dossier",
    "rejected_idea_mutation",
    "cross_domain_transfer",
    "missing_benchmark",
    "missing_evaluation_protocol",
    "negative_result_opportunity",
    "measurement_study_opportunity",
    "theory_guarantee_opportunity",
}
GENERIC_TITLES = {
    "",
    "idea",
    "research idea",
    "new idea",
    "novel idea",
    "paper idea",
    "interesting direction",
    "future work",
    "llm idea",
    "ai idea",
    "topic",
}


@dataclass(slots=True)
class IdeaGenerationResult:
    bank: IdeaBank
    candidates: list[IdeaCandidate] = field(default_factory=list)
    skipped_titles: list[str] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)


class IdeaSeedGenerator:
    """Build a diverse pool of seed ideas from v2 portfolio and project evidence."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.idea_store = IdeaStore(config)
        self.portfolio_generator = TopicPortfolioGenerator(config)

    def generate(
        self,
        *,
        project_id: str = "",
        portfolio_id: str = "",
        max_candidates: int = 50,
    ) -> IdeaGenerationResult:
        portfolio = self._resolve_portfolio(project_id=project_id, portfolio_id=portfolio_id)
        project_id = portfolio.project_id
        program = self.project_manager.load_project(project_id)
        run_states = self._load_run_states(program.run_ids)
        bank = self.idea_store.create_bank(project_id=project_id, root_topic=portfolio.root_topic)
        existing_titles = {candidate.title.strip().lower() for candidate in self.idea_store.list_candidates(project_id)}
        specs = _candidate_specs(
            portfolio=portfolio,
            memory_records=program.memory_records,
            research_directions=program.research_directions,
            campaigns=program.campaigns,
            related_work_matrices=program.related_work_matrices,
            novelty_dossiers=[dossier for state in run_states for dossier in state.novelty_dossiers],
            human_reviews=[review for state in run_states for review in state.human_reviews],
            rejected_candidates=[
                candidate for candidate in self.idea_store.list_candidates(project_id) if candidate.maturity == "rejected"
            ],
        )
        candidates: list[IdeaCandidate] = []
        skipped: list[str] = []
        source_counts: dict[str, int] = {}
        for spec in specs:
            if len(candidates) >= max_candidates:
                break
            title = spec["title"]
            if is_generic_idea_title(title) or title.strip().lower() in existing_titles:
                skipped.append(title)
                continue
            source = spec["source"]
            candidate = self.idea_store.add_candidate(
                project_id=project_id,
                source_topic_id=spec.get("source_topic_id", portfolio.id),
                title=title,
                summary=spec["summary"],
                contribution_type=spec["contribution_type"],
                core_claim=spec.get("core_claim", ""),
                proposed_experiment=spec.get("proposed_experiment", ""),
                expected_baselines=spec.get("expected_baselines", []),
                expected_metrics=spec.get("expected_metrics", []),
                closest_prior_work_ids=spec.get("closest_prior_work_ids", []),
                evidence_span_ids=spec.get("evidence_span_ids", []),
                supporting_paper_ids=spec.get("supporting_paper_ids", []),
                counterevidence_paper_ids=spec.get("counterevidence_paper_ids", []),
                novelty_status=spec.get("novelty_status", "unchecked"),
                tractability_score=spec.get("tractability_score", 0.35),
                impact_score=spec.get("impact_score", 0.35),
                evidence_score=spec.get("evidence_score", 0.1),
                reviewer_risk_score=spec.get("reviewer_risk_score", 0.7),
                idea_yield_score=spec.get("idea_yield_score", 0.25),
                maturity="seed",
                likely_failure_mode=spec["likely_failure_mode"],
                provenance=Provenance(
                    created_by_skill=f"idea-generator:{source}",
                    source_ids=spec.get("source_ids", [portfolio.id]),
                    timestamp=utc_now_iso(),
                    reasoning_summary=(
                        "Generated a seed idea from recorded portfolio or project memory. "
                        "Seed status does not imply novelty, feasibility, or paper readiness."
                    ),
                ),
            )
            candidates.append(candidate)
            existing_titles.add(candidate.title.strip().lower())
            source_counts[source] = source_counts.get(source, 0) + 1
        bank = self.idea_store.load_state(project_id).idea_bank or bank
        self.idea_store.write_bank_report(project_id)
        return IdeaGenerationResult(bank=bank, candidates=candidates, skipped_titles=skipped, source_counts=source_counts)

    def _resolve_portfolio(self, *, project_id: str, portfolio_id: str) -> TopicPortfolio:
        if portfolio_id:
            return self.portfolio_generator.load(portfolio_id)
        if not project_id:
            raise ValueError("idea-generate requires --project-id or --portfolio-id.")
        portfolios = self.portfolio_generator.list_project_portfolios(project_id)
        if portfolios:
            return portfolios[-1]
        return self.portfolio_generator.generate(project_id=project_id)

    def _load_run_states(self, run_ids: list[str]) -> list[ResearchRunState]:
        states: list[ResearchRunState] = []
        for run_id in run_ids:
            try:
                states.append(self.state_manager.load_run(run_id))
            except FileNotFoundError:
                continue
        return states


def is_generic_idea_title(title: str) -> bool:
    normalized = " ".join(title.strip().lower().split())
    if normalized in GENERIC_TITLES:
        return True
    if len(normalized) < 12:
        return True
    return normalized in {"generic monitor", "generic benchmark", "generic evaluation"}


def _candidate_specs(
    *,
    portfolio: TopicPortfolio,
    memory_records: list[ProjectMemoryRecord],
    research_directions: list[ResearchDirection],
    campaigns: list[ResearchCampaign],
    related_work_matrices: list[RelatedWorkMatrix],
    novelty_dossiers: list[NoveltyDossier],
    human_reviews: list[HumanReviewRecord],
    rejected_candidates: list[IdeaCandidate],
) -> list[dict]:
    specs: list[dict] = []
    specs.extend(_from_topic_variants(portfolio))
    specs.extend(_from_repeated_gaps(portfolio, memory_records))
    specs.extend(_from_unresolved_dossiers(portfolio, novelty_dossiers))
    specs.extend(_from_rejections(portfolio, memory_records, rejected_candidates))
    specs.extend(_from_research_agenda(portfolio, research_directions))
    specs.extend(_from_human_preferences(portfolio, human_reviews))
    specs.extend(_from_cross_domain_transfers(portfolio))
    specs.extend(_from_missing_benchmarks(portfolio, related_work_matrices))
    specs.extend(_from_missing_evaluation_protocols(portfolio, related_work_matrices, campaigns))
    specs.extend(_from_negative_results(portfolio))
    specs.extend(_from_measurement_opportunities(portfolio))
    specs.extend(_from_theory_opportunities(portfolio))
    return _dedupe_specs(specs)


def _from_topic_variants(portfolio: TopicPortfolio) -> list[dict]:
    specs: list[dict] = []
    for variant in portfolio.topic_variants:
        contribution_type = _contribution_from_variant(variant)
        specs.append(
            _spec(
                source="topic_variant",
                title=f"{variant.text} seed",
                summary=f"Seed idea from topic variant `{variant.id}`: {variant.rationale}",
                contribution_type=contribution_type,
                source_topic_id=variant.id,
                source_ids=[portfolio.id, variant.id],
                proposed_experiment=_experiment_for_variant(variant),
                expected_baselines=_baselines_for_variant(variant),
                expected_metrics=_metrics_for_variant(variant),
                likely_failure_mode=variant.risk or "The topic variant may be too broad or already covered.",
                tractability_score=0.45,
                impact_score=0.45,
                reviewer_risk_score=0.65,
                idea_yield_score=0.35,
            )
        )
    return specs


def _from_repeated_gaps(portfolio: TopicPortfolio, memory_records: list[ProjectMemoryRecord]) -> list[dict]:
    gap_records = [record for record in memory_records if record.record_type == "gap" and record.status != "rejected"]
    specs: list[dict] = []
    for record in gap_records[:10]:
        specs.append(
            _spec(
                source="repeated_literature_gap",
                title=f"Evidence-backed gap seed: {_short_title(record.text)}",
                summary=f"Project memory contains a repeated or synced gap: {record.text}",
                contribution_type="measurement",
                source_ids=[portfolio.id, record.id, *record.linked_object_ids],
                supporting_paper_ids=record.linked_paper_ids,
                evidence_score=0.35 if record.linked_paper_ids else 0.1,
                proposed_experiment="Turn the repeated literature gap into a scoped measurement or benchmark protocol.",
                expected_metrics=["false positive rate", "coverage", "failure mode count"],
                likely_failure_mode="The gap may collapse after closest-prior-work review or may lack executable artifacts.",
                idea_yield_score=0.45,
            )
        )
    return specs


def _from_unresolved_dossiers(portfolio: TopicPortfolio, dossiers: list[NoveltyDossier]) -> list[dict]:
    unresolved = [
        dossier
        for dossier in dossiers
        if dossier.verdict in {"unknown", "revise", "needs_more_search", ""}
        or dossier.novelty_strength in {"unknown", "weak", ""}
        or dossier.missing_searches
    ]
    specs: list[dict] = []
    for dossier in unresolved[:10]:
        specs.append(
            _spec(
                source="unresolved_novelty_dossier",
                title=f"Resolve novelty uncertainty for {_short_title(dossier.idea_summary or dossier.target_id)}",
                summary=f"Novelty dossier `{dossier.target_id}` remains unresolved and needs a sharper candidate.",
                contribution_type="survey" if dossier.missing_searches else "measurement",
                source_ids=[portfolio.id, dossier.target_id],
                closest_prior_work_ids=_unique([*dossier.top_prior_work, *dossier.candidates_considered]),
                evidence_span_ids=[span.id for span in dossier.evidence_spans if span.id],
                novelty_status="unknown",
                proposed_experiment="Run missing searches and recast the idea around a decisive difference or refusal.",
                expected_metrics=["prior-work recall", "coverage gaps", "decisive difference clarity"],
                likely_failure_mode=dossier.reviewer_objection
                or dossier.decisive_difference_needed
                or "The dossier may show the idea is duplicate or under-searched.",
                reviewer_risk_score=0.85,
                idea_yield_score=0.3,
            )
        )
    return specs


def _from_rejections(
    portfolio: TopicPortfolio,
    memory_records: list[ProjectMemoryRecord],
    rejected_candidates: list[IdeaCandidate],
) -> list[dict]:
    specs: list[dict] = []
    rejected_records = [
        record for record in memory_records if record.status == "rejected" or record.record_type in {"rejected_idea", "refusal"}
    ]
    for record in rejected_records[:10]:
        specs.append(
            _spec(
                source="rejected_idea_mutation",
                title=f"Repair rejected idea with stricter scope: {_short_title(record.text)}",
                summary=f"Mutation seed from rejected project memory. Prior rejection must be repaired, not ignored: {record.text}",
                contribution_type="evaluation_protocol",
                source_ids=[portfolio.id, record.id, *record.linked_object_ids],
                supporting_paper_ids=record.linked_paper_ids,
                proposed_experiment="Narrow the rejected idea into a falsifiable evaluation protocol with explicit failure criteria.",
                expected_metrics=["specificity", "false positive rate", "refusal trigger count"],
                likely_failure_mode="The mutation may still inherit the original rejection or remain too generic.",
                reviewer_risk_score=0.9,
                idea_yield_score=0.25,
            )
        )
    for candidate in rejected_candidates[:10]:
        specs.append(
            _spec(
                source="rejected_idea_mutation",
                title=f"Mutate rejected seed: {_short_title(candidate.title)}",
                summary=f"Rejected idea candidate can seed a stricter variant: {candidate.summary}",
                contribution_type=candidate.contribution_type,
                source_ids=[portfolio.id, candidate.id],
                closest_prior_work_ids=candidate.closest_prior_work_ids,
                supporting_paper_ids=candidate.supporting_paper_ids,
                counterevidence_paper_ids=candidate.counterevidence_paper_ids,
                evidence_span_ids=candidate.evidence_span_ids,
                proposed_experiment=candidate.proposed_experiment
                or "Define a narrower protocol that directly addresses the recorded rejection.",
                expected_baselines=candidate.expected_baselines,
                expected_metrics=candidate.expected_metrics,
                likely_failure_mode=candidate.rejection_reason or "The new seed may repeat the rejected candidate's flaw.",
                reviewer_risk_score=0.9,
                idea_yield_score=0.25,
            )
        )
    return specs


def _from_research_agenda(portfolio: TopicPortfolio, directions: list[ResearchDirection]) -> list[dict]:
    agenda_directions = [
        direction
        for direction in directions
        if direction.maturity in {"seed", "agenda_item", "candidate"} and direction.project_id == portfolio.project_id
    ]
    specs: list[dict] = []
    for direction in agenda_directions[:10]:
        linked_ids = _unique(
            [
                *direction.linked_gap_ids,
                *direction.linked_hypothesis_ids,
                *direction.linked_experiment_ids,
                *direction.linked_novelty_dossier_ids,
            ]
        )
        specs.append(
            _spec(
                source="topic_variant",
                title=f"Research-agenda seed: {_short_title(direction.title)}",
                summary=(f"Existing research agenda direction `{direction.id}` can be expanded into a v2 idea seed. {direction.summary}"),
                contribution_type="hybrid",
                source_ids=[portfolio.id, direction.id, *linked_ids],
                supporting_paper_ids=direction.supporting_paper_ids,
                counterevidence_paper_ids=direction.counterevidence_paper_ids,
                novelty_status="unchecked",
                proposed_experiment="Convert the agenda direction into a seed with explicit baselines, metrics, and refusal criteria.",
                expected_metrics=["idea yield score", "closest-prior-work risk", "tractability"],
                likely_failure_mode="The agenda item may still be too broad or may not survive novelty review.",
                tractability_score=max(0.2, min(direction.readiness_score, 0.65)),
                evidence_score=0.25 if direction.supporting_paper_ids else 0.05,
                reviewer_risk_score=0.75 if direction.blocking_issues else 0.6,
                idea_yield_score=0.35,
            )
        )
    return specs


def _from_human_preferences(portfolio: TopicPortfolio, human_reviews: list[HumanReviewRecord]) -> list[dict]:
    specs: list[dict] = []
    rejected = [review for review in human_reviews if review.action == "reject" or "reject" in review.note.lower()]
    approved = [
        review
        for review in human_reviews
        if review.action in {"approve", "lock"} and review.note and review.object_type in {"gap", "direction", "experiment", "claim"}
    ]
    for review in rejected[:8]:
        specs.append(
            _spec(
                source="rejected_idea_mutation",
                title=f"Repair human-rejected seed: {_short_title(review.note or review.object_id)}",
                summary=(
                    f"Human review `{review.id}` rejected `{review.object_type}:{review.object_id}`. "
                    "Generate only a repaired seed that directly addresses the recorded objection."
                ),
                contribution_type="evaluation_protocol",
                source_ids=[portfolio.id, review.id, review.object_id],
                proposed_experiment="Define a narrower protocol that makes the human rejection condition testable.",
                expected_metrics=["specificity", "false positive rate", "human objection closure"],
                likely_failure_mode=review.note or "The repaired seed may still fail the human objection.",
                reviewer_risk_score=0.9,
                idea_yield_score=0.24,
            )
        )
    for review in approved[:8]:
        specs.append(
            _spec(
                source="topic_variant",
                title=f"Human-preferred seed: {_short_title(review.note)}",
                summary=(
                    f"Human review `{review.id}` marked `{review.object_type}:{review.object_id}` as worth preserving. "
                    "Treat this as preference signal only, not as evidence of novelty."
                ),
                contribution_type="hybrid",
                source_ids=[portfolio.id, review.id, review.object_id],
                novelty_status="unchecked",
                proposed_experiment="Turn the preferred object into a seed and run normal evidence and novelty gates.",
                expected_metrics=["preference alignment", "novelty risk", "tractability"],
                likely_failure_mode="Human preference may reflect usefulness rather than publishable novelty.",
                tractability_score=0.45,
                impact_score=0.45,
                reviewer_risk_score=0.65,
                idea_yield_score=0.38,
            )
        )
    return specs


def _from_cross_domain_transfers(portfolio: TopicPortfolio) -> list[dict]:
    specs: list[dict] = []
    for variant in portfolio.topic_variants:
        if variant.transformation_type != "cross_domain":
            continue
        specs.append(
            _spec(
                source="cross_domain_transfer",
                title=f"Transfer seed from {variant.text}",
                summary=f"Cross-domain transfer candidate from portfolio variant `{variant.id}`.",
                contribution_type=_contribution_from_variant(variant),
                source_topic_id=variant.id,
                source_ids=[portfolio.id, variant.id],
                proposed_experiment="Map source-domain assumptions to the target setting and test which assumptions break.",
                expected_metrics=["transfer validity", "false positive rate", "assumption violation count"],
                likely_failure_mode=variant.risk or "The analogy may be shallow and fail during domain adaptation.",
                tractability_score=0.35,
                impact_score=0.5,
                reviewer_risk_score=0.75,
                idea_yield_score=0.35,
            )
        )
    return specs


def _from_missing_benchmarks(portfolio: TopicPortfolio, matrices: list[RelatedWorkMatrix]) -> list[dict]:
    specs: list[dict] = []
    missing_benchmark = [
        matrix
        for matrix in matrices
        if any("benchmark" in item.lower() or "baseline" in item.lower() or "dataset" in item.lower() for item in matrix.missing_categories)
    ]
    if missing_benchmark or portfolio.benchmark_topics:
        paper_ids = _unique(
            [paper_id for matrix in missing_benchmark for paper_id in [*matrix.must_read_paper_ids, *matrix.baseline_paper_ids]]
        )
        specs.append(
            _spec(
                source="missing_benchmark",
                title=f"Missing benchmark seed for {portfolio.root_topic}",
                summary="Related-work or portfolio state suggests a benchmark/dataset gap that should become an explicit seed.",
                contribution_type="benchmark",
                source_ids=[portfolio.id, *[matrix.direction_id for matrix in missing_benchmark]],
                closest_prior_work_ids=paper_ids,
                supporting_paper_ids=paper_ids,
                proposed_experiment="Construct a benchmark with benign negatives, adversarial positives, and documented labeling limits.",
                expected_baselines=["existing monitors", "simple heuristic detector"],
                expected_metrics=["false positive rate", "true positive rate", "confidence interval"],
                likely_failure_mode="The benchmark may lack realistic labels, strong baselines, or data access.",
                idea_yield_score=0.5,
            )
        )
    return specs


def _from_missing_evaluation_protocols(
    portfolio: TopicPortfolio,
    matrices: list[RelatedWorkMatrix],
    campaigns: list[ResearchCampaign],
) -> list[dict]:
    needs_protocol = any(
        any("metric" in item.lower() or "evaluation" in item.lower() or "protocol" in item.lower() for item in matrix.missing_categories)
        for matrix in matrices
    )
    if not needs_protocol and not campaigns:
        return []
    return [
        _spec(
            source="missing_evaluation_protocol",
            title=f"Evaluation protocol seed for {portfolio.root_topic}",
            summary="Campaign or related-work state suggests the next idea should be an explicit evaluation protocol, not a broad claim.",
            contribution_type="evaluation_protocol",
            source_ids=[portfolio.id, *[campaign.id for campaign in campaigns[:5]], *[matrix.direction_id for matrix in matrices[:5]]],
            proposed_experiment="Specify datasets, baselines, thresholds, and refusal conditions before any result claim.",
            expected_metrics=["specificity", "false positive rate", "power warning"],
            likely_failure_mode="The protocol may reveal that the topic is underpowered, unmeasurable, or already evaluated.",
            idea_yield_score=0.4,
        )
    ]


def _from_negative_results(portfolio: TopicPortfolio) -> list[dict]:
    variants = [variant for variant in portfolio.topic_variants if "negative_result" in variant.likely_contribution_types]
    return [
        _spec(
            source="negative_result_opportunity",
            title=f"Negative-result seed: {_short_title(variant.text)}",
            summary=f"Use variant `{variant.id}` to test whether existing approaches fail under stricter conditions.",
            contribution_type="negative_result",
            source_topic_id=variant.id,
            source_ids=[portfolio.id, variant.id],
            proposed_experiment=(
                "Replicate or stress existing monitors under low false-positive requirements and preserve negative outcomes."
            ),
            expected_baselines=["published monitor", "simple detector"],
            expected_metrics=["false positive rate", "failure slice count"],
            likely_failure_mode=variant.risk or "Negative results may be inconclusive without strong baselines.",
            reviewer_risk_score=0.75,
            idea_yield_score=0.35,
        )
        for variant in variants[:8]
    ]


def _from_measurement_opportunities(portfolio: TopicPortfolio) -> list[dict]:
    variants = [
        variant
        for variant in portfolio.topic_variants
        if variant.transformation_type in {"metric_shift", "evaluation_shift", "data_shift", "narrower"}
    ]
    return [
        _spec(
            source="measurement_study_opportunity",
            title=f"Measurement-study seed: {_short_title(variant.text)}",
            summary=f"Convert variant `{variant.id}` into a measurement study seed.",
            contribution_type="measurement",
            source_topic_id=variant.id,
            source_ids=[portfolio.id, variant.id],
            proposed_experiment="Measure false-positive behavior across benign and suspicious interaction slices.",
            expected_metrics=["false positive rate", "slice-level error rate", "uncertainty interval"],
            likely_failure_mode=variant.risk or "The measurement may not isolate a contribution beyond descriptive statistics.",
            idea_yield_score=0.38,
        )
        for variant in variants[:8]
    ]


def _from_theory_opportunities(portfolio: TopicPortfolio) -> list[dict]:
    variants = [variant for variant in portfolio.topic_variants if variant.transformation_type == "theory_shift"]
    return [
        _spec(
            source="theory_guarantee_opportunity",
            title=f"Theory/guarantee seed: {_short_title(variant.text)}",
            summary=f"Use variant `{variant.id}` to explore formal limits or guarantees.",
            contribution_type="theory",
            source_topic_id=variant.id,
            source_ids=[portfolio.id, variant.id],
            proposed_experiment="Define assumptions and show either a limit, guarantee, or falsifying counterexample.",
            expected_metrics=["assumption coverage", "counterexample count"],
            likely_failure_mode=variant.risk or "The theory may be too abstract to help empirical agent monitoring.",
            tractability_score=0.25,
            impact_score=0.45,
            reviewer_risk_score=0.8,
            idea_yield_score=0.28,
        )
        for variant in variants[:5]
    ]


def _spec(**kwargs) -> dict:
    kwargs.setdefault("novelty_status", "unchecked")
    if kwargs["novelty_status"] == "strong":
        kwargs["novelty_status"] = "plausible"
    kwargs.setdefault("expected_baselines", [])
    kwargs.setdefault("expected_metrics", [])
    kwargs.setdefault("closest_prior_work_ids", [])
    kwargs.setdefault("supporting_paper_ids", [])
    kwargs.setdefault("counterevidence_paper_ids", [])
    kwargs.setdefault("evidence_span_ids", [])
    kwargs.setdefault("core_claim", "")
    kwargs.setdefault("source_topic_id", "")
    kwargs.setdefault("source_ids", [])
    return kwargs


def _contribution_from_variant(variant: TopicVariant) -> str:
    for contribution in variant.likely_contribution_types:
        if contribution in {
            "benchmark",
            "measurement",
            "method",
            "theory",
            "negative_result",
            "replication",
            "dataset",
            "survey",
            "system",
            "evaluation_protocol",
            "tooling",
            "hybrid",
        }:
            return contribution
    return "hybrid"


def _experiment_for_variant(variant: TopicVariant) -> str:
    if variant.transformation_type == "benchmark_shift":
        return "Create a benchmark card, baseline registry, metric registry, and benign/adversarial trace splits."
    if variant.transformation_type == "cross_domain":
        return "Map source-domain criteria to LLM agent traces and test whether the adaptation survives counterexamples."
    if variant.transformation_type == "theory_shift":
        return "Formalize assumptions and search for distinguishability limits or counterexamples."
    return "Run a scoped literature search, define baselines and metrics, then test the candidate on a small auditable protocol."


def _baselines_for_variant(variant: TopicVariant) -> list[str]:
    if variant.transformation_type == "benchmark_shift":
        return ["existing collusion monitor", "simple communication-pattern heuristic"]
    if variant.transformation_type == "cross_domain":
        return ["target-domain monitor", "source-domain screening analogue"]
    return ["closest prior-work baseline", "simple heuristic baseline"]


def _metrics_for_variant(variant: TopicVariant) -> list[str]:
    if variant.transformation_type == "theory_shift":
        return ["assumption count", "counterexample count"]
    if variant.transformation_type == "cross_domain":
        return ["false positive rate", "transfer validity"]
    return ["false positive rate", "true positive rate", "confidence interval"]


def _short_title(text: str) -> str:
    clean = text.split("| Reason:", 1)[0].strip()
    words = [word.strip("`.,:;()[]{}") for word in clean.split() if word.strip("`.,:;()[]{}")]
    return " ".join(words[:10]) or "untitled seed"


def _dedupe_specs(specs: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for spec in specs:
        key = slugify(spec["title"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(spec)
    return deduped


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
