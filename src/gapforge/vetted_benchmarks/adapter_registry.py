"""Registry and runner for vetted benchmark adapters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.models import DatasetRecord, Provenance, from_dict, to_plain
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso
from gapforge.vetted_benchmarks.adapters import BenchmarkAdapter, normalize_adapter_type, render_benchmark_adapter_report
from gapforge.vetted_benchmarks.manifests import BenchmarkAdapterRun, render_adapter_run_section
from gapforge.vetted_benchmarks.registry import VettedBenchmarkRegistry
from gapforge.vetted_benchmarks.sources import VettedBenchmarkRecord, source_visibility_warnings
from gapforge.vetted_benchmarks.transforms import dataset_input_schema, trace_like_output_schema, transform_dataset_to_trace_units


class BenchmarkAdapterRegistry:
    """Create adapters that transparently reuse vetted benchmarks as substrates."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.dataset_registry = DatasetRegistry(config)
        self.selected_manager = SelectedBenchmarkManager(config)
        self.vetted_registry = VettedBenchmarkRegistry(config)

    def create_adapter(self, *, selected_benchmark_id: str, vetted_benchmark_id: str) -> BenchmarkAdapter:
        spec = self.selected_manager.load_spec(selected_benchmark_id)
        record = self.vetted_registry.load(vetted_benchmark_id)
        dataset = _load_first_dataset(self.dataset_registry, record)
        adapter = BenchmarkAdapter(
            id=_unique_adapter_id(self._adapters_dir(), selected_benchmark_id, vetted_benchmark_id),
            vetted_benchmark_id=record.id,
            selected_benchmark_id=spec.id,
            adapter_type=normalize_adapter_type(_adapter_type(record, dataset)),
            input_schema=dataset_input_schema(dataset) if dataset is not None else _record_input_schema(record),
            output_schema=trace_like_output_schema(),
            transformation_description=_transformation_description(record, dataset),
            limitations=_adapter_limitations(record, dataset),
            implementation_path="gapforge.vetted_benchmarks.transforms.transform_dataset_to_trace_units",
            provenance=Provenance(
                created_by_skill="benchmark-adapter-create",
                source_ids=[spec.id, record.id, *record.dataset_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a transparent adapter; vetted benchmark fit and adapted-data claims remain limited.",
            ),
        )
        self._write_adapter(adapter)
        return adapter

    def load_adapter(self, adapter_id: str) -> BenchmarkAdapter:
        path = self._adapters_dir() / f"{adapter_id}.adapter.json"
        if path.exists():
            return from_dict(BenchmarkAdapter, json.loads(path.read_text(encoding="utf-8")))
        for candidate in self._adapters_dir().glob("*.adapter.json"):
            adapter = from_dict(BenchmarkAdapter, json.loads(candidate.read_text(encoding="utf-8")))
            if adapter.id == adapter_id:
                return adapter
        raise FileNotFoundError(f"No benchmark adapter found with id {adapter_id}")

    def list_adapters(self, selected_benchmark_id: str = "") -> list[BenchmarkAdapter]:
        adapters = [
            from_dict(BenchmarkAdapter, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._adapters_dir().glob("*.adapter.json"))
        ]
        if selected_benchmark_id:
            return [adapter for adapter in adapters if adapter.selected_benchmark_id == selected_benchmark_id]
        return adapters

    def run_adapter(self, adapter_id: str) -> BenchmarkAdapterRun:
        adapter = self.load_adapter(adapter_id)
        record = self.vetted_registry.load(adapter.vetted_benchmark_id)
        dataset = _load_first_dataset(self.dataset_registry, record)
        run_id = _unique_run_id(self._runs_dir(), adapter.id)
        if dataset is None:
            run = BenchmarkAdapterRun(
                id=run_id,
                adapter_id=adapter.id,
                dataset_id="",
                status="failed",
                warnings=["Vetted benchmark has no registered dataset_id; adapter run cannot transform examples."],
                provenance=_run_provenance(adapter, record, []),
            )
            self._write_run(run, None)
            return run
        try:
            manifest, warnings = transform_dataset_to_trace_units(adapter=adapter, dataset=dataset, vetted_benchmark=record)
            output_dir = self._run_dir(run_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "adapted_trace_units.json"
            output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            run = BenchmarkAdapterRun(
                id=run_id,
                adapter_id=adapter.id,
                dataset_id=dataset.id,
                status="complete",
                output_dataset_id=f"adapted-{dataset.id}",
                warnings=warnings,
                provenance=_run_provenance(adapter, record, [dataset.id, str(output_path)]),
            )
            self._write_run(run, output_path)
            return run
        except Exception as exc:
            run = BenchmarkAdapterRun(
                id=run_id,
                adapter_id=adapter.id,
                dataset_id=dataset.id,
                status="failed",
                warnings=[f"Adapter transformation failed: {exc}"],
                provenance=_run_provenance(adapter, record, [dataset.id]),
            )
            self._write_run(run, None)
            return run

    def render_report(self, adapter_id: str) -> str:
        adapter = self.load_adapter(adapter_id)
        run_sections = []
        for run in self.list_runs(adapter.id):
            output_path = self._run_output_path(run.id)
            run_sections.append(render_adapter_run_section(run, output_path=str(output_path) if output_path.exists() else ""))
        markdown = render_benchmark_adapter_report(adapter, run_sections)
        (self._adapters_dir() / f"{adapter.id}.adapter.md").write_text(markdown, encoding="utf-8")
        return markdown

    def list_runs(self, adapter_id: str) -> list[BenchmarkAdapterRun]:
        runs = []
        for path in sorted(self._runs_dir().glob("*/run.json")):
            run = from_dict(BenchmarkAdapterRun, json.loads(path.read_text(encoding="utf-8")))
            if run.adapter_id == adapter_id:
                runs.append(run)
        return runs

    def adapter_output_path(self, run_id: str) -> Path:
        return self._run_output_path(run_id)

    def _write_adapter(self, adapter: BenchmarkAdapter) -> None:
        path = self._adapters_dir() / f"{adapter.id}.adapter.json"
        path.write_text(json.dumps(to_plain(adapter), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_benchmark_adapter_report(adapter, []), encoding="utf-8")

    def _write_run(self, run: BenchmarkAdapterRun, output_path: Path | None) -> None:
        run_dir = self._run_dir(run.id)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(json.dumps(to_plain(run), indent=2) + "\n", encoding="utf-8")
        rendered = render_adapter_run_section(run, output_path=str(output_path) if output_path else "")
        (run_dir / "run.md").write_text(rendered, encoding="utf-8")

    def _root_dir(self) -> Path:
        root = self.config.data_dir / "vetted_benchmarks"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _adapters_dir(self) -> Path:
        path = self._root_dir() / "adapters"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _runs_dir(self) -> Path:
        path = self._root_dir() / "adapter_runs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _run_dir(self, run_id: str) -> Path:
        return self._runs_dir() / run_id

    def _run_output_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "adapted_trace_units.json"


def _load_first_dataset(dataset_registry: DatasetRegistry, record: VettedBenchmarkRecord) -> DatasetRecord | None:
    if not record.dataset_ids:
        return None
    try:
        return dataset_registry.load_dataset(record.dataset_ids[0])
    except FileNotFoundError:
        return None


def _record_input_schema(record: VettedBenchmarkRecord) -> dict[str, Any]:
    return {
        "vetted_benchmark_id": record.id,
        "dataset_ids": record.dataset_ids,
        "task_types": record.task_types,
        "metrics": record.metric_ids,
        "local_dataset_available": False,
    }


def _adapter_type(record: VettedBenchmarkRecord, dataset: DatasetRecord | None) -> str:
    text = _record_text(record)
    if _has_all(text, ["collusion", "sequential"]) and _has_any(text, ["monitor", "audit", "trace"]):
        return "direct"
    if _has_any(text, ["trace", "trajectory", "conversation", "agent", "transcript"]):
        return "trace_conversion"
    if dataset is not None and _has_any(text, ["label", "classification", "specificity", "false positive", "anomaly"]):
        return "label_mapping"
    if _has_any(text, ["metric", "leaderboard", "baseline"]):
        return "metric_mapping"
    return "auxiliary"


def _transformation_description(record: VettedBenchmarkRecord, dataset: DatasetRecord | None) -> str:
    if dataset is None:
        return "No local dataset is registered yet; adapter records the intended trace-like output schema only."
    return (
        "Convert each vetted benchmark example into a trace-like single-window evaluation unit, preserve source labels and "
        "splits when columns are present, and record warnings when the conversion cannot preserve monitor/collusion meaning."
    )


def _adapter_limitations(record: VettedBenchmarkRecord, dataset: DatasetRecord | None) -> list[str]:
    limitations = [
        "Vetted benchmark status does not imply fit for sequential specificity or collusion-audit claims.",
        "Adapted data must not be called real collusion traces unless source labels explicitly describe real collusion traces.",
        "Original labels and splits must remain visible in all adapted outputs.",
    ]
    limitations.extend(record.limitations)
    limitations.extend(source_visibility_warnings(record))
    if dataset is None:
        limitations.append("No registered local dataset is available; adapter cannot run until a dataset_id resolves.")
    elif not dataset.license:
        limitations.append("Registered dataset license is missing even if the benchmark-level license is recorded.")
    return limitations


def _run_provenance(adapter: BenchmarkAdapter, record: VettedBenchmarkRecord, source_ids: list[str]) -> Provenance:
    return Provenance(
        created_by_skill="benchmark-adapter-run",
        source_ids=[adapter.id, record.id, *source_ids],
        timestamp=utc_now_iso(),
        reasoning_summary="Ran a vetted-benchmark adapter while preserving transformation warnings and adapted-data guardrails.",
    )


def _unique_adapter_id(adapters_dir: Path, selected_benchmark_id: str, vetted_benchmark_id: str) -> str:
    base = f"benchmark-adapter-{slugify(selected_benchmark_id)}-{slugify(vetted_benchmark_id)}"
    digest = hashlib.sha1(f"{selected_benchmark_id}:{vetted_benchmark_id}".encode()).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (adapters_dir / f"{candidate}.adapter.json").exists():
        existing = from_dict(BenchmarkAdapter, json.loads((adapters_dir / f"{candidate}.adapter.json").read_text(encoding="utf-8")))
        if existing.selected_benchmark_id == selected_benchmark_id and existing.vetted_benchmark_id == vetted_benchmark_id:
            return candidate
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate


def _unique_run_id(runs_dir: Path, adapter_id: str) -> str:
    base = f"benchmark-adapter-run-{slugify(adapter_id)}"
    digest = hashlib.sha1(f"{adapter_id}:{utc_now_iso()}".encode()).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (runs_dir / candidate).exists():
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate


def _record_text(record: VettedBenchmarkRecord) -> str:
    return " ".join(
        [
            record.name,
            record.domain,
            record.source,
            record.benchmark_type,
            " ".join(record.task_types),
            " ".join(record.metric_ids),
            " ".join(record.baseline_ids),
            " ".join(record.limitations),
        ]
    ).lower()


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)
