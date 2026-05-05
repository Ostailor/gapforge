"""Build a structured map of a research field."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from gapforge.claim_ledger import ClaimLedger
from gapforge.models import Cluster, Evidence, FieldMap, Paper, Provenance, ResearchRunState
from gapforge.skills.base import Skill
from gapforge.sources.base import ResearchSource
from gapforge.sources.coverage import add_search_query_record
from gapforge.state import utc_now_iso

CLUSTER_KEYWORDS = {
    "Detection and Anomaly Modeling": {
        "detect",
        "detection",
        "anomaly",
        "outlier",
        "fraud",
        "collusion",
        "abuse",
        "attack",
    },
    "Graph and Network Methods": {
        "graph",
        "network",
        "node",
        "edge",
        "community",
        "bipartite",
        "relational",
        "link",
    },
    "Calibration and False Positives": {
        "false",
        "positive",
        "precision",
        "calibration",
        "threshold",
        "abstention",
        "uncertainty",
        "specificity",
    },
    "Benchmarks and Evaluation": {
        "benchmark",
        "dataset",
        "evaluation",
        "metric",
        "measure",
        "validity",
        "label",
        "ground",
        "truth",
    },
    "Explainability and Human Review": {
        "explain",
        "explanation",
        "interpretable",
        "interpretability",
        "review",
        "audit",
        "evidence",
        "human",
    },
}

METHOD_TERMS = {
    "graph neural networks": {"gnn", "graph neural", "message passing"},
    "representation learning": {"representation", "embedding", "latent"},
    "supervised classification": {"classifier", "classification", "supervised"},
    "anomaly detection": {"anomaly", "outlier"},
    "calibration": {"calibration", "threshold", "abstention", "uncertainty"},
    "benchmarking": {"benchmark", "evaluation", "dataset"},
    "human-in-the-loop review": {"human", "review", "audit"},
}

DATASET_TERMS = {
    "synthetic graphs": {"synthetic", "simulated"},
    "transaction logs": {"transaction", "payment", "market"},
    "interaction networks": {"interaction", "social", "network", "graph"},
    "public benchmarks": {"benchmark", "dataset", "corpus"},
    "review datasets": {"review", "openreview"},
}

METRIC_TERMS = {
    "false positive rate": {"false positive", "fpr", "specificity"},
    "precision": {"precision", "positive predictive"},
    "recall": {"recall", "sensitivity"},
    "auc": {"auc", "roc"},
    "calibration error": {"calibration", "ece"},
    "explanation coverage": {"explanation", "coverage", "audit"},
}

ADJACENT_FIELD_TERMS = {
    "fraud detection": {"fraud", "transaction"},
    "medical screening": {"screening", "specificity", "sensitivity"},
    "trust and safety": {"abuse", "moderation", "platform"},
    "cybersecurity intrusion detection": {"attack", "intrusion", "security"},
    "recommender-system manipulation": {"review", "rating", "recommender"},
}

STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "using",
    "based",
    "paper",
    "study",
    "studies",
    "method",
    "methods",
    "approach",
    "research",
}


class LiteratureCartographer(Skill):
    name = "literature-cartographer"

    def __init__(self, sources: list[ResearchSource]) -> None:
        self.sources = sources

    def run(self, state: ResearchRunState) -> ResearchRunState:
        if not state.papers:
            state.papers = self._search_papers(state)
        state.field_map = self.build_field_map(state.topic.text, state.papers)
        state.claims = self._add_mapping_claims(state).claims
        self.mark_complete(state)
        return state

    def build_field_map(self, topic: str, papers: list[Paper]) -> FieldMap:
        clusters = self._cluster_papers(papers)
        cluster_models = [self._build_cluster(name, cluster_papers) for name, cluster_papers in clusters.items()]
        dominant_methods = _top_detected_terms(papers, METHOD_TERMS, fallback_limit=6)
        common_datasets = _top_detected_terms(papers, DATASET_TERMS, fallback_limit=5)
        common_metrics = _top_detected_terms(papers, METRIC_TERMS, fallback_limit=5)
        saturated_areas = _saturated_areas(clusters, dominant_methods)
        underexplored_areas = _underexplored_areas(papers, clusters, common_metrics, common_datasets)
        contradictions = _contradictions(papers)
        adjacent_fields = _top_detected_terms(papers, ADJACENT_FIELD_TERMS, fallback_limit=5)
        confidence = _confidence(papers, cluster_models)
        limitations = _limitations(papers, confidence)

        return FieldMap(
            topic=topic,
            clusters=cluster_models,
            major_questions=_major_questions(topic, cluster_models),
            dominant_methods=dominant_methods,
            common_datasets=common_datasets,
            common_metrics=common_metrics,
            key_papers_by_cluster={
                cluster.name: [paper.id for paper in _key_papers(_papers_by_id(papers, cluster.paper_ids))] for cluster in cluster_models
            },
            newest_papers_by_cluster={
                cluster.name: [paper.id for paper in _newest_papers(_papers_by_id(papers, cluster.paper_ids))] for cluster in cluster_models
            },
            saturated_areas=saturated_areas,
            underexplored_areas=underexplored_areas,
            contradictions=contradictions,
            adjacent_fields=adjacent_fields,
            initial_gap_candidates=[
                f"Test whether {area.lower()} remains robust across the dominant clusters." for area in underexplored_areas[:4]
            ],
            confidence=confidence,
            limitations=limitations,
            provenance=Provenance(
                created_by_skill=self.name,
                source_ids=[paper.id for paper in papers],
                timestamp=utc_now_iso(),
                reasoning_summary="Deterministic keyword and metadata heuristics grouped papers into clusters and map-level signals.",
            ),
        )

    def _search_papers(self, state: ResearchRunState) -> list[Paper]:
        papers = []
        seen = set()
        for source in self.sources:
            failures: list[str] = []
            found: list[Paper] = []
            source_name = str(getattr(source, "name", source.__class__.__name__))
            try:
                found = source.search(state.topic.text, max_results=3, sort="newest")
            except Exception as exc:
                failures.append(f"{source_name} search failed for {state.topic.text!r}: {exc}")
            add_search_query_record(
                state,
                query=state.topic.text,
                source_names=[source_name],
                purpose="initial_topic",
                max_results=3,
                date_from=None,
                date_to=None,
                result_paper_ids=[paper.id for paper in found],
                failure_messages=failures,
            )
            for paper in found:
                if paper.id in seen:
                    continue
                seen.add(paper.id)
                papers.append(paper)
        return papers

    def _cluster_papers(self, papers: list[Paper]) -> dict[str, list[Paper]]:
        clusters: dict[str, list[Paper]] = defaultdict(list)
        for paper in papers:
            text = _paper_text(paper)
            scores = {name: sum(1 for keyword in keywords if keyword in text) for name, keywords in CLUSTER_KEYWORDS.items()}
            best_name, best_score = _best_cluster(scores)
            if best_score == 0:
                best_name = _fallback_cluster_name(paper)
            clusters[best_name].append(paper)
        return dict(sorted(clusters.items()))

    def _build_cluster(self, name: str, papers: list[Paper]) -> Cluster:
        methods = _top_detected_terms(papers, METHOD_TERMS, fallback_limit=4)
        representative = [paper.id for paper in _key_papers(papers)[:3]]
        open_questions = _cluster_open_questions(name, papers, methods)
        return Cluster(
            name=name,
            description=_cluster_description(name, papers),
            paper_ids=[paper.id for paper in papers],
            representative_papers=representative,
            dominant_methods=methods,
            open_questions=open_questions,
            why_it_matters=_why_cluster_matters(name),
        )

    def _add_mapping_claims(self, state: ResearchRunState) -> ClaimLedger:
        ledger = ClaimLedger(state.claims)
        field_map = state.field_map
        if field_map is None:
            return ledger

        for cluster in field_map.clusters:
            if len(cluster.paper_ids) < 2:
                continue
            claim = ledger.add_claim(
                f"The field contains a visible cluster around {cluster.name.lower()} with {len(cluster.paper_ids)} mapped papers.",
                "background",
                created_by_skill=self.name,
                confidence="medium" if len(cluster.paper_ids) >= 3 else "low",
                source_paper_ids=cluster.paper_ids,
                needs_verification=True,
                reasoning_summary="Cluster-level claim generated from deterministic title, abstract, venue, and keyword grouping.",
            )
            for paper in _papers_by_id(state.papers, cluster.paper_ids[:3]):
                ledger.add_evidence(claim.id, _paper_evidence(paper, f"Cluster evidence for {cluster.name}."))
            ledger.mark_uncertain(claim.id, confidence=claim.confidence)

        for area in field_map.underexplored_areas[:3]:
            evidence_papers = state.papers[: min(3, len(state.papers))]
            claim = ledger.add_claim(
                f"{area} appears underexplored in the current paper set.",
                "gap",
                created_by_skill=self.name,
                confidence="low",
                source_paper_ids=[paper.id for paper in evidence_papers],
                needs_verification=True,
                notes="Heuristic map signal; requires broader search before treating as a real gap.",
                reasoning_summary="Underexplored-area claim generated from sparse keyword coverage and map limitations.",
            )
            for paper in evidence_papers:
                ledger.add_evidence(claim.id, _paper_evidence(paper, "Sparse or indirect evidence for underexplored area."))
            ledger.mark_uncertain(claim.id, confidence="low")

        for saturated in field_map.saturated_areas[:2]:
            evidence_papers = state.papers[: min(5, len(state.papers))]
            claim = ledger.add_claim(
                f"{saturated} may be saturated relative to the current search results.",
                "background",
                created_by_skill=self.name,
                confidence="low",
                source_paper_ids=[paper.id for paper in evidence_papers],
                needs_verification=True,
                notes="Saturation is inferred from repeated cluster/method counts, not citation closure.",
                reasoning_summary="Saturation claim generated from repeated cluster and method patterns.",
            )
            for paper in evidence_papers[:3]:
                ledger.add_evidence(claim.id, _paper_evidence(paper, "Repeated topic signal."))
            ledger.mark_uncertain(claim.id, confidence="low")

        return ledger


def _paper_text(paper: Paper) -> str:
    return " ".join([paper.title, paper.abstract, paper.venue, " ".join(paper.keywords)]).lower()


def _best_cluster(scores: dict[str, int]) -> tuple[str, int]:
    for specific_name in [
        "Graph and Network Methods",
        "Benchmarks and Evaluation",
        "Calibration and False Positives",
        "Explainability and Human Review",
    ]:
        if scores.get(specific_name, 0) >= 2:
            return specific_name, scores[specific_name]
    return max(scores.items(), key=lambda item: (item[1], item[0]))


def _tokens(paper: Paper) -> list[str]:
    return [token for token in re.findall(r"[a-z][a-z0-9]{2,}", _paper_text(paper)) if token not in STOP_WORDS]


def _fallback_cluster_name(paper: Paper) -> str:
    counts = Counter(_tokens(paper))
    if not counts:
        return "General Field Context"
    return f"{counts.most_common(1)[0][0].title()} Thread"


def _top_detected_terms(papers: list[Paper], lexicon: dict[str, set[str]], fallback_limit: int) -> list[str]:
    scores: Counter[str] = Counter()
    for paper in papers:
        text = _paper_text(paper)
        for label, terms in lexicon.items():
            scores[label] += sum(1 for term in terms if term in text)
    detected = [label for label, score in scores.most_common() if score > 0]
    if detected:
        return detected[:fallback_limit]
    token_counts = Counter(token for paper in papers for token in _tokens(paper))
    return [token for token, _ in token_counts.most_common(fallback_limit)]


def _key_papers(papers: list[Paper]) -> list[Paper]:
    return sorted(papers, key=lambda paper: (paper.citation_count, paper.year, paper.title), reverse=True)


def _newest_papers(papers: list[Paper]) -> list[Paper]:
    return sorted(papers, key=lambda paper: (paper.year, paper.published_date, paper.title), reverse=True)[:3]


def _papers_by_id(papers: list[Paper], paper_ids: list[str]) -> list[Paper]:
    by_id = {paper.id: paper for paper in papers}
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]


def _cluster_description(name: str, papers: list[Paper]) -> str:
    venues = sorted({paper.venue for paper in papers if paper.venue})
    years = [paper.year for paper in papers if paper.year]
    year_span = f"{min(years)}-{max(years)}" if years else "unknown years"
    venue_text = ", ".join(venues[:4]) if venues else "mixed or unknown venues"
    return f"{len(papers)} papers from {year_span} emphasize {name.lower()} across {venue_text}."


def _cluster_open_questions(name: str, papers: list[Paper], methods: list[str]) -> list[str]:
    questions = [
        f"Which assumptions make {name.lower()} fail outside the studied settings?",
        f"How should {name.lower()} be evaluated against closest prior work?",
    ]
    if not any("dataset" in _paper_text(paper) or "benchmark" in _paper_text(paper) for paper in papers):
        questions.append("What benchmark or dataset would make this cluster's claims falsifiable?")
    if methods:
        questions.append(f"Do {methods[0]} results hold under stricter false-positive constraints?")
    return questions


def _why_cluster_matters(name: str) -> str:
    if "False Positives" in name:
        return "False-positive control determines whether a detector can be used in high-stakes review workflows."
    if "Benchmarks" in name:
        return "Benchmark design shapes whether reported progress transfers to realistic settings."
    if "Graph" in name:
        return "Graph assumptions often define what collusion patterns are even observable."
    if "Explainability" in name:
        return "Human review depends on evidence that can be inspected, challenged, and improved."
    return "This cluster captures repeated framing in the current literature map."


def _major_questions(topic: str, clusters: list[Cluster]) -> list[str]:
    questions = [f"What failure modes matter most for {topic}?"]
    questions.extend(question for cluster in clusters for question in cluster.open_questions[:1])
    return _dedupe(questions)[:8]


def _saturated_areas(clusters: dict[str, list[Paper]], methods: list[str]) -> list[str]:
    areas = [f"{name} has repeated coverage in the current sample" for name, papers in clusters.items() if len(papers) >= 3]
    if methods:
        method_counts = Counter(method for method in methods)
        areas.extend([f"{method} appears repeatedly as a default method family" for method, count in method_counts.items() if count > 1])
    return areas


def _underexplored_areas(
    papers: list[Paper],
    clusters: dict[str, list[Paper]],
    metrics: list[str],
    datasets: list[str],
) -> list[str]:
    areas = []
    if "false positive rate" not in metrics:
        areas.append("Explicit false-positive-rate evaluation")
    if "calibration error" not in metrics:
        areas.append("Calibration under deployment shift")
    if "explanation coverage" not in metrics:
        areas.append("Auditable explanation coverage")
    if not datasets or "synthetic graphs" in datasets and len(datasets) == 1:
        areas.append("Realistic labeled datasets beyond synthetic benchmarks")
    if "Calibration and False Positives" not in clusters:
        areas.append("Low false-positive optimization as a primary objective")
    if len(papers) < 5:
        areas.append("Broader source coverage before firm gap claims")
    return _dedupe(areas)


def _contradictions(papers: list[Paper]) -> list[str]:
    text = " ".join(_paper_text(paper) for paper in papers)
    contradictions = []
    if "accuracy" in text and ("false positive" in text or "precision" in text):
        contradictions.append("Some papers emphasize aggregate accuracy while others imply false-positive control is the real bottleneck.")
    if "synthetic" in text and ("real" in text or "field" in text or "deployment" in text):
        contradictions.append("Synthetic evaluation appears alongside claims that deployment realism matters.")
    return contradictions


def _confidence(papers: list[Paper], clusters: list[Cluster]) -> str:
    if len(papers) >= 12 and len(clusters) >= 4:
        return "medium"
    if len(papers) >= 5 and len(clusters) >= 2:
        return "low"
    return "low"


def _limitations(papers: list[Paper], confidence: str) -> list[str]:
    limitations = [
        "Heuristic keyword clustering can miss semantic relationships and merge distinct subproblems.",
        "The map reflects the current paper set, not exhaustive field coverage.",
    ]
    if confidence == "low":
        limitations.append("Evidence is too sparse for firm saturation or novelty conclusions.")
    if any((paper.raw_metadata or {}).get("fallback") for paper in papers):
        limitations.append("Some papers came from deterministic fallback metadata, so claims require real-source verification.")
    return limitations


def _paper_evidence(paper: Paper, notes: str) -> Evidence:
    quote = paper.abstract or paper.title
    return Evidence(
        source_id=paper.id,
        source_paper_id=paper.id,
        quote=quote[:500],
        locator=paper.url or paper.id,
        confidence="medium" if paper.abstract else "low",
        notes=notes,
    )


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
