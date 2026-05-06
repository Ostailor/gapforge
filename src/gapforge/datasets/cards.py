"""Dataset card rendering."""

from __future__ import annotations

from gapforge.models import DatasetCard, DatasetRecord


def default_dataset_card(record: DatasetRecord) -> DatasetCard:
    fixture_note = _fixture_or_synthetic_note(record)
    limitations = list(record.limitations)
    if fixture_note:
        limitations.append(fixture_note)
    return DatasetCard(
        dataset_id=record.id,
        motivation=record.intended_use or "Dataset registered for experiment execution.",
        composition=record.schema_summary or record.size_summary or "Composition not yet summarized.",
        collection_process=record.source or "Collection process not specified.",
        preprocessing="Preprocessing not specified.",
        labeling="Labeling process not specified.",
        recommended_splits=record.split_names,
        leakage_risks=["No split integrity validation has been reviewed yet."],
        bias_risks=["Bias risks require human review before interpreting results."],
        privacy_risks=record.safety_notes,
        limitations=limitations,
        citation=record.source_url or record.source or "Citation not specified.",
        provenance=record.provenance,
    )


def render_dataset_card_markdown(record: DatasetRecord, card: DatasetCard) -> str:
    lines = [
        f"# Dataset Card: {record.name}",
        "",
        f"- Dataset ID: `{record.id}`",
        f"- Type: `{record.dataset_type}`",
        f"- Source: {record.source or 'unknown'}",
        f"- Source URL: {record.source_url or 'unknown'}",
        f"- Local path: `{record.local_path or 'none'}`",
        f"- Version: {record.version or 'unknown'}",
        f"- License: {record.license or 'unknown'}",
        "",
        "## Motivation",
        "",
        card.motivation or "Not specified.",
        "",
        "## Composition",
        "",
        card.composition or "Not specified.",
        "",
        "## Collection Process",
        "",
        card.collection_process or "Not specified.",
        "",
        "## Preprocessing",
        "",
        card.preprocessing or "Not specified.",
        "",
        "## Labeling",
        "",
        card.labeling or "Not specified.",
        "",
    ]
    _extend_list(lines, "Recommended Splits", card.recommended_splits)
    _extend_list(lines, "Leakage Risks", card.leakage_risks)
    _extend_list(lines, "Bias Risks", card.bias_risks)
    _extend_list(lines, "Privacy Risks", card.privacy_risks)
    _extend_list(lines, "Limitations", card.limitations)
    lines.extend(["## Citation", "", card.citation or "Not specified.", ""])
    return "\n".join(lines).rstrip() + "\n"


def render_dataset_registry_markdown(records: list[DatasetRecord]) -> str:
    lines = ["# Dataset Registry", ""]
    if not records:
        lines.append("No datasets registered yet.")
        return "\n".join(lines).rstrip() + "\n"
    for record in records:
        lines.extend(
            [
                f"## `{record.id}` {record.name}",
                "",
                f"- Type: `{record.dataset_type}`",
                f"- License: {record.license or 'unknown'}",
                f"- Local path: `{record.local_path or 'none'}`",
                f"- Size: {record.size_summary or 'unknown'}",
                f"- Splits: {', '.join(record.split_names) or 'none'}",
                f"- Intended use: {record.intended_use or 'not specified'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _extend_list(lines: list[str], title: str, items: list[str]) -> None:
    lines.extend([f"## {title}", ""])
    lines.extend([f"- {item}" for item in items] or ["- none"])
    lines.append("")


def _fixture_or_synthetic_note(record: DatasetRecord) -> str:
    if record.dataset_type == "fixture":
        return "Fixture data is for workflow validation and cannot support real empirical claims."
    if record.dataset_type == "synthetic":
        return "Synthetic data must be labeled as synthetic in reports and cannot be treated as real-world evidence."
    return ""
