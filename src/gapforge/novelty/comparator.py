"""Deterministic closest-prior-work comparison."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from gapforge.models import Gap, Paper, PaperNote, PaperSection


@dataclass(slots=True)
class PriorWorkMatch:
    paper: Paper
    overall_similarity: float
    title_similarity: float
    abstract_similarity: float
    full_text_similarity: float
    problem_overlap: float
    method_overlap: float
    dataset_overlap: float
    metric_overlap: float
    contribution_overlap: float
    limitation_overlap: float
    evaluation_overlap: float
    tests_minimum_experiment: bool
    overlap_terms: list[str]


class PriorWorkComparator:
    def compare(
        self,
        idea_summary: str,
        candidates: list[Paper],
        *,
        gap: Gap | None = None,
        notes: list[PaperNote] | None = None,
        sections: list[PaperSection] | None = None,
    ) -> list[PriorWorkMatch]:
        note_by_paper = {note.paper_id: note for note in notes or []}
        sections_by_paper: dict[str, list[PaperSection]] = {}
        for section in sections or []:
            sections_by_paper.setdefault(section.paper_id, []).append(section)
        matches: list[PriorWorkMatch] = []
        for paper in candidates:
            note = note_by_paper.get(paper.id)
            paper_sections = sections_by_paper.get(paper.id, [])
            match = self._compare_one(idea_summary, paper, gap=gap, note=note, sections=paper_sections)
            if match.overall_similarity >= 0.08:
                matches.append(match)
        return sorted(matches, key=lambda item: item.overall_similarity, reverse=True)

    def _compare_one(
        self,
        idea_summary: str,
        paper: Paper,
        *,
        gap: Gap | None,
        note: PaperNote | None,
        sections: list[PaperSection],
    ) -> PriorWorkMatch:
        idea_tokens = _tokens(idea_summary)
        paper_text = _paper_text(paper, note)
        section_text = " ".join(section.text for section in sections)
        full_text = " ".join([paper_text, section_text])
        title_similarity = SequenceMatcher(None, _norm(idea_summary), _norm(paper.title)).ratio()
        if gap is not None and gap.title:
            title_similarity = max(title_similarity, SequenceMatcher(None, _norm(gap.title), _norm(paper.title)).ratio())
        abstract_similarity = _weighted_token_overlap(idea_tokens, _tokens(paper.abstract))
        full_text_similarity = _weighted_token_overlap(idea_tokens, _tokens(full_text)) if section_text else 0.0
        problem_overlap = _category_overlap(idea_summary, full_text, PROBLEM_TERMS)
        method_overlap = _category_overlap(idea_summary, full_text, METHOD_TERMS)
        dataset_overlap = _category_overlap(idea_summary, full_text, DATASET_TERMS)
        metric_overlap = _category_overlap(idea_summary, full_text, METRIC_TERMS)
        contribution_overlap = _category_overlap(idea_summary, full_text, CONTRIBUTION_TERMS)
        limitation_overlap = _category_overlap(idea_summary, full_text, LIMITATION_TERMS)
        evaluation_overlap = max(dataset_overlap, metric_overlap, _category_overlap(idea_summary, full_text, EVALUATION_TERMS))
        minimum = gap.minimum_experiment_needed if gap is not None else ""
        tests_minimum = bool(minimum and _weighted_token_overlap(_tokens(minimum), _tokens(full_text)) >= 0.45)
        overlap_terms = sorted(set(idea_tokens) & set(_tokens(full_text)))[:12]
        overall = (
            0.18 * title_similarity
            + 0.17 * abstract_similarity
            + 0.15 * full_text_similarity
            + 0.14 * problem_overlap
            + 0.12 * method_overlap
            + 0.12 * evaluation_overlap
            + 0.06 * contribution_overlap
            + 0.06 * limitation_overlap
        )
        if tests_minimum:
            overall += 0.12
        if title_similarity > 0.92:
            overall += 0.25
        return PriorWorkMatch(
            paper=paper,
            overall_similarity=min(1.0, overall),
            title_similarity=title_similarity,
            abstract_similarity=abstract_similarity,
            full_text_similarity=full_text_similarity,
            problem_overlap=problem_overlap,
            method_overlap=method_overlap,
            dataset_overlap=dataset_overlap,
            metric_overlap=metric_overlap,
            contribution_overlap=contribution_overlap,
            limitation_overlap=limitation_overlap,
            evaluation_overlap=evaluation_overlap,
            tests_minimum_experiment=tests_minimum,
            overlap_terms=overlap_terms,
        )


PROBLEM_TERMS = {"collusion", "fraud", "anomaly", "detection", "agents", "provenance", "portfolio", "wildfire"}
METHOD_TERMS = {"calibration", "abstention", "graph", "neural", "classification", "benchmark", "optimization", "monitoring"}
DATASET_TERMS = {"dataset", "benchmark", "corpus", "synthetic", "real", "deployment", "labels"}
METRIC_TERMS = {"false", "positive", "fpr", "precision", "recall", "auc", "specificity", "calibration"}
CONTRIBUTION_TERMS = {"propose", "introduce", "present", "show", "demonstrate", "study", "evaluate"}
LIMITATION_TERMS = {"limitation", "future", "fails", "cannot", "challenge", "open"}
EVALUATION_TERMS = {"experiment", "evaluation", "baseline", "metric", "ablation", "result"}
STOP_WORDS = {"the", "and", "for", "with", "from", "that", "this", "into", "under", "using", "paper", "work"}


def comparison_row(match: PriorWorkMatch) -> dict[str, object]:
    return {
        "paper_id": match.paper.id,
        "title": match.paper.title,
        "overall_similarity": round(match.overall_similarity, 3),
        "title_similarity": round(match.title_similarity, 3),
        "abstract_similarity": round(match.abstract_similarity, 3),
        "full_text_similarity": round(match.full_text_similarity, 3),
        "problem_overlap": round(match.problem_overlap, 3),
        "method_overlap": round(match.method_overlap, 3),
        "dataset_overlap": round(match.dataset_overlap, 3),
        "metric_overlap": round(match.metric_overlap, 3),
        "evaluation_overlap": round(match.evaluation_overlap, 3),
        "tests_minimum_experiment": match.tests_minimum_experiment,
        "overlap_terms": match.overlap_terms,
    }


def _paper_text(paper: Paper, note: PaperNote | None) -> str:
    note_text = ""
    if note is not None:
        note_text = " ".join(
            [
                note.one_sentence_summary,
                " ".join(note.core_claims),
                " ".join(note.method),
                " ".join(note.datasets),
                " ".join(note.metrics),
                " ".join(note.main_results),
                " ".join(note.stated_limitations),
            ]
        )
    return " ".join([paper.title, paper.abstract, paper.venue, " ".join(paper.keywords), note_text])


def _category_overlap(idea: str, paper_text: str, terms: set[str]) -> float:
    idea_terms = {term for term in terms if term in idea.lower()}
    if not idea_terms:
        return 0.0
    paper_lower = paper_text.lower()
    return len({term for term in idea_terms if term in paper_lower}) / len(idea_terms)


def _weighted_token_overlap(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    left_counts = {token: left.count(token) for token in set(left)}
    right_counts = {token: right.count(token) for token in set(right)}
    shared = set(left_counts) & set(right_counts)
    score = sum(1 + math.log1p(min(left_counts[token], right_counts[token])) for token in shared)
    denom = sum(1 + math.log1p(count) for count in left_counts.values())
    return min(1.0, score / max(1.0, denom))


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOP_WORDS and len(token) > 2]


def _norm(text: str) -> str:
    return " ".join(_tokens(text))
