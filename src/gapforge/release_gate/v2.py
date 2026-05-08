"""v2 release gate for Idea Discovery Engine readiness."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.ideas.metrics import IdeaYieldMetricCalculator, IdeaYieldMetrics
from gapforge.ideas.models import IdeaCandidate, IdeaNoveltyAssessment
from gapforge.ideas.store import IdeaStore
from gapforge.ideas.topic_portfolio import TopicPortfolioGenerator
from gapforge.ideas.tournament import RESULT_CLAIM_MARKERS
from gapforge.models import ResearchProject
from gapforge.pilots import PilotStore
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager

try:  # Keep release gate importable if v2 pilot helpers are not loaded in minimal installs.
    from gapforge.pilots.v2 import V2_LOW_FPR_COLLUSION
except ImportError:  # pragma: no cover - defensive compatibility path.
    V2_LOW_FPR_COLLUSION = "v2_low_fpr_collusion"


@dataclass(slots=True)
class V2ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    project_id: str = ""
    pilot_id: str = ""
    selected_idea_id: str = ""
    agenda_id: str = ""
    idea_yield_rate: float = 0.0
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V2ReleaseGateEnforcer:
    """Machine-check whether v2 can be released as an Idea Discovery Engine."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"
        self.projects = ProjectMemoryManager(config)
        self.store = IdeaStore(config)
        self.portfolios = TopicPortfolioGenerator(config)
        self.metrics = IdeaYieldMetricCalculator(config)

    def evaluate(self, *, allow_agenda_only: bool = False) -> V2ReleaseGateResult:
        project_id, pilot_id = self._resolve_project()
        if not project_id:
            requirements = {
                "v1_readiness_passes": self._v1_readiness_passes(),
                "topic_portfolio_exists": False,
                "idea_bank_exists": False,
                "mutation_ran": False,
                "constructive_gap_creator_ran": False,
                "cross_domain_transfer_ran": False,
                "codex_idea_synthesis_task_ran_or_unavailable": False,
                "novelty_counterevidence_loop_ran": False,
                "idea_tournament_ran": False,
                "human_feedback_or_review_exists": False,
                "idea_yield_metrics_generated": False,
                "human_accepted_candidate_exists": False,
                "agenda_fallback_exists": False,
                "selected_idea_has_no_fake_citations": False,
                "selected_idea_has_no_fake_results": False,
                "selected_idea_has_no_fatal_novelty_blocker": False,
                "rejected_ideas_preserved": False,
            }
            blockers = ["No v2 idea discovery project found. Run `gapforge v2-pilot-run --name low_fpr_collusion` first."]
            return V2ReleaseGateResult(
                passed=False,
                status="incomplete",
                recommended_next_version="v2.0.1",
                requirements=requirements,
                blockers=blockers,
                warnings=[],
                project_id="",
                pilot_id=pilot_id,
            )

        state = self.store.load_state(project_id)
        project = self.projects.load_project(project_id).project
        portfolios = self.portfolios.list_project_portfolios(project_id)
        metrics = self.metrics.compute(project_id)
        yield_paths = self._write_yield_metrics(project_id)
        selected_candidate = self._selected_candidate(state, metrics)
        accepted_ids = _human_accepted_idea_ids(state)
        selected_id = selected_candidate.id if selected_candidate is not None else metrics.selected_idea_id
        selected_is_accepted = bool(selected_id and selected_id in accepted_ids)
        selected_fake_citations = bool(selected_candidate and self._selected_has_fake_citations(project_id, selected_candidate))
        selected_fake_results = bool(selected_candidate and _has_fake_results(selected_candidate))
        selected_fatal_novelty = bool(selected_candidate and _has_fatal_novelty_blocker(selected_candidate, state))
        agenda_fallback = self._agenda_fallback_exists(state, metrics)

        requirements = {
            "v1_readiness_passes": self._v1_readiness_passes(),
            "topic_portfolio_exists": bool(portfolios),
            "idea_bank_exists": state.idea_bank is not None,
            "mutation_ran": bool(state.mutations),
            "constructive_gap_creator_ran": bool(state.constructive_gaps),
            "cross_domain_transfer_ran": bool(state.transfer_candidates),
            "codex_idea_synthesis_task_ran_or_unavailable": self._codex_task_ran_or_unavailable(project),
            "novelty_counterevidence_loop_ran": bool(state.novelty_assessments),
            "idea_tournament_ran": bool(state.tournaments),
            "human_feedback_or_review_exists": bool(
                state.feedback_records or state.reviews or self._external_human_review_exists(pilot_id)
            ),
            "idea_yield_metrics_generated": all(path.exists() for path in yield_paths),
            "human_accepted_candidate_exists": bool(accepted_ids),
            "selected_idea_is_human_accepted": selected_is_accepted if selected_id else not accepted_ids,
            "agenda_fallback_exists": agenda_fallback,
            "selected_idea_has_no_fake_citations": not selected_fake_citations,
            "selected_idea_has_no_fake_results": not selected_fake_results,
            "selected_idea_has_no_fatal_novelty_blocker": not selected_fatal_novelty,
            "rejected_ideas_preserved": _rejected_ideas_preserved(state),
        }

        preferred_core = [
            "v1_readiness_passes",
            "topic_portfolio_exists",
            "idea_bank_exists",
            "mutation_ran",
            "constructive_gap_creator_ran",
            "cross_domain_transfer_ran",
            "codex_idea_synthesis_task_ran_or_unavailable",
            "novelty_counterevidence_loop_ran",
            "idea_tournament_ran",
            "human_feedback_or_review_exists",
            "idea_yield_metrics_generated",
            "selected_idea_has_no_fake_citations",
            "selected_idea_has_no_fake_results",
            "selected_idea_has_no_fatal_novelty_blocker",
            "rejected_ideas_preserved",
        ]
        accepted_pass = all(requirements[name] for name in preferred_core) and requirements["human_accepted_candidate_exists"]
        accepted_pass = accepted_pass and requirements["selected_idea_is_human_accepted"]
        agenda_only_pass = (
            all(requirements[name] for name in preferred_core)
            and not requirements["human_accepted_candidate_exists"]
            and requirements["agenda_fallback_exists"]
        )

        blockers = _requirement_blockers(requirements, include_agenda=not accepted_pass)
        warnings: list[str] = []
        passed = accepted_pass
        status = "pass" if accepted_pass else "fail"
        recommended_next_version = "v2.0" if accepted_pass else "v2.0.1"
        if agenda_only_pass:
            if allow_agenda_only:
                passed = True
                status = "warning_pass"
                recommended_next_version = "v2.0-agenda-only"
                blockers = []
                warnings.append(
                    "idea_discovery_incomplete: research agenda fallback accepted; release notes must say idea discovery "
                    "did not produce an accepted idea."
                )
            else:
                blockers.append("Agenda-only fallback requires --allow-agenda-only for v2.0 and must be labeled idea_discovery_incomplete.")
                recommended_next_version = "v2.0.1"
        if requirements["human_accepted_candidate_exists"] and not requirements["selected_idea_is_human_accepted"]:
            blockers.append("A human-accepted idea exists, but the selected tournament idea is not human-accepted.")
        if not accepted_pass and not agenda_only_pass and not requirements["agenda_fallback_exists"]:
            recommended_next_version = "v2.1"

        return V2ReleaseGateResult(
            passed=passed,
            status=status,
            recommended_next_version=recommended_next_version,
            requirements=requirements,
            blockers=_dedupe(blockers),
            warnings=_dedupe(warnings),
            project_id=project_id,
            pilot_id=pilot_id,
            selected_idea_id=selected_id,
            agenda_id=metrics.agenda_id,
            idea_yield_rate=metrics.idea_yield_rate,
            artifact_paths=self._artifact_paths(project, metrics, yield_paths),
        )

    def write_outputs(self, result: V2ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v2_release_gate_latest.json"
        data_md_path = self.release_dir / "v2-release-gate-latest.md"
        report = render_v2_release_gate_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v2-release-gate-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _resolve_project(self) -> tuple[str, str]:
        pilot_id = ""
        try:
            record = PilotStore(self.config).load_record(V2_LOW_FPR_COLLUSION)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            record = None
        if record is not None and record.project_id:
            return record.project_id, record.id
        active_project_id = self.projects.active_project_id()
        if active_project_id and self._has_idea_bank(active_project_id):
            return active_project_id, pilot_id
        candidates: list[tuple[float, str]] = []
        if self.config.project_root.exists():
            for path in self.config.project_root.glob("*/ideas/idea_bank.json"):
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                candidates.append((mtime, path.parents[1].name))
        if not candidates:
            return "", pilot_id
        return sorted(candidates)[-1][1], pilot_id

    def _has_idea_bank(self, project_id: str) -> bool:
        try:
            return self.store.load_state(project_id).idea_bank is not None
        except FileNotFoundError:
            return False

    def _v1_readiness_passes(self) -> bool:
        cached = _read_json_object(self.release_dir / "v1_readiness_latest.json")
        if cached:
            return cached.get("passed") is True or cached.get("status") == "pass"
        from gapforge.release_gate.v1 import V1ReadinessGate

        try:
            return V1ReadinessGate(self.config).evaluate().passed
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return False

    def _codex_task_ran_or_unavailable(self, project: ResearchProject) -> bool:
        codex_root = Path(project.root_dir) / "ideas" / "codex_tasks"
        if codex_root.exists() and any(path.name == "task.json" for path in codex_root.glob("*/task.json")):
            return True
        unavailable_paths = [
            codex_root / "UNAVAILABLE.md",
            codex_root / "codex_unavailable.json",
            Path(project.root_dir) / "ideas" / "codex_idea_synthesis_unavailable.json",
        ]
        return any(path.exists() for path in unavailable_paths)

    def _external_human_review_exists(self, pilot_id: str) -> bool:
        if not pilot_id:
            return False
        try:
            return bool(PilotStore(self.config).load_external_reviews(pilot_id))
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return False

    def _write_yield_metrics(self, project_id: str) -> list[Path]:
        self.metrics.write_report(project_id)
        program = self.projects.load_project(project_id)
        reports_dir = Path(program.project.root_dir) / "ideas" / "reports"
        return [reports_dir / "idea_yield.md", reports_dir / "idea_yield.json"]

    def _selected_candidate(self, state, metrics: IdeaYieldMetrics) -> IdeaCandidate | None:
        selected_id = metrics.selected_idea_id
        if not selected_id and state.tournaments:
            selected_id = state.tournaments[-1].selected_candidate_id
        if not selected_id:
            accepted_ids = _human_accepted_idea_ids(state)
            selected_id = next(iter(sorted(accepted_ids)), "")
        return next((candidate for candidate in state.candidates if candidate.id == selected_id), None)

    def _selected_has_fake_citations(self, project_id: str, candidate: IdeaCandidate) -> bool:
        claimed = _claimed_paper_ids(candidate)
        if not claimed:
            return False
        return bool(claimed - self._known_paper_ids(project_id))

    def _known_paper_ids(self, project_id: str) -> set[str]:
        known: set[str] = set()
        try:
            program = self.projects.sync_project_memory(project_id)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            program = self.projects.load_project(project_id)
        known.update(record.paper_id for record in program.corpus_papers)
        for record in program.corpus_papers:
            known.update(record.source_paper_ids)
        state_manager = ResearchStateManager(self.config)
        for run_id in program.run_ids:
            try:
                run = state_manager.load_run(run_id)
            except FileNotFoundError:
                continue
            known.update(paper.id for paper in run.papers)
        state = self.store.load_state(project_id)
        known.update(link.paper_id for link in state.evidence_links if link.paper_id)
        return {paper_id for paper_id in known if paper_id}

    def _agenda_fallback_exists(self, state, metrics: IdeaYieldMetrics) -> bool:
        if not metrics.agenda_generated or not metrics.agenda_id:
            return False
        if not state.tournaments:
            return False
        latest = state.tournaments[-1]
        if latest.selected_candidate_id:
            return False
        if latest.agenda_id and latest.agenda_id != metrics.agenda_id:
            return False
        return any(agenda.id == metrics.agenda_id for agenda in state.agendas)

    def _artifact_paths(self, project: ResearchProject, metrics: IdeaYieldMetrics, yield_paths: list[Path]) -> dict[str, list[str]]:
        ideas_dir = Path(project.root_dir) / "ideas"
        reports_dir = ideas_dir / "reports"
        artifact_paths = {
            "v1_readiness": [str(self.release_dir / "v1_readiness_latest.json")],
            "topic_portfolios": [str(path) for path in sorted(ideas_dir.glob("topic-portfolio-*.json"))],
            "idea_bank": [str(ideas_dir / "idea_bank.json")],
            "idea_yield": [str(path) for path in yield_paths],
            "reports": [str(path) for path in sorted(reports_dir.glob("*.md"))],
        }
        if metrics.selected_idea_id:
            artifact_paths["selected_idea"] = [str(reports_dir / f"{metrics.selected_idea_id}.md")]
        if metrics.agenda_id:
            artifact_paths["agenda"] = [str(reports_dir / f"{metrics.agenda_id}.md")]
        return artifact_paths


def render_v2_release_gate_markdown(result: V2ReleaseGateResult) -> str:
    lines = [
        "# GapForge v2 Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Project: `{result.project_id or 'missing'}`",
        f"- Pilot: `{result.pilot_id or 'not resolved'}`",
        f"- Selected idea: `{result.selected_idea_id or 'none'}`",
        f"- Agenda: `{result.agenda_id or 'none'}`",
        f"- Idea yield rate: {result.idea_yield_rate:.4f}",
        "",
    ]
    if result.status == "warning_pass" or any("idea_discovery_incomplete" in warning for warning in result.warnings):
        lines.extend(
            [
                "## Release Note Requirement",
                "",
                "This is an agenda-only v2 gate pass. Release notes must state that idea discovery did not produce a "
                "human-accepted candidate idea and that v2.0.1 or v2.1 planning must address the blockers.",
                "",
            ]
        )
    lines.extend(["## Requirements", ""])
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Artifact Counts", ""])
    lines.extend(f"- `{name}`: {len(paths)}" for name, paths in sorted(result.artifact_paths.items()))
    return "\n".join(lines).rstrip() + "\n"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _human_accepted_idea_ids(state) -> set[str]:
    accepted = {feedback.idea_id for feedback in state.feedback_records if feedback.action == "accept"}
    accepted.update(review.idea_id for review in state.reviews if review.status == "accepted")
    return {idea_id for idea_id in accepted if idea_id}


def _claimed_paper_ids(candidate: IdeaCandidate) -> set[str]:
    return {
        paper_id
        for paper_id in [
            *candidate.closest_prior_work_ids,
            *candidate.supporting_paper_ids,
            *candidate.counterevidence_paper_ids,
        ]
        if paper_id
    }


def _has_fake_results(candidate: IdeaCandidate) -> bool:
    text = " ".join([candidate.title, candidate.summary, candidate.core_claim, candidate.proposed_experiment]).lower()
    return any(marker in text for marker in RESULT_CLAIM_MARKERS)


def _has_fatal_novelty_blocker(candidate: IdeaCandidate, state) -> bool:
    if candidate.novelty_status == "likely_duplicate" or candidate.maturity == "rejected":
        return True
    text = f"{candidate.rejection_reason} {candidate.summary} {candidate.likely_failure_mode}".lower()
    if any(marker in text for marker in ["fatal novelty", "fatal prior work", "already solves", "duplicate"]):
        return True
    latest = _latest_novelty(candidate.id, state)
    if latest is not None and latest.verdict == "reject":
        return True
    for tournament in state.tournaments:
        for record in tournament.score_records:
            if record.idea_id == candidate.id and any("fatal novelty" in blocker.lower() for blocker in record.blockers):
                return True
    return False


def _latest_novelty(idea_id: str, state) -> IdeaNoveltyAssessment | None:
    matches = [assessment for assessment in state.novelty_assessments if assessment.idea_id == idea_id]
    return matches[-1] if matches else None


def _rejected_ideas_preserved(state) -> bool:
    candidate_ids = {candidate.id for candidate in state.candidates}
    rejected_ids = set(state.idea_bank.rejected_candidate_ids if state.idea_bank is not None else [])
    mutation_source_ids = {record.source_idea_id for record in state.mutations}
    mutation_target_ids = {record.mutated_idea_id for record in state.mutations}
    return (rejected_ids | mutation_source_ids | mutation_target_ids).issubset(candidate_ids)


def _requirement_blockers(requirements: dict[str, bool], *, include_agenda: bool) -> list[str]:
    blockers: list[str] = []
    for name, passed in requirements.items():
        if passed:
            continue
        if name == "agenda_fallback_exists" and not include_agenda:
            continue
        blockers.append(f"Requirement failed: {name}")
    return blockers


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
