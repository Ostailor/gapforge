"""Venue templates for manuscript submission readiness."""

from __future__ import annotations

import json

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import VENUE_FORMATS, VENUE_TYPES, ManuscriptState, VenueTemplate
from gapforge.models import Provenance, to_plain
from gapforge.state import utc_now_iso


def list_venue_templates() -> list[VenueTemplate]:
    """Return built-in venue templates as fresh dataclass instances."""

    return [
        _template(
            template_id="generic_conference",
            name="Generic Conference",
            venue_type="conference",
            manuscript_format="latex",
            sections_required=["abstract", "introduction", "related_work", "method", "experiments", "results", "limitations", "conclusion"],
            page_limit=8,
            anonymization_required=True,
            artifact_policy="encouraged",
            ethics_required=False,
            reproducibility_required=True,
            citation_style="numeric",
        ),
        _template(
            template_id="generic_workshop",
            name="Generic Workshop",
            venue_type="workshop",
            manuscript_format="latex",
            sections_required=["abstract", "introduction", "method", "experiments", "results", "limitations"],
            page_limit=4,
            anonymization_required=True,
            artifact_policy="optional",
            ethics_required=False,
            reproducibility_required=False,
            citation_style="numeric",
        ),
        _template(
            template_id="arxiv_preprint",
            name="arXiv Preprint",
            venue_type="preprint",
            manuscript_format="latex",
            sections_required=["abstract", "introduction", "method", "results", "limitations"],
            page_limit=0,
            anonymization_required=False,
            artifact_policy="optional",
            ethics_required=False,
            reproducibility_required=False,
            citation_style="author_year_or_numeric",
        ),
        _template(
            template_id="ml_conference_like",
            name="ML Conference Like",
            venue_type="conference",
            manuscript_format="latex",
            sections_required=[
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
            anonymization_required=True,
            artifact_policy="expected",
            ethics_required=True,
            reproducibility_required=True,
            citation_style="numeric",
        ),
        _template(
            template_id="artifact_evaluation_like",
            name="Artifact Evaluation Like",
            venue_type="conference",
            manuscript_format="markdown",
            sections_required=["abstract", "method", "experiments", "results", "limitations", "appendix"],
            page_limit=0,
            anonymization_required=False,
            artifact_policy="required",
            ethics_required=False,
            reproducibility_required=True,
            citation_style="numeric",
        ),
    ]


def get_venue_template(template_id: str) -> VenueTemplate:
    for template in list_venue_templates():
        if template.id == template_id:
            return template
    allowed = ", ".join(template.id for template in list_venue_templates())
    raise ValueError(f"Unknown venue template `{template_id}`. Expected one of: {allowed}")


def venue_templates_json() -> str:
    return json.dumps(to_plain(list_venue_templates()), indent=2) + "\n"


class ManuscriptVenueManager:
    """Assign built-in venue templates to manuscript state."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)

    def set_venue(self, manuscript_id: str, venue_id: str) -> ManuscriptState:
        template = get_venue_template(venue_id)
        state = self.manuscript_manager.load_state(manuscript_id)
        state.manuscript.target_venue = template.id
        state.manuscript.updated_at = utc_now_iso()
        state.provenance.append(
            Provenance(
                created_by_skill="manuscript-venue",
                source_ids=[manuscript_id, template.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Assigned a built-in venue template for venue-aware submission readiness checks.",
            )
        )
        self.manuscript_manager._save_state(state)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        (root / "submission" / "venue_template.json").write_text(json.dumps(to_plain(template), indent=2) + "\n", encoding="utf-8")
        return state


def _template(
    *,
    template_id: str,
    name: str,
    venue_type: str,
    manuscript_format: str,
    sections_required: list[str],
    page_limit: int,
    anonymization_required: bool,
    artifact_policy: str,
    ethics_required: bool,
    reproducibility_required: bool,
    citation_style: str,
) -> VenueTemplate:
    if venue_type not in VENUE_TYPES:
        raise ValueError(f"Unsupported venue type: {venue_type}")
    if manuscript_format not in VENUE_FORMATS:
        raise ValueError(f"Unsupported venue format: {manuscript_format}")
    return VenueTemplate(
        id=template_id,
        name=name,
        venue_type=venue_type,
        format=manuscript_format,
        sections_required=sections_required,
        page_limit=page_limit,
        anonymization_required=anonymization_required,
        artifact_policy=artifact_policy,
        ethics_required=ethics_required,
        reproducibility_required=reproducibility_required,
        citation_style=citation_style,
        provenance=Provenance(
            created_by_skill="venue-template",
            source_ids=[template_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Built-in deterministic venue template; not a claim about any specific venue's current rules.",
        ),
    )
