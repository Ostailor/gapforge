"""Label helpers for selected-benchmark synthetic traces."""

from __future__ import annotations

SYNTHETIC_LABEL = "synthetic"
HONEST_LABEL = "honest"
COLLUSIVE_LABEL = "collusive"
AMBIGUOUS_LABEL = "ambiguous"
BENIGN_COORDINATION_LABEL = "benign_coordination"
HARD_NEGATIVE_LABEL = "hard_negative"
EXPLICIT_COLLUSION_LABEL = "explicit_collusion"
ACTION_ONLY_LABEL = "action_only"
TRANSCRIPT_VISIBLE_LABEL = "transcript_visible"
EXCLUDE_MAIN_METRIC_LABEL = "exclude_from_main_metric"


def synthetic_labels(*labels: str) -> list[str]:
    """Return stable labels with the required synthetic marker first."""

    ordered = [SYNTHETIC_LABEL]
    for label in labels:
        if label and label not in ordered:
            ordered.append(label)
    return ordered
