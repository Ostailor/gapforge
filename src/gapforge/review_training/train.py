"""Reviewer model/rubric training harness."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.review_training.baselines import reviewer_for_mode
from gapforge.review_training.openreview_dataset import ReviewDatasetBuilder
from gapforge.review_training.prompts import reviewer_task_pack_prompt
from gapforge.review_training.schemas import ReviewDatasetPaper
from gapforge.review_training.scoring import score_predictions
from gapforge.review_training.taxonomy import ReviewIssueLabel, ReviewTaxonomyLabeler
from gapforge.state import slugify, utc_now_iso

REVIEWER_TRAINING_MODES = {"heuristic", "retrieval_calibrated", "codex_task_pack", "local_model"}


@dataclass(slots=True)
class ReviewerTrainingRun:
    id: str
    dataset_id: str
    model_type: str
    train_split: list[str] = field(default_factory=list)
    eval_split: list[str] = field(default_factory=list)
    metrics: dict[str, float | str] = field(default_factory=dict)
    status: str = "planned"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="reviewer-train"))


class ReviewerTrainingManager:
    """Train or calibrate deterministic reviewer rubrics against review-taxonomy labels."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.datasets = ReviewDatasetBuilder(config)
        self.taxonomy = ReviewTaxonomyLabeler(config)

    def train(self, dataset_id: str, *, mode: str = "heuristic") -> ReviewerTrainingRun:
        if mode not in REVIEWER_TRAINING_MODES:
            allowed = ", ".join(sorted(REVIEWER_TRAINING_MODES))
            raise ValueError(f"Unsupported reviewer training mode `{mode}`. Expected one of: {allowed}")
        dataset = self.datasets.load(dataset_id)
        papers = self.datasets.list_papers(dataset_id)
        paper_ids = [paper.id for paper in papers]
        split_index = max(1, int(len(paper_ids) * 0.7)) if paper_ids else 0
        train_split = paper_ids[:split_index]
        eval_split = paper_ids[split_index:] or paper_ids
        run = ReviewerTrainingRun(
            id=_unique_run_id(self._runs_dir(dataset_id), dataset_id, mode),
            dataset_id=dataset_id,
            model_type=mode,
            train_split=train_split,
            eval_split=eval_split,
            status="planned",
            provenance=Provenance(
                created_by_skill="reviewer-train",
                source_ids=[dataset_id, mode],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Initialized reviewer calibration run. Outputs are benchmarked rubric behavior, not human reviewer equivalence."
                ),
            ),
        )
        if mode == "codex_task_pack":
            self._write_task_pack(run, papers)
            run.metrics = {"limitation": "task pack written; no live model required or executed in CI"}
            run.status = "planned"
        elif mode == "local_model":
            run.metrics = {"limitation": "optional local model dependencies are not configured; no model was trained"}
            run.status = "skipped"
        else:
            gold = self.taxonomy.list_labels(dataset_id)
            predicted = reviewer_for_mode(mode).predict(papers, model_id=run.id)
            self._write_predictions(run, predicted)
            metrics: dict[str, float | str] = dict(
                score_predictions(_filter_labels(gold, eval_split), _filter_labels(predicted, eval_split))
            )
            metrics["training_data_warning"] = "small_dataset" if dataset.paper_count < 10 else "none"
            metrics["human_equivalence_claim"] = "not_claimed"
            run.metrics = metrics
            run.status = "complete"
        self._write_run(run)
        return run

    def latest_run(self, dataset_id: str) -> ReviewerTrainingRun:
        runs = [
            from_dict(ReviewerTrainingRun, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._runs_dir(dataset_id).glob("reviewer-training-*.json"))
        ]
        if not runs:
            return self.train(dataset_id, mode="heuristic")
        return runs[-1]

    def load_predictions(self, run: ReviewerTrainingRun) -> list[ReviewIssueLabel]:
        path = self._run_dir(run.dataset_id, run.id) / "predicted_labels.json"
        if not path.exists():
            return []
        return [from_dict(ReviewIssueLabel, item) for item in json.loads(path.read_text(encoding="utf-8"))]

    def render_report(self, dataset_id: str) -> str:
        run = self.latest_run(dataset_id)
        lines = [
            f"# Reviewer Calibration Report `{dataset_id}`",
            "",
            f"- Run: `{run.id}`",
            f"- Mode: `{run.model_type}`",
            f"- Status: `{run.status}`",
            f"- Train split: {', '.join(run.train_split) or 'none'}",
            f"- Eval split: {', '.join(run.eval_split) or 'none'}",
            "",
            "## Boundary",
            "",
            "This harness benchmarks reviewer simulation behavior. It does not claim human reviewer equivalence.",
            "Reviewer outputs must not invent citations, results, datasets, or artifact claims.",
            "",
            "## Metrics",
            "",
        ]
        lines.extend(f"- `{key}`: {value}" for key, value in sorted(run.metrics.items()))
        report = "\n".join(lines).rstrip() + "\n"
        (self._dataset_dir(dataset_id) / "reviewer_calibration_report.md").write_text(report, encoding="utf-8")
        return report

    def _write_run(self, run: ReviewerTrainingRun) -> None:
        run_dir = self._run_dir(run.dataset_id, run.id)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "training_run.json").write_text(json.dumps(to_plain(run), indent=2) + "\n", encoding="utf-8")
        (self._runs_dir(run.dataset_id) / f"{run.id}.json").write_text(json.dumps(to_plain(run), indent=2) + "\n", encoding="utf-8")

    def _write_predictions(self, run: ReviewerTrainingRun, predicted: list[ReviewIssueLabel]) -> None:
        run_dir = self._run_dir(run.dataset_id, run.id)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "predicted_labels.json").write_text(json.dumps(to_plain(predicted), indent=2) + "\n", encoding="utf-8")

    def _write_task_pack(self, run: ReviewerTrainingRun, papers: list[ReviewDatasetPaper]) -> None:
        task_dir = self._run_dir(run.dataset_id, run.id) / "task_pack"
        task_dir.mkdir(parents=True, exist_ok=True)
        for paper in papers:
            task_dir.joinpath(f"{paper.id}.md").write_text(reviewer_task_pack_prompt(paper, mode=run.model_type), encoding="utf-8")

    def _dataset_dir(self, dataset_id: str) -> Path:
        path = self.config.data_dir / "review_training" / "datasets" / dataset_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _runs_dir(self, dataset_id: str) -> Path:
        path = self._dataset_dir(dataset_id) / "training_runs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _run_dir(self, dataset_id: str, run_id: str) -> Path:
        path = self._runs_dir(dataset_id) / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path


def reviewer_training_json(run: ReviewerTrainingRun) -> str:
    return json.dumps(to_plain(run), indent=2) + "\n"


def _filter_labels(labels: list[ReviewIssueLabel], paper_ids: list[str]) -> list[ReviewIssueLabel]:
    allowed = set(paper_ids)
    return [label for label in labels if label.paper_id in allowed]


def _unique_run_id(runs_dir: Path, dataset_id: str, mode: str) -> str:
    base = f"reviewer-training-{slugify(dataset_id)}-{slugify(mode)}"
    candidate = base
    suffix = 2
    while (runs_dir / f"{candidate}.json").exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
