"""Workspace-scoped benchmark registry and project-level suites."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gapforge.benchmarks.cards import (
    default_benchmark_card,
    is_fixture_benchmark,
    render_benchmark_card_markdown,
    render_benchmark_registry_markdown,
)
from gapforge.benchmarks.suites import render_benchmark_suite_status_markdown
from gapforge.benchmarks.tasks import default_benchmark_task
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import (
    BenchmarkCard,
    BenchmarkRecord,
    BenchmarkSuite,
    BenchmarkTask,
    DatasetRecord,
    Provenance,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso


class BenchmarkRegistry:
    """Register benchmarks and suites for experiment execution."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.project_manager = ProjectMemoryManager(config)

    def register_benchmark(
        self,
        *,
        workspace_id: str,
        name: str,
        description: str = "",
        domain: str = "",
        task_type: str = "custom",
        source_url: str = "",
        dataset_ids: list[str] | None = None,
        baseline_ids: list[str] | None = None,
        metric_ids: list[str] | None = None,
        license: str = "",
        expected_splits: list[str] | None = None,
        evaluation_protocol: str = "",
        leaderboard_url: str = "",
        paper_ids: list[str] | None = None,
        limitations: list[str] | None = None,
        safety_notes: list[str] | None = None,
    ) -> BenchmarkRecord:
        self.workspace_manager.load_workspace(workspace_id)
        datasets = dataset_ids or []
        baselines = baseline_ids or []
        metrics = metric_ids or []
        record = BenchmarkRecord(
            id=_unique_benchmark_id(self._benchmark_dir(workspace_id), name),
            name=name,
            description=description,
            domain=domain or _domain_from_datasets(self._dataset_records(workspace_id, datasets)),
            task_type=task_type,
            source_url=source_url,
            dataset_ids=datasets,
            baseline_ids=baselines,
            metric_ids=metrics,
            license=license,
            expected_splits=expected_splits or [],
            evaluation_protocol=evaluation_protocol,
            leaderboard_url=leaderboard_url,
            paper_ids=paper_ids or [],
            limitations=limitations or [],
            safety_notes=safety_notes or [],
            provenance=Provenance(
                created_by_skill="benchmark-registry",
                source_ids=[workspace_id, *datasets, *baselines, *metrics],
                timestamp=utc_now_iso(),
                reasoning_summary="Registered an explicit benchmark artifact. Registration does not imply benchmark readiness.",
            ),
        )
        if _fixture_from_datasets(self._dataset_records(workspace_id, datasets)):
            record.domain = record.domain or "fixture"
            if "Fixture benchmark: workflow validation only." not in record.limitations:
                record.limitations.append("Fixture benchmark: workflow validation only.")
        return self._persist_record(workspace_id, record)

    def list_benchmarks(self, workspace_id: str) -> list[BenchmarkRecord]:
        benchmark_dir = self._benchmark_dir(workspace_id)
        if not benchmark_dir.exists():
            return []
        return [
            from_dict(BenchmarkRecord, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(benchmark_dir.glob("benchmark-*.record.json"))
        ]

    def load_benchmark(self, benchmark_id: str) -> BenchmarkRecord:
        for project_dir in self.config.project_root.glob("*"):
            for path in (project_dir / "experiment_workspaces").glob("*/benchmarks/benchmark-*.record.json"):
                record = from_dict(BenchmarkRecord, json.loads(path.read_text(encoding="utf-8")))
                if record.id == benchmark_id:
                    return record
        raise FileNotFoundError(f"No benchmark registered with id {benchmark_id}")

    def render_card(self, benchmark_id: str) -> str:
        record = self.load_benchmark(benchmark_id)
        card = self._load_or_create_card(record)
        return render_benchmark_card_markdown(record, card)

    def readiness_blockers(self, workspace_id: str) -> list[str]:
        records = self.list_benchmarks(workspace_id)
        blockers: list[str] = []
        if not records:
            return ["No explicit benchmark records are registered for this experiment workspace."]
        dataset_ids = {record.id for record in self._all_dataset_records(workspace_id)}
        baseline_ids = {record.id for record in self._all_baseline_records(workspace_id)}
        metric_ids = {record.id for record in self._all_metric_records(workspace_id)}
        for record in records:
            blockers.extend(
                f"Benchmark `{record.id}` references missing dataset `{item}`." for item in record.dataset_ids if item not in dataset_ids
            )
            blockers.extend(
                f"Benchmark `{record.id}` references missing baseline `{item}`." for item in record.baseline_ids if item not in baseline_ids
            )
            blockers.extend(
                f"Benchmark `{record.id}` references missing metric `{item}`." for item in record.metric_ids if item not in metric_ids
            )
            card_path = self._card_path(_workspace_id_from_record(record), record.id)
            if not card_path.exists():
                blockers.append(f"Benchmark `{record.id}` is missing a benchmark card.")
            if not record.metric_ids:
                blockers.append(f"Benchmark `{record.id}` has no required metrics.")
            if not record.dataset_ids:
                blockers.append(f"Benchmark `{record.id}` has no linked datasets.")
        return blockers

    def create_suite(
        self,
        *,
        project_id: str,
        name: str,
        description: str = "",
        benchmark_ids: list[str] | None = None,
        required_tasks: list[str] | None = None,
        optional_tasks: list[str] | None = None,
        source_profile: str = "generic",
    ) -> BenchmarkSuite:
        program = self.project_manager.load_project(project_id)
        suites = list(program.benchmark_suites)
        suite = BenchmarkSuite(
            id=_unique_suite_id(Path(program.project.root_dir) / "benchmark_suites", name),
            name=name,
            description=description,
            benchmark_ids=benchmark_ids or [],
            required_tasks=required_tasks or [],
            optional_tasks=optional_tasks or [],
            source_profile=source_profile,
            provenance=Provenance(
                created_by_skill="benchmark-suite",
                source_ids=[project_id, *(benchmark_ids or [])],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a project-level benchmark suite.",
            ),
        )
        suites = [item for item in suites if item.id != suite.id]
        suites.append(suite)
        program.benchmark_suites = suites
        self.project_manager.save_project(program)
        self._write_suite_markdown(program.project.root_dir, suite)
        return suite

    def suite_status(self, suite_id: str) -> str:
        program = self._program_for_suite(suite_id)
        suite = next(item for item in program.benchmark_suites if item.id == suite_id)
        benchmarks = [self.load_benchmark(benchmark_id) for benchmark_id in suite.benchmark_ids if self._benchmark_exists(benchmark_id)]
        blockers = []
        for benchmark in benchmarks:
            blockers.extend(self.readiness_blockers(_workspace_id_from_record(benchmark)))
        rendered = render_benchmark_suite_status_markdown(suite, benchmarks, blockers)
        self._write_suite_markdown(program.project.root_dir, suite, rendered)
        return rendered

    def _persist_record(self, workspace_id: str, record: BenchmarkRecord) -> BenchmarkRecord:
        benchmark_dir = self._benchmark_dir(workspace_id)
        existing = next((item for item in self.list_benchmarks(workspace_id) if item.name.lower() == record.name.lower()), None)
        if existing is not None:
            record.id = existing.id
        (benchmark_dir / f"{record.id}.record.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        task = default_benchmark_task(record)
        self._write_task(workspace_id, task)
        card = default_benchmark_card(record, fixture_labeled=is_fixture_benchmark(record))
        self._write_card(workspace_id, record, card)
        self._write_registry_markdown(workspace_id)
        return record

    def _write_task(self, workspace_id: str, task: BenchmarkTask) -> None:
        tasks_dir = self._benchmark_dir(workspace_id) / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        (tasks_dir / f"{task.id}.task.json").write_text(json.dumps(to_plain(task), indent=2) + "\n", encoding="utf-8")

    def _write_card(self, workspace_id: str, record: BenchmarkRecord, card: BenchmarkCard) -> None:
        cards_dir = self._benchmark_dir(workspace_id) / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        (cards_dir / f"{record.id}.card.json").write_text(json.dumps(to_plain(card), indent=2) + "\n", encoding="utf-8")
        (cards_dir / f"{record.id}.card.md").write_text(render_benchmark_card_markdown(record, card), encoding="utf-8")

    def _load_or_create_card(self, record: BenchmarkRecord) -> BenchmarkCard:
        workspace_id = _workspace_id_from_record(record)
        card_path = self._card_path(workspace_id, record.id)
        if card_path.exists():
            return from_dict(BenchmarkCard, json.loads(card_path.read_text(encoding="utf-8")))
        card = default_benchmark_card(record, fixture_labeled=is_fixture_benchmark(record))
        self._write_card(workspace_id, record, card)
        return card

    def _write_registry_markdown(self, workspace_id: str) -> None:
        records = self.list_benchmarks(workspace_id)
        markdown = render_benchmark_registry_markdown(records)
        (self._benchmark_dir(workspace_id) / "benchmark_registry.md").write_text(markdown, encoding="utf-8")
        reports_dir = Path(self.workspace_manager.load_workspace(workspace_id).root_dir) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "benchmark_registry.md").write_text(markdown, encoding="utf-8")

    def _write_suite_markdown(self, project_root: str, suite: BenchmarkSuite, rendered: str = "") -> None:
        suites_dir = Path(project_root) / "benchmark_suites"
        suites_dir.mkdir(parents=True, exist_ok=True)
        if not rendered:
            rendered = render_benchmark_suite_status_markdown(suite, [], ["Suite status has not been refreshed."])
        (suites_dir / f"{suite.id}.md").write_text(rendered, encoding="utf-8")

    def _benchmark_dir(self, workspace_id: str) -> Path:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        benchmark_dir = Path(workspace.root_dir) / "benchmarks"
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        return benchmark_dir

    def _card_path(self, workspace_id: str, benchmark_id: str) -> Path:
        return self._benchmark_dir(workspace_id) / "cards" / f"{benchmark_id}.card.json"

    def _dataset_records(self, workspace_id: str, dataset_ids: list[str]) -> list[DatasetRecord]:
        records = self._all_dataset_records(workspace_id)
        return [record for record in records if record.id in set(dataset_ids)]

    def _all_dataset_records(self, workspace_id: str):
        from gapforge.datasets.registry import DatasetRegistry

        return DatasetRegistry(self.config).list_datasets(workspace_id)

    def _all_baseline_records(self, workspace_id: str):
        from gapforge.baselines.registry import BaselineRegistry

        return BaselineRegistry(self.config).list_baselines(workspace_id)

    def _all_metric_records(self, workspace_id: str):
        from gapforge.metrics.registry import MetricRegistry

        return MetricRegistry(self.config).list_metrics(workspace_id)

    def _program_for_suite(self, suite_id: str):
        for project in self.project_manager.list_projects():
            program = self.project_manager.load_project(project.id)
            if any(item.id == suite_id for item in program.benchmark_suites):
                return program
        raise FileNotFoundError(f"No benchmark suite found with id {suite_id}")

    def _benchmark_exists(self, benchmark_id: str) -> bool:
        try:
            self.load_benchmark(benchmark_id)
        except FileNotFoundError:
            return False
        return True


def _unique_benchmark_id(benchmark_dir: Path, name: str) -> str:
    base = f"benchmark-{slugify(name)}"
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (benchmark_dir / f"{candidate}.record.json").exists():
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate


def _unique_suite_id(suite_dir: Path, name: str) -> str:
    suite_dir.mkdir(parents=True, exist_ok=True)
    base = f"benchmark-suite-{slugify(name)}"
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (suite_dir / f"{candidate}.md").exists():
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate


def _workspace_id_from_record(record: BenchmarkRecord) -> str:
    return record.provenance.source_ids[0] if record.provenance.source_ids else ""


def _fixture_from_datasets(records: list[DatasetRecord]) -> bool:
    return any(record.dataset_type in {"fixture", "synthetic"} for record in records)


def _domain_from_datasets(records: list[DatasetRecord]) -> str:
    if _fixture_from_datasets(records):
        return "fixture"
    return ""
