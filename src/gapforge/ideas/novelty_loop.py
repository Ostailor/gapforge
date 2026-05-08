"""Idea-specific novelty and counterevidence loop."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.ideas.models import IdeaCandidate, IdeaNoveltyAssessment
from gapforge.ideas.mutation import IdeaMutationEngine
from gapforge.ideas.store import IdeaStore
from gapforge.models import Paper, Provenance, ResearchRunState
from gapforge.novelty.comparator import PriorWorkComparator, PriorWorkMatch, comparison_row
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval.hybrid import retrieval_candidates_for_state
from gapforge.sources.coverage import add_search_query_record
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso


@dataclass(slots=True)
class IdeaNoveltyRunResult:
    assessments: list[IdeaNoveltyAssessment] = field(default_factory=list)


class IdeaNoveltyLoop:
    """Assess idea candidates against current corpus, optional live sources, and counterevidence."""

    def __init__(
        self,
        config: GapForgeConfig,
        *,
        sources: list[Any] | None = None,
        search_sources: bool = False,
        comparator: PriorWorkComparator | None = None,
    ) -> None:
        self.config = config
        self.store = IdeaStore(config)
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.sources = sources or []
        self.search_sources = search_sources
        self.comparator = comparator or PriorWorkComparator()
        self.mutations = IdeaMutationEngine(config)

    def assess_idea(self, idea_id: str, *, top_k: int = 10, counterevidence_only: bool = False) -> IdeaNoveltyAssessment:
        state, candidate = self.store.load_by_idea_id(idea_id)
        program = self.project_manager.sync_project_memory(candidate.project_id)
        run_states = _load_runs(self.state_manager, program.run_ids)
        queries = generate_idea_prior_work_queries(candidate)
        retrieval_papers, retrieval_evidence = self._search_current_corpus(candidate, run_states, top_k=top_k)
        live_papers, live_missing = self._search_live_sources(candidate, run_states, queries)
        candidate_papers = _dedupe_papers([*retrieval_papers, *live_papers])
        matches = self.comparator.compare(
            _idea_summary(candidate),
            candidate_papers,
            notes=[note for run in run_states for note in run.paper_notes],
            sections=[section for run in run_states for section in run.paper_sections],
        )
        missing_searches = _missing_searches(
            run_states=run_states,
            retrieval_evidence=retrieval_evidence,
            live_missing=live_missing,
            candidate_papers=candidate_papers,
            live_sources_requested=self.search_sources,
            live_sources_available=bool(self.sources),
        )
        counterevidence = self._find_counterevidence(candidate, run_states, matches, candidate_papers, top_k=top_k)
        verdict, strength, required_mutation = _verdict(candidate, matches, missing_searches, counterevidence, counterevidence_only)
        assessment = IdeaNoveltyAssessment(
            id=_assessment_id(candidate.id, verdict, matches, counterevidence),
            idea_id=candidate.id,
            closest_prior_work_ids=[match.paper.id for match in matches[: min(top_k, 5)]],
            similarity_summary=_similarity_summary(matches, retrieval_evidence),
            missing_searches=missing_searches,
            counterevidence=counterevidence,
            verdict=verdict,
            novelty_strength=strength,
            required_mutation=required_mutation,
            provenance=Provenance(
                created_by_skill="idea-novelty-loop",
                source_ids=[candidate.id, *[match.paper.id for match in matches[:5]], *counterevidence],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Assessed idea novelty against current corpus, retrieval-ranked closest prior work, "
                    "and stored counterevidence. Strong novelty is blocked without completed prior-work search."
                ),
            ),
        )
        self._apply_assessment(state.idea_bank.project_id if state.idea_bank else candidate.project_id, candidate.id, assessment)
        self._link_assessment_evidence(assessment)
        self.write_report(candidate.project_id)
        return assessment

    def assess_project(self, project_id: str, *, top_k: int = 10) -> IdeaNoveltyRunResult:
        state = self.store.load_state(project_id)
        candidates = _promising_candidates(state.candidates, top_k=top_k)
        return IdeaNoveltyRunResult(assessments=[self.assess_idea(candidate.id, top_k=top_k) for candidate in candidates])

    def find_counterevidence(self, idea_id: str, *, top_k: int = 10) -> IdeaNoveltyAssessment:
        return self.assess_idea(idea_id, top_k=top_k, counterevidence_only=True)

    def render_report(self, project_id: str) -> str:
        state = self.store.load_state(project_id)
        lines = [
            "# Idea Novelty Assessments",
            "",
            "Idea novelty assessments are evidence-gated. Missing searches keep novelty unknown, and counterevidence is persisted.",
            "",
        ]
        if not state.novelty_assessments:
            lines.append("- none")
            return "\n".join(lines).rstrip() + "\n"
        for assessment in state.novelty_assessments:
            lines.extend(
                [
                    f"## `{assessment.id}`",
                    "",
                    f"- Idea ID: `{assessment.idea_id}`",
                    f"- Verdict: `{assessment.verdict}`",
                    f"- Novelty strength: `{assessment.novelty_strength}`",
                    f"- Closest prior work: {', '.join(assessment.closest_prior_work_ids) or 'none'}",
                    f"- Missing searches: {'; '.join(assessment.missing_searches) or 'none'}",
                    f"- Counterevidence: {'; '.join(assessment.counterevidence) or 'none'}",
                    f"- Required mutation: {assessment.required_mutation or 'none'}",
                    f"- Similarity summary: {assessment.similarity_summary or 'not recorded'}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def write_report(self, project_id: str) -> str:
        report = self.render_report(project_id)
        program = self.project_manager.load_project(project_id)
        reports_dir = Path(program.project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "idea_novelty.md").write_text(report, encoding="utf-8")
        return report

    def _search_current_corpus(
        self,
        candidate: IdeaCandidate,
        run_states: list[ResearchRunState],
        *,
        top_k: int,
    ) -> tuple[list[Paper], list[str]]:
        summary = _idea_summary(candidate)
        paper_by_id: dict[str, Paper] = {}
        evidence: list[str] = []
        for run in run_states:
            for paper in run.papers:
                paper_by_id.setdefault(paper.id, paper)
            try:
                results, paper_ids = retrieval_candidates_for_state(run, summary, top_k=max(top_k, 10), persist=True)
            except (FileNotFoundError, ValueError, OSError, RuntimeError) as exc:
                evidence.append(f"{run.run_id}: retrieval failed: {type(exc).__name__}: {exc}")
                continue
            evidence.append(f"{run.run_id}: retrieval_results={len(results)}")
            for paper_id in paper_ids:
                found_paper = next((item for item in run.papers if item.id == paper_id), None)
                if found_paper is not None:
                    paper_by_id.setdefault(found_paper.id, found_paper)
        return list(paper_by_id.values()), evidence

    def _search_live_sources(
        self,
        candidate: IdeaCandidate,
        run_states: list[ResearchRunState],
        queries: list[str],
    ) -> tuple[list[Paper], list[str]]:
        if not self.search_sources:
            return [], []
        if not self.sources:
            return [], ["live source search requested but no source connectors were configured"]
        found: list[Paper] = []
        failures: list[str] = []
        for query in queries[:8]:
            found_for_query: list[Paper] = []
            for source in self.sources:
                source_name = str(getattr(source, "name", source.__class__.__name__))
                try:
                    found_for_query.extend(source.search(query, max_results=3, sort="relevance", date_from=None, date_to=None))
                except Exception as exc:  # pragma: no cover - source connectors are integration surfaces
                    failures.append(f"{source_name} search failed for {query!r}: {exc}")
            found.extend(found_for_query)
            if run_states:
                add_search_query_record(
                    run_states[0],
                    query=query,
                    source_names=[str(getattr(source, "name", source.__class__.__name__)) for source in self.sources],
                    purpose="idea_novelty",
                    max_results=3 * max(1, len(self.sources)),
                    date_from=None,
                    date_to=None,
                    result_paper_ids=[paper.id for paper in found_for_query],
                    failure_messages=failures,
                )
                self.state_manager.save_run(run_states[0])
        if _network_disabled():
            failures.append("GAPFORGE_DISABLE_NETWORK=1; live source novelty search was not executed")
        return found, failures

    def _find_counterevidence(
        self,
        candidate: IdeaCandidate,
        run_states: list[ResearchRunState],
        matches: list[PriorWorkMatch],
        candidate_papers: list[Paper],
        *,
        top_k: int,
    ) -> list[str]:
        summary = _idea_summary(candidate)
        labels: list[str] = []
        paper_by_id = {paper.id: paper for paper in candidate_papers}
        for run in run_states:
            query = f"{summary} counterevidence duplicate already solves closest prior work"
            try:
                results, paper_ids = retrieval_candidates_for_state(run, query, top_k=max(top_k, 10), persist=True)
            except (FileNotFoundError, ValueError, OSError, RuntimeError):
                results, paper_ids = [], []
            for paper_id in paper_ids:
                paper = paper_by_id.get(paper_id) or next((item for item in run.papers if item.id == paper_id), None)
                if paper is not None and _paper_has_counterevidence_text(paper, run):
                    labels.append(f"{paper.id}: {_counterevidence_note(paper)}")
            for result in results:
                if result.paper_id and _result_mentions_counterevidence(result):
                    labels.append(f"{result.paper_id}: retrieval result suggests counterevidence at {result.locator or result.document_id}")
        for match in matches[:5]:
            if _match_solves_core(match):
                labels.append(f"{match.paper.id}: closest prior work appears to solve the core idea")
        return _dedupe(labels)

    def _apply_assessment(self, project_id: str, idea_id: str, assessment: IdeaNoveltyAssessment) -> None:
        state, candidate = self.store.load_by_idea_id(idea_id)
        if assessment.verdict == "reject":
            candidate.novelty_status = "likely_duplicate"
            candidate.maturity = "rejected"
            candidate.rejection_reason = (
                "Idea novelty loop found closest prior work or counterevidence that appears to solve the core idea. "
                f"Required mutation: {assessment.required_mutation or 'not specified'}."
            )
            if state.idea_bank is not None:
                state.idea_bank.rejected_candidate_ids = _dedupe([*state.idea_bank.rejected_candidate_ids, candidate.id])
        elif assessment.verdict == "revise":
            candidate.novelty_status = "weak"
            candidate.maturity = "candidate"
            candidate.likely_failure_mode = _append_sentence(
                candidate.likely_failure_mode,
                f"Novelty loop requires mutation `{assessment.required_mutation}` before promotion.",
            )
        elif assessment.verdict == "pursue":
            candidate.novelty_status = "plausible" if assessment.novelty_strength != "strong" else "strong"
            candidate.maturity = "candidate" if candidate.maturity == "seed" else candidate.maturity
            candidate.idea_yield_score = max(candidate.idea_yield_score, 0.45 if assessment.novelty_strength == "medium" else 0.55)
        else:
            candidate.novelty_status = "unknown"
        candidate.closest_prior_work_ids = _dedupe([*candidate.closest_prior_work_ids, *assessment.closest_prior_work_ids])
        candidate.counterevidence_paper_ids = _dedupe(
            [*candidate.counterevidence_paper_ids, *[_paper_id_from_label(label) for label in assessment.counterevidence]]
        )
        state.novelty_assessments.append(assessment)
        if state.idea_bank is not None:
            state.idea_bank.updated_at = utc_now_iso()
        self.store._save_state(project_id, state)

    def _link_assessment_evidence(self, assessment: IdeaNoveltyAssessment) -> None:
        for paper_id in assessment.closest_prior_work_ids[:10]:
            self.store.link_evidence(
                idea_id=assessment.idea_id,
                link_type="closest_prior_work",
                paper_id=paper_id,
                note=f"Closest prior work from novelty assessment `{assessment.id}`.",
                confidence="medium" if assessment.verdict in {"revise", "pursue"} else "high",
            )
        for label in assessment.counterevidence:
            paper_id = _paper_id_from_label(label)
            self.store.link_evidence(
                idea_id=assessment.idea_id,
                link_type="counters",
                paper_id=paper_id,
                note=label,
                confidence="high" if assessment.verdict == "reject" else "medium",
            )
        for missing in assessment.missing_searches:
            self.store.link_evidence(
                idea_id=assessment.idea_id,
                link_type="missing_evidence",
                note=missing,
                confidence="high",
            )


def generate_idea_prior_work_queries(candidate: IdeaCandidate) -> list[str]:
    summary = _idea_summary(candidate)
    title = candidate.title.strip()
    metrics = " ".join(candidate.expected_metrics[:4])
    baselines = " ".join(candidate.expected_baselines[:4])
    queries = [
        f'"{title}"',
        f"{title} closest prior work",
        f"{title} duplicate benchmark measurement evaluation",
        f"{candidate.contribution_type} {metrics} {baselines} prior work",
        f"{summary[:180]} closest prior work",
        f"{summary[:180]} counterevidence already solves",
        f"{summary[:180]} survey systematic review",
    ]
    return _dedupe([_clean_query(query) for query in queries if _clean_query(query)])


def _promising_candidates(candidates: list[IdeaCandidate], *, top_k: int) -> list[IdeaCandidate]:
    active = [candidate for candidate in candidates if candidate.maturity not in {"rejected", "agenda_item", "manuscript_ready"}]
    return sorted(
        active,
        key=lambda candidate: (candidate.idea_yield_score, candidate.impact_score, candidate.evidence_score, candidate.title),
        reverse=True,
    )[:top_k]


def _load_runs(manager: ResearchStateManager, run_ids: list[str]) -> list[ResearchRunState]:
    states: list[ResearchRunState] = []
    for run_id in run_ids:
        try:
            states.append(manager.load_run(run_id))
        except FileNotFoundError:
            continue
    return states


def _missing_searches(
    *,
    run_states: list[ResearchRunState],
    retrieval_evidence: list[str],
    live_missing: list[str],
    candidate_papers: list[Paper],
    live_sources_requested: bool,
    live_sources_available: bool,
) -> list[str]:
    missing = list(live_missing)
    if not run_states:
        missing.append("current corpus search: no attached runs for this project")
    if not candidate_papers:
        missing.append("current corpus search: no papers available for closest-prior-work comparison")
    if run_states and not retrieval_evidence:
        missing.append("retrieval search did not complete for any run")
    if live_sources_requested and not live_sources_available:
        missing.append("live source search could not run because no source connectors were configured")
    return _dedupe(missing)


def _verdict(
    candidate: IdeaCandidate,
    matches: list[PriorWorkMatch],
    missing_searches: list[str],
    counterevidence: list[str],
    counterevidence_only: bool,
) -> tuple[str, str, str]:
    if missing_searches and not matches:
        return "unknown", "unknown", ""
    top = matches[0] if matches else None
    if top is not None and (_match_solves_core(top) or top.overall_similarity >= 0.72):
        return "reject", "weak", _required_mutation(candidate, top)
    if counterevidence:
        if any("appears to solve" in item or "already solves" in item.lower() for item in counterevidence):
            return "reject", "weak", _required_mutation(candidate, top)
        return "revise", "weak", _required_mutation(candidate, top)
    if counterevidence_only:
        return "unknown", "unknown", ""
    if top is None:
        return "unknown", "unknown", ""
    if _match_leaves_target_gap(top):
        return "pursue", "medium", ""
    if top.overall_similarity >= 0.38 or (top.problem_overlap >= 0.5 and top.evaluation_overlap >= 0.4):
        return "revise", "weak", _required_mutation(candidate, top)
    if missing_searches:
        return "unknown", "unknown", ""
    if top.overall_similarity >= 0.08:
        return "pursue", "medium", ""
    return "unknown", "unknown", ""


def _required_mutation(candidate: IdeaCandidate, match: PriorWorkMatch | None) -> str:
    if candidate.contribution_type == "method":
        return "method_to_measurement"
    if candidate.contribution_type in {"benchmark", "evaluation_protocol"}:
        return "metric_shift"
    if match is not None and match.evaluation_overlap >= 0.5:
        return "benchmark_shift"
    return "reviewer_objection_to_new_idea"


def _match_solves_core(match: PriorWorkMatch) -> bool:
    if "solves" in match.paper.abstract.lower() or "already covers" in match.paper.abstract.lower():
        return True
    return match.problem_overlap >= 0.6 and match.method_overlap >= 0.5 and match.evaluation_overlap >= 0.5


def _match_leaves_target_gap(match: PriorWorkMatch) -> bool:
    text = match.paper.abstract.lower()
    return any(marker in text for marker in ("does not evaluate", "does not address", "does not cover", "limited to"))


def _paper_has_counterevidence_text(paper: Paper, run: ResearchRunState) -> bool:
    text = _paper_text(paper, run)
    return any(marker in text for marker in _COUNTEREVIDENCE_MARKERS)


def _result_mentions_counterevidence(result: Any) -> bool:
    text = " ".join(
        [
            str(getattr(result, "title", "")),
            str(getattr(result, "text_snippet", "")),
            str(getattr(result, "metadata", {})),
        ]
    ).lower()
    return any(marker in text for marker in _COUNTEREVIDENCE_MARKERS)


def _counterevidence_note(paper: Paper) -> str:
    text = " ".join([paper.title, paper.abstract]).lower()
    if "already solves" in text or "solves the core" in text:
        return "paper text says the prior work already solves the core idea"
    if "duplicate" in text or "not novel" in text:
        return "paper text raises duplicate or not-novel risk"
    return "paper text contains counterevidence against the idea framing"


def _paper_text(paper: Paper, run: ResearchRunState) -> str:
    sections = " ".join(section.text for section in run.paper_sections if section.paper_id == paper.id)
    notes = " ".join(
        " ".join(
            [
                note.one_sentence_summary,
                *note.core_claims,
                *note.main_results,
                *note.stated_limitations,
                *note.what_it_cannot_answer,
            ]
        )
        for note in run.paper_notes
        if note.paper_id == paper.id
    )
    return " ".join([paper.title, paper.abstract, sections, notes]).lower()


def _similarity_summary(matches: list[PriorWorkMatch], retrieval_evidence: list[str]) -> str:
    if not matches:
        return "No closest prior work was found in the current comparison set. " + "; ".join(retrieval_evidence)
    rows = [comparison_row(match) for match in matches[:3]]
    parts = [
        f"{row['paper_id']} similarity={row['overall_similarity']} problem={row['problem_overlap']} "
        f"method={row['method_overlap']} evaluation={row['evaluation_overlap']}"
        for row in rows
    ]
    if retrieval_evidence:
        parts.append("retrieval: " + "; ".join(retrieval_evidence[:4]))
    return "; ".join(parts)


def _idea_summary(candidate: IdeaCandidate) -> str:
    return " ".join(
        [
            candidate.title,
            candidate.summary,
            candidate.core_claim,
            candidate.proposed_experiment,
            " ".join(candidate.expected_baselines),
            " ".join(candidate.expected_metrics),
        ]
    ).strip()


def _assessment_id(idea_id: str, verdict: str, matches: list[PriorWorkMatch], counterevidence: list[str]) -> str:
    digest = hashlib.sha1(
        "::".join([idea_id, verdict, *[match.paper.id for match in matches[:5]], *counterevidence, utc_now_compact()]).encode()
    ).hexdigest()[:10]
    return f"idea-novelty-{digest}"


def _dedupe_papers(papers: list[Paper]) -> list[Paper]:
    by_id: dict[str, Paper] = {}
    for paper in papers:
        if paper.id:
            by_id.setdefault(paper.id, paper)
    return list(by_id.values())


def _paper_id_from_label(label: str) -> str:
    return label.split(":", 1)[0].strip() or "unknown-paper"


def _append_sentence(existing: str, sentence: str) -> str:
    if not existing:
        return sentence
    if sentence in existing:
        return existing
    return f"{existing.rstrip('.')} . {sentence}"


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _network_disabled() -> bool:
    return os.environ.get("GAPFORGE_DISABLE_NETWORK", "").strip() == "1"


_COUNTEREVIDENCE_MARKERS = (
    "counterevidence",
    "already solves",
    "solves the core",
    "already covers",
    "duplicate",
    "not novel",
    "subsumes",
    "same benchmark",
)
