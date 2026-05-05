"""Conservative manuscript starter sections."""

from __future__ import annotations

from gapforge.models import ExperimentPlan, ExperimentProtocol, Gap, NoveltyDossier, ResearchDirection


def render_abstract(direction: ResearchDirection, gap: Gap | None, protocol: ExperimentProtocol | None) -> str:
    topic = direction.title or (gap.title if gap else "Untitled direction")
    lines = [
        "# Abstract Draft",
        "",
        "This is a starter abstract, not a claim of completed results.",
        "",
        f"We study `{topic}`.",
        "The current evidence suggests a research direction, but final claims require the planned experiment and reviewer checks.",
    ]
    if gap is not None:
        lines.append(f"The motivating gap is: {gap.description or gap.title}.")
    if protocol is not None:
        lines.append(f"The planned protocol tests: {protocol.hypothesis or protocol.objective}.")
    lines.append("Expected outcomes are hypothetical until experiments are run.")
    return "\n".join(lines).rstrip() + "\n"


def render_intro_outline(direction: ResearchDirection, gap: Gap | None, dossier: NoveltyDossier | None) -> str:
    lines = [
        "# Introduction Outline",
        "",
        "1. Define the broad problem and why the exact setting matters.",
        "2. State the evidence-backed gap without overclaiming novelty.",
        "3. Summarize closest prior work and the decisive difference needed.",
        "4. Present the experiment as a test of the gap, not as a completed result.",
        "5. Preview limitations, missing searches, and expected reviewer concerns.",
        "",
        "## Direction",
        "",
        direction.summary or direction.title,
    ]
    if gap is not None:
        lines.extend(
            ["", "## Gap", "", gap.description or gap.title, "", f"Risk that gap is fake: {gap.risk_that_gap_is_fake or 'unknown'}"]
        )
    if dossier is not None:
        lines.extend(
            [
                "",
                "## Novelty Positioning",
                "",
                f"Verdict: {dossier.verdict}",
                f"Decisive difference: {dossier.decisive_difference_needed or 'not specified'}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_method_outline(protocol: ExperimentProtocol | None, experiment: ExperimentPlan | None) -> str:
    lines = ["# Method Outline", ""]
    if protocol is None and experiment is None:
        lines.append("No experiment protocol or plan is linked yet.")
        return "\n".join(lines).rstrip() + "\n"
    if protocol is not None:
        lines.extend(
            [
                "## Protocol Objective",
                "",
                protocol.objective,
                "",
                "## Implementation Modules",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in protocol.implementation_modules] or ["- none"])
        lines.extend(["", "## Evaluation Script", ""])
        lines.extend([f"- {item}" for item in protocol.evaluation_script_outline] or ["- none"])
    if experiment is not None:
        lines.extend(["", "## Falsification Condition", "", experiment.what_result_would_falsify_the_idea or "Not specified."])
    return "\n".join(lines).rstrip() + "\n"


def render_expected_results(protocol: ExperimentProtocol | None, experiment: ExperimentPlan | None) -> str:
    lines = [
        "# Expected Results",
        "",
        "All expected results in this file are hypothetical. GapForge has not run the experiment and does not claim findings.",
        "",
    ]
    patterns = experiment.expected_result_patterns if experiment is not None else []
    if protocol is not None:
        patterns.extend([f"Protocol should produce artifact `{artifact}`." for artifact in protocol.expected_artifacts])
    lines.extend([f"- Hypothetical: {item}" for item in patterns] or ["- Hypothetical: define expected result patterns before running."])
    lines.extend(["", "## Falsification", ""])
    lines.append(experiment.what_result_would_falsify_the_idea if experiment is not None else "Not specified.")
    return "\n".join(lines).rstrip() + "\n"


def render_limitations(direction: ResearchDirection, gap: Gap | None, dossier: NoveltyDossier | None, missing: list[str]) -> str:
    lines = ["# Limitations And Uncertainty", ""]
    lines.extend([f"- Direction maturity: {direction.maturity}", f"- Readiness score: {direction.readiness_score:.2f}"])
    if gap is not None:
        lines.append(f"- Risk that gap is fake: {gap.risk_that_gap_is_fake or 'unknown'}")
    if dossier is not None:
        lines.extend([f"- Novelty verdict: {dossier.verdict}", f"- Missing searches: {', '.join(dossier.missing_searches) or 'none'}"])
    lines.extend(["", "## Missing Requirements", ""])
    lines.extend([f"- {item}" for item in missing] or ["- none"])
    lines.extend(["", "## Required Honesty Notes", ""])
    lines.extend(
        [
            "- Do not present expected results as completed findings.",
            "- Do not claim exhaustive literature coverage.",
            "- Cite paper IDs and available DOI/arXiv/URLs for every related-work claim.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
