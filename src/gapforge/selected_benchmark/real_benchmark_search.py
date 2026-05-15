"""Real public benchmark candidate search for selected benchmark grounding."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso

FIT_STATUSES = {"primary", "auxiliary", "sanity_check", "no_fit", "unknown"}
REAL_BENCHMARK_SEARCH_QUERIES = [
    "multi-agent benchmarks",
    "AI safety monitoring benchmarks",
    "anomaly detection benchmarks",
    "deception/collusion/covert-channel benchmarks",
    "LLM monitor-evasion benchmarks",
    "sequential detection benchmarks",
    "public datasets useful as sanity checks",
]


@dataclass(slots=True)
class RealBenchmarkCandidateSearch:
    id: str
    selected_benchmark_id: str
    search_queries: list[str] = field(default_factory=list)
    candidate_benchmark_ids: list[str] = field(default_factory=list)
    rejected_candidate_ids: list[str] = field(default_factory=list)
    no_fit_reason: str = ""
    status: str = "planned"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-real-benchmark-search"))


@dataclass(slots=True)
class RealBenchmarkCandidate:
    id: str
    name: str
    source_url: str
    benchmark_type: str
    domain: str
    task_type: str
    license: str
    dataset_access: str
    relevance_to_selected_benchmark: str
    fit_status: str = "unknown"
    fit_reason: str = ""
    adaptation_required: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-real-benchmark-search"))


class RealBenchmarkSearchManager:
    """Record real public benchmark candidates without downloading or forcing fit."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.projects = ProjectMemoryManager(config)
        self.benchmarks = SelectedBenchmarkManager(config)

    def search(
        self,
        benchmark_id: str,
        *,
        candidates: list[RealBenchmarkCandidate] | None = None,
    ) -> RealBenchmarkCandidateSearch:
        spec = self.benchmarks.load_spec(benchmark_id)
        normalized = [_normalize_candidate(candidate) for candidate in (candidates if candidates is not None else default_candidates())]
        relevant = [candidate for candidate in normalized if _candidate_matches_selected(candidate)]
        rejected = [candidate for candidate in normalized if candidate.fit_status == "no_fit" or not _candidate_matches_selected(candidate)]
        candidate_ids = [candidate.id for candidate in relevant if candidate.fit_status != "no_fit"]
        rejected_ids = [candidate.id for candidate in rejected if candidate.id not in candidate_ids]
        no_fit_reason = _no_fit_reason(relevant, rejected)
        status = "complete" if candidate_ids else "no_fit"
        search = RealBenchmarkCandidateSearch(
            id=f"real-benchmark-search-{slugify(benchmark_id)}",
            selected_benchmark_id=benchmark_id,
            search_queries=list(REAL_BENCHMARK_SEARCH_QUERIES),
            candidate_benchmark_ids=candidate_ids,
            rejected_candidate_ids=rejected_ids,
            no_fit_reason=no_fit_reason,
            status=status,
            provenance=Provenance(
                created_by_skill="selected-real-benchmark-search",
                source_ids=[benchmark_id, *[candidate.source_url for candidate in normalized]],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Recorded real public benchmark candidates as metadata only; no datasets were downloaded and no fit was claimed."
                ),
            ),
        )
        self._write_search(spec.project_id, search, normalized)
        return search

    def load_or_search(self, benchmark_id: str) -> RealBenchmarkCandidateSearch:
        spec = self.benchmarks.load_spec(benchmark_id)
        path = self._search_dir(spec.project_id) / "real_benchmark_candidate_search.json"
        if not path.exists():
            return self.search(benchmark_id)
        return from_dict(RealBenchmarkCandidateSearch, json.loads(path.read_text(encoding="utf-8")))

    def load_candidates(self, benchmark_id: str) -> list[RealBenchmarkCandidate]:
        spec = self.benchmarks.load_spec(benchmark_id)
        path = self._search_dir(spec.project_id) / "real_benchmark_candidates.json"
        if not path.exists():
            self.search(benchmark_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(RealBenchmarkCandidate, item) for item in raw]

    def render_candidates(self, benchmark_id: str) -> str:
        search = self.load_or_search(benchmark_id)
        candidates = self.load_candidates(benchmark_id)
        markdown = render_real_benchmark_candidates(search, candidates)
        spec = self.benchmarks.load_spec(benchmark_id)
        (self._search_dir(spec.project_id) / "real_benchmark_candidates.md").write_text(markdown, encoding="utf-8")
        return markdown

    def render_no_fit_report(self, benchmark_id: str) -> str:
        search = self.load_or_search(benchmark_id)
        candidates = self.load_candidates(benchmark_id)
        markdown = render_real_benchmark_no_fit_report(search, candidates)
        spec = self.benchmarks.load_spec(benchmark_id)
        (self._search_dir(spec.project_id) / "real_benchmark_no_fit_report.md").write_text(markdown, encoding="utf-8")
        return markdown

    def _write_search(
        self,
        project_id: str,
        search: RealBenchmarkCandidateSearch,
        candidates: list[RealBenchmarkCandidate],
    ) -> None:
        search_dir = self._search_dir(project_id)
        search_dir.mkdir(parents=True, exist_ok=True)
        (search_dir / "real_benchmark_candidate_search.json").write_text(json.dumps(to_plain(search), indent=2) + "\n", encoding="utf-8")
        (search_dir / "real_benchmark_candidate_search.md").write_text(render_real_benchmark_search(search), encoding="utf-8")
        (search_dir / "real_benchmark_candidates.json").write_text(
            json.dumps(to_plain(candidates), indent=2) + "\n",
            encoding="utf-8",
        )
        (search_dir / "real_benchmark_candidates.md").write_text(
            render_real_benchmark_candidates(search, candidates),
            encoding="utf-8",
        )
        (search_dir / "real_benchmark_no_fit_report.md").write_text(
            render_real_benchmark_no_fit_report(search, candidates),
            encoding="utf-8",
        )
        for candidate in candidates:
            (search_dir / f"{candidate.id}.json").write_text(json.dumps(to_plain(candidate), indent=2) + "\n", encoding="utf-8")

    def _search_dir(self, project_id: str) -> Path:
        program = self.projects.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "real_benchmark_search"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_real_benchmark_search(search: RealBenchmarkCandidateSearch) -> str:
    lines = [
        f"# Real Benchmark Candidate Search `{search.selected_benchmark_id}`",
        "",
        f"- Status: `{search.status}`",
        f"- Candidate benchmark IDs: {_fmt(search.candidate_benchmark_ids)}",
        f"- Rejected candidate IDs: {_fmt(search.rejected_candidate_ids)}",
        "",
        "## Search Queries",
        "",
        *[f"- {query}" for query in search.search_queries],
        "",
        "## No-Fit Boundary",
        "",
        search.no_fit_reason or "No no-fit reason recorded.",
        "",
        "## Rules",
        "",
        "- Candidate search is metadata-only and does not download datasets.",
        "- Candidate presence is not a fit claim; mapping assessment must pass before primary, auxiliary, or sanity-check use.",
        "- Source URL, license, and dataset access notes must be preserved before adapter work.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_real_benchmark_candidates(
    search: RealBenchmarkCandidateSearch,
    candidates: list[RealBenchmarkCandidate],
) -> str:
    by_id = {candidate.id: candidate for candidate in candidates}
    ordered_ids = [
        *search.candidate_benchmark_ids,
        *[item for item in search.rejected_candidate_ids if item not in search.candidate_benchmark_ids],
    ]
    ordered = [by_id[item] for item in ordered_ids if item in by_id]
    lines = [
        f"# Real Benchmark Candidates `{search.selected_benchmark_id}`",
        "",
        f"- Search status: `{search.status}`",
        f"- Candidates: {len(search.candidate_benchmark_ids)}",
        f"- Rejected/no-fit: {len(search.rejected_candidate_ids)}",
        "",
    ]
    for candidate in ordered:
        lines.extend(
            [
                f"## `{candidate.id}`",
                "",
                f"- Name: {candidate.name}",
                f"- Source: {candidate.source_url}",
                f"- Type: `{candidate.benchmark_type}`",
                f"- Domain: {candidate.domain}",
                f"- Task type: {candidate.task_type}",
                f"- License: {candidate.license or 'unknown'}",
                f"- Dataset access: {candidate.dataset_access or 'unknown'}",
                f"- Fit status: `{candidate.fit_status}`",
                f"- Fit reason: {candidate.fit_reason or 'Mapping assessment required before any fit claim.'}",
                "",
                "### Relevance",
                "",
                candidate.relevance_to_selected_benchmark or "No relevance note recorded.",
                "",
                "### Adaptation Required",
                "",
                *[f"- {item}" for item in (candidate.adaptation_required or ["No adaptation recorded."])],
                "",
                "### Limitations",
                "",
                *[f"- {item}" for item in (candidate.limitations or ["No limitations recorded."])],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_real_benchmark_no_fit_report(
    search: RealBenchmarkCandidateSearch,
    candidates: list[RealBenchmarkCandidate],
) -> str:
    unresolved = [candidate for candidate in candidates if candidate.id in search.candidate_benchmark_ids]
    rejected = [candidate for candidate in candidates if candidate.id in search.rejected_candidate_ids]
    lines = [
        f"# Real Benchmark No-Fit Report `{search.selected_benchmark_id}`",
        "",
        f"- Search status: `{search.status}`",
        "- Direct fit claimed: false",
        "",
        "## Reason",
        "",
        search.no_fit_reason or "No candidate has passed mapping assessment as a direct fit.",
        "",
        "## Candidate Evidence",
        "",
    ]
    if unresolved:
        lines.extend(
            [
                "The following public candidates may support auxiliary or sanity-check work after mapping assessment, but they are not "
                "accepted as direct validation here:",
                "",
            ]
        )
        lines.extend(f"- `{candidate.id}`: {candidate.fit_reason}" for candidate in unresolved)
    else:
        lines.append("No candidate survived the metadata search as potentially relevant.")
    lines.extend(["", "## Rejected Or No-Fit Candidates", ""])
    lines.extend([f"- `{candidate.id}`: {candidate.fit_reason or 'No fit.'}" for candidate in rejected] or ["- none"])
    lines.extend(
        [
            "",
            "## Manuscript Boundary",
            "",
            "- A no-fit outcome supports explaining why a new benchmark protocol is needed.",
            "- It does not validate synthetic results as real collusion evidence.",
            "- Any future adapter must keep source labels separate from synthetic selected-benchmark results.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def default_candidates() -> list[RealBenchmarkCandidate]:
    return [
        _candidate(
            id="real-benchmark-agentdojo",
            name="AgentDojo",
            source_url="https://github.com/ethz-spylab/agentdojo",
            benchmark_type="benchmark",
            domain="LLM agent security and prompt injection",
            task_type="tool-using agent prompt-injection attack and defense evaluation",
            license="MIT",
            dataset_access="Public GitHub repository and package; no automatic download by GapForge search.",
            relevance="Public benchmark for attacks and defenses on tool-using LLM agents; useful for monitor-evasion pressure.",
            adaptation=[
                "Map task/security outcomes into sequential trace windows before any low-FPR evaluation.",
                "Separate prompt-injection robustness evidence from collusion-specific claims.",
            ],
            limitations=[
                "Not a collusion benchmark.",
                "Does not directly measure multi-agent collusive coordination or low false-positive specificity.",
            ],
        ),
        _candidate(
            id="real-benchmark-agent-security-bench",
            name="Agent Security Bench (ASB)",
            source_url="https://github.com/agiresearch/ASB",
            benchmark_type="benchmark",
            domain="LLM agent attacks and defenses",
            task_type="agent security attack and defense scenarios",
            license="MIT",
            dataset_access="Public GitHub repository; dependencies and model runs require explicit user action.",
            relevance="Covers adversarial attacks and defenses for LLM-based agents across scenarios; candidate monitor-evasion substrate.",
            adaptation=[
                "Extract event traces and attack success labels into selected-benchmark format.",
                "Define benign negative windows separately before low-FPR claims.",
            ],
            limitations=[
                "Attack success rate is not the same as sequential specificity.",
                "No direct collusion/covert coordination task is recorded by this search.",
            ],
        ),
        _candidate(
            id="real-benchmark-injecagent",
            name="InjecAgent",
            source_url="https://github.com/uiuc-kang-lab/InjecAgent",
            benchmark_type="benchmark",
            domain="tool-integrated LLM agents",
            task_type="indirect prompt injection vulnerability evaluation",
            license="MIT",
            dataset_access="Public GitHub repository; external model outputs may require separate access.",
            relevance="Indirect prompt injection can sanity-check monitor-evasion and untrusted-context handling.",
            adaptation=[
                "Convert tool/user/attacker interactions into sequential observation units.",
                "Keep injection vulnerability labels separate from collusion labels.",
            ],
            limitations=[
                "Not a collusion or multi-party covert-channel benchmark.",
                "May support sanity-check evidence only unless mapping assessment justifies more.",
            ],
        ),
        _candidate(
            id="real-benchmark-agentbench",
            name="AgentBench",
            source_url="https://github.com/THUDM/AgentBench",
            benchmark_type="suite",
            domain="LLM agent evaluation",
            task_type="autonomous agent performance across interactive environments",
            license="Apache-2.0",
            dataset_access="Public GitHub repository; benchmark assets are not downloaded by search.",
            relevance="Provides public LLM-agent task substrate for trace-adapter plumbing and baseline sanity checks.",
            adaptation=[
                "Select tasks that produce repeated agent observations and actions.",
                "Add selected-benchmark monitor labels externally; do not infer collusion labels from AgentBench success.",
            ],
            limitations=[
                "Capability benchmark, not a safety/collusion benchmark.",
                "No inherent low-FPR or collusion ground truth.",
            ],
        ),
        _candidate(
            id="real-benchmark-numenta-nab",
            name="Numenta Anomaly Benchmark (NAB)",
            source_url="https://github.com/numenta/NAB",
            benchmark_type="benchmark",
            domain="streaming anomaly detection",
            task_type="real-time anomaly detection with labeled time-series windows",
            license="MIT",
            dataset_access="Public GitHub repository with benchmark data; no automatic download by search.",
            relevance="Sequential anomaly scoring can sanity-check low false-positive and online detection plumbing.",
            adaptation=[
                "Use only as anomaly-detection sanity check unless collusion traces are separately supplied.",
                "Translate time-series anomaly windows into false-alarm calibration tests.",
            ],
            limitations=[
                "Not an LLM, multi-agent, or collusion benchmark.",
                "Can support metric plumbing but not deployment validity for collusion audits.",
            ],
        ),
        _candidate(
            id="real-benchmark-machiavelli",
            name="MACHIAVELLI",
            source_url="https://github.com/aypan17/machiavelli",
            benchmark_type="benchmark",
            domain="text-agent ethical behavior and deception",
            task_type="text-game agent behavior and ethical trade-off evaluation",
            license="MIT",
            dataset_access=(
                "Repository is public; game data is separately downloaded from Google Drive and must not be fetched automatically."
            ),
            relevance="Deception and agent behavior metrics may provide auxiliary pressure for hidden-objective behavior.",
            adaptation=[
                "Review game-data access terms before adapter work.",
                "Map trajectories to selected-benchmark traces without treating ethical metrics as collusion labels.",
            ],
            limitations=[
                "Dataset access is separate from the repository.",
                "Deception/ethical trade-off evidence does not directly validate low-FPR collusion monitoring.",
            ],
        ),
        _candidate(
            id="real-benchmark-mlcommons-ailuminate",
            name="MLCommons AILuminate",
            source_url="https://mlcommons.org/ailuminate/",
            benchmark_type="suite",
            domain="AI safety and security",
            task_type="hazard-category safety and jailbreak benchmarking",
            license="Apache-2.0 for open tooling; prompt-set license varies by testing mode",
            dataset_access="Multiple access modes; official/online tests and prompt sets have separate terms.",
            relevance="Safety-monitoring taxonomy can inform auxiliary risk categories and no-fit justification.",
            adaptation=[
                "Preserve MLCommons benchmark/testing terms for each test mode.",
                "Use only as hazard or jailbreak auxiliary evidence unless a task-level mapping is approved.",
            ],
            limitations=[
                "Primarily general safety/jailbreak benchmarking, not multi-agent collusion.",
                "Prompt access and publication terms vary; adapter work must review terms first.",
            ],
        ),
    ]


def _candidate(
    *,
    id: str,
    name: str,
    source_url: str,
    benchmark_type: str,
    domain: str,
    task_type: str,
    license: str,
    dataset_access: str,
    relevance: str,
    adaptation: list[str],
    limitations: list[str],
) -> RealBenchmarkCandidate:
    return RealBenchmarkCandidate(
        id=id,
        name=name,
        source_url=source_url,
        benchmark_type=benchmark_type,
        domain=domain,
        task_type=task_type,
        license=license,
        dataset_access=dataset_access,
        relevance_to_selected_benchmark=relevance,
        fit_status="unknown",
        fit_reason="Potential real public benchmark candidate; mapping assessment is required before any fit claim.",
        adaptation_required=adaptation,
        limitations=limitations,
        provenance=Provenance(
            created_by_skill="selected-real-benchmark-search",
            source_ids=[source_url],
            timestamp=utc_now_iso(),
            reasoning_summary="Recorded public benchmark metadata from public source pages without downloading benchmark assets.",
        ),
    )


def _normalize_candidate(candidate: RealBenchmarkCandidate) -> RealBenchmarkCandidate:
    fit_status = candidate.fit_status if candidate.fit_status in FIT_STATUSES else "unknown"
    limitations = list(candidate.limitations)
    if fit_status in {"primary", "auxiliary", "sanity_check"}:
        limitations.append(f"Fit status `{fit_status}` was demoted to `unknown` until selected benchmark mapping assessment passes.")
        fit_status = "unknown"
    if not candidate.license or candidate.license.lower() in {"unknown", "not recorded"}:
        limitations.append("License warning: license is not recorded; adapter work is blocked until terms are reviewed.")
    if any(term in candidate.license.lower() for term in ["non-commercial", "restricted", "varies"]):
        limitations.append("License warning: license or prompt-set terms may restrict use; preserve terms before adapter work.")
    if any(term in candidate.dataset_access.lower() for term in ["google drive", "authentication", "official", "online", "separate"]):
        limitations.append("Access warning: dataset or official benchmark access requires explicit review and must not be auto-downloaded.")
    return RealBenchmarkCandidate(
        id=slugify(candidate.id) if not candidate.id.startswith("real-benchmark-") else candidate.id,
        name=candidate.name,
        source_url=candidate.source_url,
        benchmark_type=candidate.benchmark_type,
        domain=candidate.domain,
        task_type=candidate.task_type,
        license=candidate.license,
        dataset_access=candidate.dataset_access,
        relevance_to_selected_benchmark=candidate.relevance_to_selected_benchmark,
        fit_status=fit_status,
        fit_reason=candidate.fit_reason or "Mapping assessment required before any fit claim.",
        adaptation_required=list(candidate.adaptation_required),
        limitations=_dedupe(limitations),
        provenance=candidate.provenance,
    )


def _candidate_matches_selected(candidate: RealBenchmarkCandidate) -> bool:
    text = " ".join(
        [
            candidate.name,
            candidate.domain,
            candidate.task_type,
            candidate.relevance_to_selected_benchmark,
            " ".join(candidate.adaptation_required),
            " ".join(candidate.limitations),
        ]
    ).lower()
    positive_terms = [
        "agent",
        "multi-agent",
        "monitor",
        "safety",
        "anomaly",
        "deception",
        "collusion",
        "covert",
        "prompt injection",
        "sequential",
        "time-series",
        "false-positive",
        "jailbreak",
    ]
    return any(term in text for term in positive_terms)


def _no_fit_reason(relevant: list[RealBenchmarkCandidate], rejected: list[RealBenchmarkCandidate]) -> str:
    if not relevant:
        return (
            "No searched public benchmark candidate matched the selected benchmark metadata. A benchmark-no-fit outcome is justified "
            "until a source with multi-agent collusion, sequential monitoring, and low-FPR labels is found."
        )
    return (
        "Real public candidates were found, but none is treated as a direct fit by search alone. The selected benchmark still needs "
        "mapping assessment for primary, auxiliary, or sanity-check use; absent that assessment, the correct boundary is no direct fit. "
        f"Rejected/no-fit candidates considered: {len(rejected)}."
    )


def _fmt(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
