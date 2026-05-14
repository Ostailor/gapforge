"""Venue profile registry for conference-style manuscript generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from gapforge.models import Provenance, to_plain
from gapforge.state import utc_now_iso

VENUE_TYPES = {"conference", "workshop", "journal", "preprint"}
PAPER_STYLES = {"empirical", "benchmark", "theory", "systems", "dataset", "methods", "measurement"}


@dataclass(slots=True)
class VenueProfile:
    id: str
    name: str
    field: str
    venue_type: str
    paper_style: str
    required_sections: list[str] = dataclass_field(default_factory=list)
    common_section_order: list[str] = dataclass_field(default_factory=list)
    page_limit: int = 0
    anonymity_required: bool = False
    artifact_expectations: list[str] = dataclass_field(default_factory=list)
    reproducibility_expectations: list[str] = dataclass_field(default_factory=list)
    reviewer_norms: list[str] = dataclass_field(default_factory=list)
    citation_style: str = ""
    latex_template_hint: str = ""
    limitations_expectations: list[str] = dataclass_field(default_factory=list)
    provenance: Provenance = dataclass_field(default_factory=lambda: Provenance(created_by_skill="venue-profile-registry"))


def list_venue_profiles() -> list[VenueProfile]:
    return [
        _profile(
            profile_id="generic_ml_conference",
            name="Generic ML Conference",
            field="machine learning",
            venue_type="conference",
            paper_style="empirical",
            required_sections=[
                "abstract",
                "introduction",
                "related_work",
                "method",
                "experiments",
                "results",
                "limitations",
                "ethics",
                "conclusion",
            ],
            common_section_order=[
                "abstract",
                "introduction",
                "related_work",
                "method",
                "experiments",
                "results",
                "limitations",
                "ethics",
                "conclusion",
            ],
            page_limit=9,
            anonymity_required=True,
            artifact_expectations=[
                "Artifact appendix or checklist is expected for empirical claims.",
                "Code, data, and environment details should be available or justified as withheld.",
            ],
            reproducibility_expectations=[
                "Report datasets, splits, metrics, baselines, uncertainty, and compute.",
                "Separate exploratory, smoke, pilot, and main results.",
            ],
            reviewer_norms=[
                "Reviewers expect strong baselines and ablations.",
                "Reviewers penalize overclaiming beyond the experimental evidence.",
                "Novelty must be positioned against closest prior work.",
            ],
            citation_style="numeric",
            latex_template_hint="Use a current ML conference style class as a structural guide; do not copy venue-specific prose.",
            limitations_expectations=[
                "Include a dedicated limitations section.",
                "State deployment-validity and dataset-validity limits explicitly.",
            ],
        ),
        _profile(
            profile_id="generic_ai_safety_workshop",
            name="Generic AI Safety Workshop",
            field="AI safety",
            venue_type="workshop",
            paper_style="benchmark",
            required_sections=["abstract", "introduction", "threat_model", "method", "experiments", "limitations", "conclusion"],
            common_section_order=[
                "abstract",
                "introduction",
                "threat_model",
                "related_work",
                "method",
                "experiments",
                "results",
                "limitations",
                "conclusion",
            ],
            page_limit=8,
            anonymity_required=True,
            artifact_expectations=["Benchmarks should include data cards, task cards, and misuse notes when applicable."],
            reproducibility_expectations=["Describe evaluation protocol, seeds, model access assumptions, and monitor prompts."],
            reviewer_norms=[
                "Reviewers expect clear threat models and safety relevance.",
                "Claims should distinguish benchmark protocol value from deployment validity.",
            ],
            citation_style="numeric",
            latex_template_hint="Workshop-style LaTeX with compact related work and explicit threat model framing.",
            limitations_expectations=[
                "List how benchmark artifacts could be misused.",
                "Do not imply real-world safety without external validation.",
            ],
        ),
        _profile(
            profile_id="generic_systems_conference",
            name="Generic Systems Conference",
            field="computer systems",
            venue_type="conference",
            paper_style="systems",
            required_sections=[
                "abstract",
                "introduction",
                "background",
                "design",
                "implementation",
                "evaluation",
                "limitations",
                "conclusion",
            ],
            common_section_order=[
                "abstract",
                "introduction",
                "background",
                "design",
                "implementation",
                "evaluation",
                "limitations",
                "conclusion",
            ],
            page_limit=12,
            anonymity_required=True,
            artifact_expectations=["Artifact availability, reproducible scripts, and system configuration are expected."],
            reproducibility_expectations=["Report workloads, environment, resource use, and end-to-end replication steps."],
            reviewer_norms=[
                "Reviewers expect realistic workloads and clear system boundaries.",
                "Evaluation should justify overhead, robustness, and failure modes.",
            ],
            citation_style="numeric",
            latex_template_hint="Systems conference structure with design and evaluation separated.",
            limitations_expectations=["Discuss operational constraints, deployment assumptions, and benchmark representativeness."],
        ),
        _profile(
            profile_id="generic_dataset_benchmark_track",
            name="Generic Dataset or Benchmark Track",
            field="datasets and benchmarks",
            venue_type="conference",
            paper_style="dataset",
            required_sections=[
                "abstract",
                "introduction",
                "related_work",
                "dataset",
                "benchmark_protocol",
                "experiments",
                "limitations",
                "ethics",
                "conclusion",
            ],
            common_section_order=[
                "abstract",
                "introduction",
                "related_work",
                "dataset",
                "benchmark_protocol",
                "experiments",
                "results",
                "limitations",
                "ethics",
                "conclusion",
            ],
            page_limit=10,
            anonymity_required=True,
            artifact_expectations=["Dataset cards, licenses, splits, baselines, and download/access terms should be explicit."],
            reproducibility_expectations=["Benchmark construction and evaluation protocol should be independently runnable."],
            reviewer_norms=[
                "Reviewers expect strong motivation for why a new benchmark is needed.",
                "Known dataset leakage, licensing, and representativeness risks must be visible.",
            ],
            citation_style="numeric",
            latex_template_hint="Dataset/benchmark track structure emphasizing task definition, data, protocol, and governance.",
            limitations_expectations=["Include a limitations section covering validity, access, licensing, and misuse risks."],
        ),
        _profile(
            profile_id="generic_theory_workshop",
            name="Generic Theory Workshop",
            field="theory",
            venue_type="workshop",
            paper_style="theory",
            required_sections=["abstract", "introduction", "preliminaries", "main_results", "proofs", "limitations", "conclusion"],
            common_section_order=["abstract", "introduction", "preliminaries", "main_results", "proofs", "discussion", "conclusion"],
            page_limit=8,
            anonymity_required=True,
            artifact_expectations=["Artifacts are optional unless experiments or mechanized proofs are central."],
            reproducibility_expectations=["Definitions, assumptions, theorem statements, and proof dependencies should be complete."],
            reviewer_norms=[
                "Reviewers expect precise assumptions and proof sketches in the main text.",
                "Empirical claims should be clearly secondary or omitted.",
            ],
            citation_style="numeric",
            latex_template_hint="Theory workshop structure with preliminaries before formal claims.",
            limitations_expectations=["State scope of assumptions and non-covered settings."],
        ),
        _profile(
            profile_id="arxiv_preprint",
            name="arXiv Preprint",
            field="general",
            venue_type="preprint",
            paper_style="measurement",
            required_sections=["abstract", "introduction", "method", "results", "limitations"],
            common_section_order=[
                "abstract",
                "introduction",
                "related_work",
                "method",
                "results",
                "limitations",
                "conclusion",
                "appendix",
            ],
            page_limit=0,
            anonymity_required=False,
            artifact_expectations=["Artifacts are optional but should be linked when claims depend on them."],
            reproducibility_expectations=["Enough detail should be present for readers to assess evidence quality."],
            reviewer_norms=["No acceptance claim is implied; preprint readers still expect accurate citations and limitations."],
            citation_style="author_year_or_numeric",
            latex_template_hint="Generic article or conference-like LaTeX structure is acceptable.",
            limitations_expectations=["Include limitations even when no formal venue requires them."],
        ),
    ]


def get_venue_profile(profile_id: str) -> VenueProfile:
    for profile in list_venue_profiles():
        if profile.id == profile_id:
            return profile
    allowed = ", ".join(profile.id for profile in list_venue_profiles())
    raise ValueError(f"Unknown venue profile `{profile_id}`. Expected one of: {allowed}")


def venue_profiles_json() -> str:
    return json.dumps(to_plain(list_venue_profiles()), indent=2) + "\n"


def is_venue_profile(profile_id: str) -> bool:
    return any(profile.id == profile_id for profile in list_venue_profiles())


def _profile(
    *,
    profile_id: str,
    name: str,
    field: str,
    venue_type: str,
    paper_style: str,
    required_sections: list[str],
    common_section_order: list[str],
    page_limit: int,
    anonymity_required: bool,
    artifact_expectations: list[str],
    reproducibility_expectations: list[str],
    reviewer_norms: list[str],
    citation_style: str,
    latex_template_hint: str,
    limitations_expectations: list[str],
) -> VenueProfile:
    if venue_type not in VENUE_TYPES:
        raise ValueError(f"Unsupported venue type: {venue_type}")
    if paper_style not in PAPER_STYLES:
        raise ValueError(f"Unsupported paper style: {paper_style}")
    return VenueProfile(
        id=profile_id,
        name=name,
        field=field,
        venue_type=venue_type,
        paper_style=paper_style,
        required_sections=required_sections,
        common_section_order=common_section_order,
        page_limit=page_limit,
        anonymity_required=anonymity_required,
        artifact_expectations=artifact_expectations,
        reproducibility_expectations=reproducibility_expectations,
        reviewer_norms=reviewer_norms,
        citation_style=citation_style,
        latex_template_hint=latex_template_hint,
        limitations_expectations=limitations_expectations,
        provenance=Provenance(
            created_by_skill="venue-profile-registry",
            source_ids=[profile_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Built-in venue profile guides paper structure and reviewer expectations; it is not an acceptance claim.",
        ),
    )
