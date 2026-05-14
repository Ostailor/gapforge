"""OpenReview-style review dataset builder."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.review_training.ingest import SYNTHETIC_OPENREVIEW_FIXTURE, guarded_openreview_ingest_warning, parse_fixture_paper
from gapforge.review_training.labels import LABEL_SCHEMA
from gapforge.review_training.schemas import ReviewDataset, ReviewDatasetPaper, ReviewRecord
from gapforge.state import slugify, utc_now_iso


class ReviewDatasetBuilder:
    """Build public, auditable review calibration datasets."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()

    def create(self, name: str, *, source: str = "manual") -> ReviewDataset:
        dataset = ReviewDataset(
            id=_unique_dataset_id(self._datasets_dir(), name),
            name=name,
            source=source,
            label_schema=LABEL_SCHEMA,
            license_warnings=[
                "Dataset is empty until an allowed public source or synthetic fixture is ingested.",
                "Do not store hidden/private reviews or unhashed reviewer identifiers.",
            ],
            provenance=Provenance(
                created_by_skill="review-dataset-create",
                source_ids=[name, source],
                timestamp=utc_now_iso(),
                reasoning_summary="Created an auditable review calibration dataset shell.",
            ),
        )
        self._write_dataset(dataset)
        return dataset

    def ingest_openreview(self, *, venue: str, year: int) -> ReviewDataset:
        name = f"openreview_{slugify(venue)}_{year}"
        dataset = ReviewDataset(
            id=_unique_dataset_id(self._datasets_dir(), name),
            name=name,
            source="openreview",
            venue_years=[f"{venue} {year}"],
            label_schema=LABEL_SCHEMA,
            license_warnings=[guarded_openreview_ingest_warning(venue, year)],
            provenance=Provenance(
                created_by_skill="review-dataset-ingest",
                source_ids=["openreview", venue, str(year)],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Recorded guarded OpenReview ingestion request without downloading data because source terms/privacy were not verified."
                ),
            ),
        )
        self._write_dataset(dataset)
        self._write_report(dataset.id)
        return dataset

    def ingest_fixture(self) -> ReviewDataset:
        dataset = ReviewDataset(
            id=_unique_dataset_id(self._datasets_dir(), "openreview_like_fixture"),
            name="openreview_like_fixture",
            source="synthetic_fixture",
            venue_years=["FixtureReview 2024"],
            label_schema=LABEL_SCHEMA,
            license_warnings=["Synthetic CI fixture only; no real reviewer data or private OpenReview data is stored."],
            provenance=Provenance(
                created_by_skill="review-dataset-ingest-fixture",
                source_ids=["synthetic-openreview-fixture"],
                timestamp=utc_now_iso(),
                reasoning_summary="Ingested synthetic OpenReview-style fixture data for reviewer calibration tests.",
            ),
        )
        papers: list[ReviewDatasetPaper] = []
        reviews: list[ReviewRecord] = []
        for raw_paper in SYNTHETIC_OPENREVIEW_FIXTURE:
            paper, paper_reviews = parse_fixture_paper(raw_paper, dataset_id=dataset.id)
            papers.append(paper)
            reviews.extend(paper_reviews)
        dataset.paper_count = len(papers)
        dataset.review_count = len(reviews)
        self._write_dataset(dataset)
        for paper in papers:
            self._write_paper(dataset.id, paper)
        for review in reviews:
            self._write_review(dataset.id, review)
        self._write_report(dataset.id)
        return dataset

    def load(self, dataset_id: str) -> ReviewDataset:
        path = self._dataset_dir(dataset_id) / "dataset.json"
        if not path.exists():
            raise FileNotFoundError(f"No review dataset found with id {dataset_id}")
        return from_dict(ReviewDataset, json.loads(path.read_text(encoding="utf-8")))

    def list_papers(self, dataset_id: str) -> list[ReviewDatasetPaper]:
        return [
            from_dict(ReviewDatasetPaper, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted((self._dataset_dir(dataset_id) / "papers").glob("*.json"))
        ]

    def list_reviews(self, dataset_id: str) -> list[ReviewRecord]:
        return [
            from_dict(ReviewRecord, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted((self._dataset_dir(dataset_id) / "reviews").glob("*.json"))
        ]

    def render_report(self, dataset_id: str) -> str:
        return self._write_report(dataset_id)

    def _write_dataset(self, dataset: ReviewDataset) -> None:
        dataset_dir = self._dataset_dir(dataset.id)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        (dataset_dir / "dataset.json").write_text(json.dumps(to_plain(dataset), indent=2) + "\n", encoding="utf-8")

    def _write_paper(self, dataset_id: str, paper: ReviewDatasetPaper) -> None:
        papers_dir = self._dataset_dir(dataset_id) / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)
        (papers_dir / f"{paper.id}.json").write_text(json.dumps(to_plain(paper), indent=2) + "\n", encoding="utf-8")

    def _write_review(self, dataset_id: str, review: ReviewRecord) -> None:
        reviews_dir = self._dataset_dir(dataset_id) / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / f"{review.id}.json").write_text(json.dumps(to_plain(review), indent=2) + "\n", encoding="utf-8")

    def _write_report(self, dataset_id: str) -> str:
        dataset = self.load(dataset_id)
        papers = self.list_papers(dataset_id)
        reviews = self.list_reviews(dataset_id)
        report = render_review_dataset_report(dataset, papers, reviews)
        (self._dataset_dir(dataset_id) / "review_dataset_report.md").write_text(report, encoding="utf-8")
        return report

    def _root_dir(self) -> Path:
        path = self.config.data_dir / "review_training"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _datasets_dir(self) -> Path:
        path = self._root_dir() / "datasets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _dataset_dir(self, dataset_id: str) -> Path:
        path = self._datasets_dir() / dataset_id
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_review_dataset_report(
    dataset: ReviewDataset,
    papers: list[ReviewDatasetPaper],
    reviews: list[ReviewRecord],
) -> str:
    weakness_count = sum(len(review.weaknesses) for review in reviews)
    strength_count = sum(len(review.strengths) for review in reviews)
    lines = [
        f"# Review Dataset `{dataset.id}`",
        "",
        f"- Name: {dataset.name}",
        f"- Source: `{dataset.source}`",
        f"- Venue years: {', '.join(dataset.venue_years) if dataset.venue_years else 'none'}",
        f"- Papers: {dataset.paper_count}",
        f"- Reviews: {dataset.review_count}",
        f"- Strength labels: {strength_count}",
        f"- Weakness labels: {weakness_count}",
        "",
        "## Safety Boundary",
        "",
        (
            "Reviewer identifiers are hashed. Hidden/private review data must not be stored. "
            "This dataset is for calibration, not truth generation."
        ),
        "",
    ]
    if dataset.license_warnings:
        lines.extend(["## License And Terms Warnings", ""])
        lines.extend(f"- {warning}" for warning in dataset.license_warnings)
        lines.append("")
    lines.extend(["## Papers", ""])
    if not papers:
        lines.append("No papers ingested.")
    for paper in papers:
        lines.extend(
            [
                f"### `{paper.id}`",
                "",
                f"- Title: {paper.title}",
                f"- Venue/year: {paper.venue} {paper.year}",
                f"- Decision: `{paper.decision or 'unknown'}`",
                f"- Average score: {paper.average_score:.2f}",
                f"- Confidence: {paper.confidence_summary}",
                f"- Topic tags: {', '.join(paper.topic_tags) or 'none'}",
                "",
            ]
        )
    lines.extend(["## Review Label Summary", ""])
    if reviews:
        lines.extend(
            [
                f"- Reviews with weaknesses: {sum(1 for review in reviews if review.weaknesses)}",
                f"- Reviews with questions: {sum(1 for review in reviews if review.questions)}",
                f"- Reviews with reproducibility comments: {sum(1 for review in reviews if review.reproducibility_comments)}",
                f"- Reviews with ethics comments: {sum(1 for review in reviews if review.ethics_comments)}",
            ]
        )
    else:
        lines.append("No reviews ingested.")
    return "\n".join(lines).rstrip() + "\n"


def _unique_dataset_id(datasets_dir: Path, name: str) -> str:
    base = f"review-dataset-{slugify(name)}"
    candidate = base
    suffix = 2
    while (datasets_dir / candidate / "dataset.json").exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
