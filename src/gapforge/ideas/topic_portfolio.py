"""Deterministic v2 topic portfolio generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas.store import IdeaStore
from gapforge.models import ProjectMemoryRecord, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso

TRANSFORMATION_TYPES = {
    "narrower",
    "broader",
    "adjacent",
    "cross_domain",
    "metric_shift",
    "threat_model_shift",
    "benchmark_shift",
    "theory_shift",
    "evaluation_shift",
    "data_shift",
}


@dataclass(slots=True)
class TopicVariant:
    id: str
    portfolio_id: str
    text: str
    transformation_type: str
    rationale: str
    expected_search_queries: list[str] = field(default_factory=list)
    likely_contribution_types: list[str] = field(default_factory=list)
    promise: str = ""
    risk: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="topic-portfolio"))


@dataclass(slots=True)
class TopicPortfolio:
    id: str
    project_id: str
    root_topic: str
    topic_variants: list[TopicVariant] = field(default_factory=list)
    adjacent_topics: list[str] = field(default_factory=list)
    cross_domain_topics: list[str] = field(default_factory=list)
    high_risk_high_reward_topics: list[str] = field(default_factory=list)
    measurement_topics: list[str] = field(default_factory=list)
    benchmark_topics: list[str] = field(default_factory=list)
    negative_result_topics: list[str] = field(default_factory=list)
    theory_topics: list[str] = field(default_factory=list)
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="topic-portfolio"))


class TopicPortfolioGenerator:
    """Generate, persist, and report diverse topic variants for v2 idea search."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.idea_store = IdeaStore(config)

    def generate(self, *, root_topic: str = "", project_id: str = "") -> TopicPortfolio:
        if project_id:
            program = self.project_manager.load_project(project_id)
            resolved_topic = root_topic or self._root_topic_for_project(project_id, program.project.name)
        else:
            if not root_topic:
                raise ValueError("topic-portfolio requires a root topic or --project-id.")
            program = self.project_manager.create_project(f"Topic Portfolio: {root_topic}")
            project_id = program.project.id
            resolved_topic = root_topic
        now = utc_now_iso()
        portfolio_id = _stable_id("topic-portfolio", project_id, resolved_topic)
        refusals = self._prior_refusals(project_id)
        variants = _generate_variants(portfolio_id, project_id, resolved_topic, refusals, now)
        portfolio = TopicPortfolio(
            id=portfolio_id,
            project_id=project_id,
            root_topic=resolved_topic,
            topic_variants=variants,
            adjacent_topics=[variant.text for variant in variants if variant.transformation_type == "adjacent"],
            cross_domain_topics=[variant.text for variant in variants if variant.transformation_type == "cross_domain"],
            high_risk_high_reward_topics=[
                variant.text for variant in variants if variant.transformation_type in {"threat_model_shift", "theory_shift"}
            ],
            measurement_topics=[
                variant.text for variant in variants if variant.transformation_type in {"metric_shift", "evaluation_shift", "data_shift"}
            ],
            benchmark_topics=[variant.text for variant in variants if variant.transformation_type == "benchmark_shift"],
            negative_result_topics=[variant.text for variant in variants if "negative result" in variant.text.lower()],
            theory_topics=[variant.text for variant in variants if variant.transformation_type == "theory_shift"],
            created_at=now,
            provenance=Provenance(
                created_by_skill="topic-portfolio",
                source_ids=[project_id, *[record.id for record in refusals]],
                timestamp=now,
                reasoning_summary=(
                    "Generated a diverse topic portfolio for idea discovery. Variants are campaign and idea-generation inputs, not claims."
                ),
            ),
        )
        self._write_portfolio(portfolio)
        return portfolio

    def load(self, portfolio_id: str) -> TopicPortfolio:
        for project in self.project_manager.list_projects():
            path = self._portfolio_path(project.id, portfolio_id)
            if path.exists():
                return from_dict(TopicPortfolio, json.loads(path.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"No topic portfolio found for {portfolio_id}")

    def write_report(self, portfolio_id: str) -> str:
        portfolio = self.load(portfolio_id)
        report = render_topic_portfolio_markdown(portfolio)
        reports_dir = self._ideas_dir(portfolio.project_id) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{portfolio.id}.md").write_text(report, encoding="utf-8")
        return report

    def _write_portfolio(self, portfolio: TopicPortfolio) -> None:
        ideas_dir = self._ideas_dir(portfolio.project_id)
        portfolios = [item for item in self.list_project_portfolios(portfolio.project_id) if item.id != portfolio.id]
        portfolios.append(portfolio)
        (ideas_dir / "topic_portfolios.json").write_text(json.dumps(to_plain(portfolios), indent=2) + "\n", encoding="utf-8")
        (ideas_dir / f"{portfolio.id}.json").write_text(json.dumps(to_plain(portfolio), indent=2) + "\n", encoding="utf-8")
        reports_dir = ideas_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{portfolio.id}.md").write_text(render_topic_portfolio_markdown(portfolio), encoding="utf-8")

    def list_project_portfolios(self, project_id: str) -> list[TopicPortfolio]:
        path = self._ideas_dir(project_id) / "topic_portfolios.json"
        if not path.exists():
            return []
        return [from_dict(TopicPortfolio, item) for item in json.loads(path.read_text(encoding="utf-8"))]

    def _root_topic_for_project(self, project_id: str, fallback: str) -> str:
        state = self.idea_store.load_state(project_id)
        if state.idea_bank is not None and state.idea_bank.root_topic:
            return state.idea_bank.root_topic
        program = self.project_manager.load_project(project_id)
        active_topic = next((topic.text for topic in program.topics if topic.status == "active"), "")
        return active_topic or fallback

    def _prior_refusals(self, project_id: str) -> list[ProjectMemoryRecord]:
        program = self.project_manager.load_project(project_id)
        memory_refusals = [
            record for record in program.memory_records if record.status == "rejected" or record.record_type in {"rejected_idea", "refusal"}
        ]
        state = self.idea_store.load_state(project_id)
        candidate_refusals = [
            ProjectMemoryRecord(
                id=f"idea-refusal-{candidate.id}",
                project_id=project_id,
                record_type="rejected_idea",
                text=f"{candidate.title} | Reason: {candidate.rejection_reason}",
                linked_object_ids=[candidate.id],
                status="rejected",
                confidence="medium",
                updated_at=utc_now_iso(),
                provenance=Provenance(
                    created_by_skill="topic-portfolio",
                    source_ids=[candidate.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Read rejected idea candidate as prior refusal context for portfolio generation.",
                ),
            )
            for candidate in state.candidates
            if candidate.maturity == "rejected" or candidate.rejection_reason
        ]
        return memory_refusals + candidate_refusals

    def _portfolio_path(self, project_id: str, portfolio_id: str) -> Path:
        return self._ideas_dir(project_id) / f"{portfolio_id}.json"

    def _ideas_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        ideas_dir = Path(program.project.root_dir) / "ideas"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        (ideas_dir / "reports").mkdir(parents=True, exist_ok=True)
        return ideas_dir


def render_topic_portfolio_markdown(portfolio: TopicPortfolio) -> str:
    lines = [
        f"# Topic Portfolio `{portfolio.id}`",
        "",
        f"- Project ID: `{portfolio.project_id}`",
        f"- Root topic: {portfolio.root_topic}",
        f"- Variants: {len(portfolio.topic_variants)}",
        "",
        "These variants are inputs to campaigns and idea generation. "
        "They do not establish prior-work status, evidence strength, or paper readiness.",
        "",
        "## Variants",
        "",
    ]
    for variant in portfolio.topic_variants:
        lines.extend(
            [
                f"### `{variant.id}`",
                "",
                f"- Type: `{variant.transformation_type}`",
                f"- Topic: {variant.text}",
                f"- Why it may produce a paper: {variant.promise}",
                f"- Why it may fail: {variant.risk}",
                f"- Rationale: {variant.rationale}",
                "- Search queries:",
                *[f"  - {query}" for query in variant.expected_search_queries],
                f"- Likely contribution types: {', '.join(variant.likely_contribution_types) or 'unknown'}",
                "",
            ]
        )
    lines.extend(["## Buckets", ""])
    buckets = [
        ("Adjacent topics", portfolio.adjacent_topics),
        ("Cross-domain topics", portfolio.cross_domain_topics),
        ("High-risk/high-reward topics", portfolio.high_risk_high_reward_topics),
        ("Measurement topics", portfolio.measurement_topics),
        ("Benchmark topics", portfolio.benchmark_topics),
        ("Negative-result topics", portfolio.negative_result_topics),
        ("Theory topics", portfolio.theory_topics),
    ]
    for title, items in buckets:
        lines.extend([f"### {title}", ""])
        lines.extend([f"- {item}" for item in items] if items else ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _generate_variants(
    portfolio_id: str,
    project_id: str,
    root_topic: str,
    refusals: list[ProjectMemoryRecord],
    timestamp: str,
) -> list[TopicVariant]:
    refusal_note = _refusal_note(refusals)
    specs = [
        (
            "narrower",
            "Low false-positive auditing for collusion detection in LLM multi-agent systems",
            "Narrow the root topic around auditability and false-alarm control.",
            ["measurement", "evaluation_protocol"],
            "A tight audit frame can produce measurable criteria, reviewer-readable error cases, and concrete failure analysis.",
            "May fail if prior monitors already report specificity or if benign-agent datasets are unavailable.",
            [
                f'"{root_topic}" "false positive"',
                '"LLM multi-agent" collusion detection specificity',
                '"multi-agent systems" monitor false alarms',
            ],
        ),
        (
            "adjacent",
            "Monitor evasion and covert channels in multi-agent LLM communication",
            "Move from collusion labels to the adjacent mechanism of hidden communication and monitor evasion.",
            ["measurement", "method", "negative_result"],
            "Mechanism-focused variants can expose concrete behaviors that broad collusion framing misses.",
            "May fail if the topic becomes dual-use, too security-general, or lacks benign comparison traces.",
            [
                '"LLM agents" "covert channels"',
                '"monitor evasion" "multi-agent"',
                '"multi-agent communication" hidden signals',
            ],
        ),
        (
            "cross_domain",
            "Medical-test specificity analogies for low false-positive LLM agent monitors",
            "Borrow diagnostic-test framing from medicine to reason about specificity, screening cost, and base rates.",
            ["measurement", "evaluation_protocol"],
            "Specificity and base-rate framing can clarify why low false-positive claims need different evidence.",
            "May fail if the analogy is only vocabulary and does not change metrics, sampling, or decision thresholds.",
            [
                '"medical test specificity" false positive screening',
                '"diagnostic specificity" "false positive rate"',
                '"base rate" "screening" false positives',
            ],
        ),
        (
            "cross_domain",
            "Cartel detection analogies for coordinated behavior among LLM agents",
            "Use antitrust and cartel-screening analogies to identify coordination patterns and false accusation risks.",
            ["measurement", "theory", "survey"],
            "Cartel screening has mature ideas around collusion evidence, benign parallel behavior, and enforcement thresholds.",
            "May fail if economic settings do not transfer to language-agent traces or if definitions diverge too far.",
            [
                '"cartel detection" screening false positives',
                '"collusion detection" economics "false positive"',
                '"parallel conduct" cartel detection evidence',
            ],
        ),
        (
            "metric_shift",
            "Sequential testing protocols for low false-positive collusion monitors",
            "Shift from one-shot detection to sequential evidence accumulation and stopping rules.",
            ["evaluation_protocol", "method", "measurement"],
            "Sequential tests can make false-alarm budgets explicit and may fit long-running agent interactions.",
            "May fail if interaction traces are too short or if assumptions behind sequential tests are not defensible.",
            [
                '"sequential testing" "false positive rate"',
                '"sequential probability ratio test" anomaly detection',
                '"LLM agents" sequential monitoring',
            ],
        ),
        (
            "threat_model_shift",
            "Threat models for monitor evasion by colluding LLM agents",
            "Change the threat model from accidental coordination to agents adapting communication under observation.",
            ["theory", "system", "negative_result"],
            "A threat-model contribution can organize what monitor evaluations must defend against.",
            "May fail if the assumptions are too speculative or cannot be grounded in observable interaction logs.",
            [
                '"monitor evasion" "LLM agents"',
                '"threat model" "multi-agent" "LLM"',
                '"colluding agents" "monitor"',
            ],
        ),
        (
            "benchmark_shift",
            "Benchmark construction for benign versus collusive multi-agent communication",
            "Turn the broad topic into a dataset and benchmark design problem with explicit benign negatives.",
            ["benchmark", "dataset", "evaluation_protocol"],
            "A benchmark can make false positives inspectable by requiring benign parallel behavior and adversarial coordination cases.",
            "May fail if realistic labels are unavailable, expensive, or ethically difficult to construct.",
            [
                '"LLM multi-agent" benchmark collusion',
                '"agent communication" benchmark benign adversarial',
                '"collusion detection" benchmark dataset',
            ],
        ),
        (
            "theory_shift",
            "Formal limits of distinguishing collusion from benign coordination in language agents",
            "Ask when observed communication is insufficient to separate collusion from benign coordination.",
            ["theory", "negative_result"],
            "A limits result can be useful when existing monitors overstate what traces can prove.",
            "May fail if the formalization is too abstract or disconnected from real agent systems.",
            [
                '"collusion" "benign coordination" detection limits',
                '"impossibility" anomaly detection false positives',
                '"multi-agent" communication distinguishability',
            ],
        ),
        (
            "evaluation_shift",
            "Negative results for existing LLM multi-agent collusion monitors under low false-positive requirements",
            "Evaluate whether current monitors fail when specificity and benign-stress tests are prioritized.",
            ["negative_result", "replication", "measurement"],
            "Negative results can be defensible if they are careful, artifact-backed, and expose a real evaluation gap.",
            "May fail if baselines are unavailable, too weak, or already evaluated under similar conditions.",
            [
                '"LLM collusion monitor" evaluation',
                '"multi-agent" "false positive" monitor',
                '"LLM agents" anomaly detection false positives',
            ],
        ),
        (
            "data_shift",
            "Benign multi-agent communication corpora for false-positive stress testing",
            "Shift toward collecting or curating benign interaction traces that should not trigger collusion monitors.",
            ["dataset", "benchmark", "measurement"],
            "A negative-class corpus can unlock more credible evaluation of low false-positive claims.",
            "May fail if traces are synthetic-only, privacy-sensitive, or not representative of deployment settings.",
            [
                '"multi-agent communication" dataset',
                '"LLM agents" benign conversations dataset',
                '"false positive" stress test dataset',
            ],
        ),
        (
            "broader",
            "Low false-positive anomaly detection for monitored LLM agent ecosystems",
            "Broaden from collusion to anomaly detection in monitored agent ecosystems while preserving false-positive emphasis.",
            ["survey", "tooling", "measurement"],
            "The broader frame can reveal adjacent sources, baselines, and metrics before narrowing again.",
            "May fail by becoming too generic unless it feeds back into specific candidate generation.",
            [
                '"LLM agents" anomaly detection',
                '"agent monitoring" "false positive"',
                '"AI agent" monitoring evaluation',
            ],
        ),
    ]
    variants: list[TopicVariant] = []
    seen_texts: set[str] = set()
    for transformation_type, text, rationale, contribution_types, promise, risk, queries in specs:
        if text.lower() in seen_texts:
            continue
        seen_texts.add(text.lower())
        variant_id = _variant_id(portfolio_id, transformation_type, text)
        variants.append(
            TopicVariant(
                id=variant_id,
                portfolio_id=portfolio_id,
                text=text,
                transformation_type=_validate_transformation_type(transformation_type),
                rationale=f"{rationale}{refusal_note}",
                expected_search_queries=queries,
                likely_contribution_types=contribution_types,
                promise=promise,
                risk=f"{risk}{refusal_note}",
                provenance=Provenance(
                    created_by_skill="topic-portfolio",
                    source_ids=[project_id, *[record.id for record in refusals]],
                    timestamp=timestamp,
                    reasoning_summary="Generated deterministic, diverse topic variant for v2 idea discovery.",
                ),
            )
        )
    return variants


def _refusal_note(refusals: list[ProjectMemoryRecord]) -> str:
    if not refusals:
        return ""
    summaries = [record.text.split("| Reason:", 1)[-1].strip() for record in refusals[:3] if record.text]
    joined = "; ".join(summaries) or "prior refusal exists"
    return f" Prior refusal context to avoid or repair: {joined}."


def _validate_transformation_type(value: str) -> str:
    if value not in TRANSFORMATION_TYPES:
        raise ValueError(f"Unsupported transformation type: {value}. Expected one of: {', '.join(sorted(TRANSFORMATION_TYPES))}")
    return value


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "::".join(parts)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8]
    readable = slugify(parts[-1])[:48] or "untitled"
    return f"{prefix}-{readable}-{digest}"


def _variant_id(portfolio_id: str, transformation_type: str, text: str) -> str:
    digest = hashlib.sha1(f"{portfolio_id}::{transformation_type}::{text}".encode()).hexdigest()[:8]
    return f"topic-{transformation_type}-{slugify(text)[:40]}-{digest}"
