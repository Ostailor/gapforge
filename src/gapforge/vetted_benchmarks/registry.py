"""Global vetted benchmark registry for real benchmark grounding."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso
from gapforge.vetted_benchmarks.cards import (
    VettedBenchmarkCard,
    default_vetted_benchmark_card,
    render_vetted_benchmark_card,
    render_vetted_benchmark_list,
)
from gapforge.vetted_benchmarks.eligibility import (
    BenchmarkEligibilityAssessment,
    assess_benchmark_eligibility,
    render_eligibility_assessment,
)
from gapforge.vetted_benchmarks.sources import (
    VettedBenchmarkRecord,
    normalize_benchmark_type,
    normalize_vetted_status,
    source_visibility_warnings,
)


class VettedBenchmarkRegistry:
    """Register existing benchmarks as auditable grounding options."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)

    def register(
        self,
        *,
        name: str,
        domain: str = "",
        source: str = "",
        source_url: str = "",
        benchmark_type: str = "unknown",
        task_types: list[str] | None = None,
        dataset_ids: list[str] | None = None,
        metric_ids: list[str] | None = None,
        baseline_ids: list[str] | None = None,
        paper_ids: list[str] | None = None,
        leaderboard_url: str = "",
        license: str = "",
        terms_of_use: str = "",
        download_required: bool = False,
        authentication_required: bool = False,
        size_estimate: str = "",
        citation: str = "",
        vetted_status: str = "uncertain",
        limitations: list[str] | None = None,
    ) -> VettedBenchmarkRecord:
        record = VettedBenchmarkRecord(
            id=_unique_vetted_benchmark_id(self._records_dir(), name),
            name=name,
            domain=domain,
            source=source,
            source_url=source_url,
            benchmark_type=normalize_benchmark_type(benchmark_type),
            task_types=task_types or [],
            dataset_ids=dataset_ids or [],
            metric_ids=metric_ids or [],
            baseline_ids=baseline_ids or [],
            paper_ids=paper_ids or [],
            leaderboard_url=leaderboard_url,
            license=license,
            terms_of_use=terms_of_use,
            download_required=download_required,
            authentication_required=authentication_required,
            size_estimate=size_estimate,
            citation=citation,
            vetted_status=normalize_vetted_status(vetted_status),
            limitations=limitations or [],
            provenance=Provenance(
                created_by_skill="vetted-benchmark-registry",
                source_ids=[source_url, leaderboard_url, *(paper_ids or [])],
                timestamp=utc_now_iso(),
                reasoning_summary="Registered an existing benchmark as an auditable grounding option; fit is assessed separately.",
            ),
        )
        return self._persist(record)

    def list(self) -> list[VettedBenchmarkRecord]:
        return [
            from_dict(VettedBenchmarkRecord, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._records_dir().glob("vetted-benchmark-*.record.json"))
        ]

    def load(self, benchmark_id: str) -> VettedBenchmarkRecord:
        path = self._records_dir() / f"{benchmark_id}.record.json"
        if path.exists():
            return from_dict(VettedBenchmarkRecord, json.loads(path.read_text(encoding="utf-8")))
        for record in self.list():
            if record.id == benchmark_id:
                return record
        raise FileNotFoundError(f"No vetted benchmark registered with id {benchmark_id}")

    def render_list(self) -> str:
        return render_vetted_benchmark_list(self.list())

    def render_card(self, benchmark_id: str) -> str:
        record = self.load(benchmark_id)
        card = self._load_or_create_card(record)
        return render_vetted_benchmark_card(record, card)

    def assess_eligibility(self, *, benchmark_id: str, selected_idea_id: str) -> BenchmarkEligibilityAssessment:
        record = self.load(benchmark_id)
        assessment = assess_benchmark_eligibility(record, selected_idea_id=selected_idea_id)
        self._write_eligibility(assessment)
        return assessment

    def render_eligibility(self, *, benchmark_id: str, selected_idea_id: str) -> str:
        return render_eligibility_assessment(self.assess_eligibility(benchmark_id=benchmark_id, selected_idea_id=selected_idea_id))

    def render_project_report(self, project_id: str) -> str:
        program = self.project_manager.load_project(project_id)
        records = self.list()
        selected_idea_id = _selected_idea_id(program)
        assessments = [self.assess_eligibility(benchmark_id=record.id, selected_idea_id=selected_idea_id) for record in records]
        markdown = render_vetted_benchmark_project_report(project_id, selected_idea_id, records, assessments)
        report_dir = Path(program.project.root_dir) / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "vetted_benchmark_report.md").write_text(markdown, encoding="utf-8")
        return markdown

    def _persist(self, record: VettedBenchmarkRecord) -> VettedBenchmarkRecord:
        existing = next((item for item in self.list() if item.name.lower() == record.name.lower()), None)
        if existing is not None:
            record.id = existing.id
        (self._records_dir() / f"{record.id}.record.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        self._write_card(record, default_vetted_benchmark_card(record))
        (self._root_dir() / "vetted_benchmark_registry.md").write_text(self.render_list(), encoding="utf-8")
        return record

    def _load_or_create_card(self, record: VettedBenchmarkRecord) -> VettedBenchmarkCard:
        path = self._cards_dir() / f"{record.id}.card.json"
        if path.exists():
            return from_dict(VettedBenchmarkCard, json.loads(path.read_text(encoding="utf-8")))
        card = default_vetted_benchmark_card(record)
        self._write_card(record, card)
        return card

    def _write_card(self, record: VettedBenchmarkRecord, card: VettedBenchmarkCard) -> None:
        self._cards_dir().mkdir(parents=True, exist_ok=True)
        (self._cards_dir() / f"{record.id}.card.json").write_text(json.dumps(to_plain(card), indent=2) + "\n", encoding="utf-8")
        (self._cards_dir() / f"{record.id}.card.md").write_text(render_vetted_benchmark_card(record, card), encoding="utf-8")

    def _write_eligibility(self, assessment: BenchmarkEligibilityAssessment) -> None:
        self._eligibility_dir().mkdir(parents=True, exist_ok=True)
        path = self._eligibility_dir() / f"{assessment.benchmark_id}.{slugify(assessment.selected_idea_id)}.eligibility.json"
        path.write_text(json.dumps(to_plain(assessment), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_eligibility_assessment(assessment), encoding="utf-8")

    def _root_dir(self) -> Path:
        root = self.config.data_dir / "vetted_benchmarks"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _records_dir(self) -> Path:
        path = self._root_dir() / "records"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _cards_dir(self) -> Path:
        path = self._root_dir() / "cards"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _eligibility_dir(self) -> Path:
        path = self._root_dir() / "eligibility"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_vetted_benchmark_project_report(
    project_id: str,
    selected_idea_id: str,
    records: list[VettedBenchmarkRecord],
    assessments: list[BenchmarkEligibilityAssessment],
) -> str:
    lines = [
        f"# Vetted Benchmark Grounding Report `{project_id}`",
        "",
        f"- Selected idea: `{selected_idea_id or 'unknown'}`",
        f"- Registered vetted benchmarks: {len(records)}",
        "",
        "## Grounding Rule",
        "",
        (
            "Vetted benchmark does not automatically mean good fit. Existing benchmarks can be primary, auxiliary, or "
            "sanity-check only. If no benchmark fits, preserve the synthetic benchmark as a protocol contribution."
        ),
        "",
    ]
    if not records:
        lines.extend(["## Registry", "", "No vetted benchmarks are registered."])
        return "\n".join(lines).rstrip() + "\n"

    by_id = {assessment.benchmark_id: assessment for assessment in assessments}
    for record in records:
        assessment = by_id.get(record.id)
        warnings = source_visibility_warnings(record)
        lines.extend(
            [
                f"## `{record.id}`",
                "",
                f"- Name: {record.name}",
                f"- Vetted status: `{record.vetted_status}`",
                f"- License: {record.license or 'unknown'}",
                f"- Terms of use: {record.terms_of_use or 'unknown'}",
                f"- Download required: {record.download_required}",
                f"- Authentication required: {record.authentication_required}",
                f"- Recommended use: `{assessment.recommended_use if assessment else 'not_assessed'}`",
                f"- Fit score: {assessment.fit_score if assessment else 'not assessed'}",
                "",
            ]
        )
        if warnings:
            lines.extend(["### Visibility Warnings", "", *[f"- {item}" for item in warnings], ""])
        if assessment and assessment.blockers:
            lines.extend(["### Blockers", "", *[f"- {item}" for item in assessment.blockers], ""])
    if assessments and all(item.recommended_use == "not_recommended" for item in assessments):
        lines.extend(
            [
                "## No Fit Outcome",
                "",
                (
                    "No registered vetted benchmark currently fits the selected idea. Preserve the synthetic benchmark as a "
                    "protocol contribution and use adapter work only after a better source is found."
                ),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _selected_idea_id(program: Any) -> str:
    ideas = getattr(program, "idea_bank", None)
    if ideas is not None:
        try:
            selected_candidate_id = ideas.selected_candidate_id
        except AttributeError:
            selected_candidate_id = ""
        if selected_candidate_id:
            return str(selected_candidate_id)
    # Selected-idea projects commonly carry the source idea in project metadata only on disk.
    project = getattr(program, "project", None)
    if project is not None:
        try:
            return str(project.id)
        except AttributeError:
            return ""
    return ""


def _unique_vetted_benchmark_id(records_dir: Path, name: str) -> str:
    base = f"vetted-benchmark-{slugify(name)}"
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (records_dir / f"{candidate}.record.json").exists():
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate
