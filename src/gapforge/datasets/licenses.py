"""License and terms heuristics for dataset downloads."""

from __future__ import annotations

RESTRICTED_MARKERS = {
    "restricted",
    "non-commercial",
    "noncommercial",
    "research only",
    "terms",
    "eula",
    "gated",
    "kaggle",
}


def license_warnings(license_text: str) -> list[str]:
    normalized = license_text.strip().lower()
    if not normalized:
        return ["Dataset license is missing; confirm terms before using or redistributing the data."]
    warnings: list[str] = []
    if any(marker in normalized for marker in RESTRICTED_MARKERS):
        warnings.append(f"Dataset license/terms look restricted: `{license_text}`.")
    return warnings


def requires_terms_consent(license_text: str) -> bool:
    normalized = license_text.strip().lower()
    return any(marker in normalized for marker in RESTRICTED_MARKERS)


def url_requires_auth(url: str) -> bool:
    normalized = url.strip().lower()
    if normalized.startswith("file://"):
        return False
    return any(marker in normalized for marker in ("kaggle.com", "huggingface.co/datasets", "login", "token="))
