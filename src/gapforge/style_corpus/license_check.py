"""License checks for style corpus TeX ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ALLOWED_MARKERS = (
    "spdx-license-identifier: cc-by",
    "spdx-license-identifier: cc0",
    "spdx-license-identifier: mit",
    "spdx-license-identifier: apache-2.0",
    "creative commons attribution",
    "cc-by",
    "cc by",
    "public domain",
)
RESTRICTED_MARKERS = (
    "all rights reserved",
    "do not distribute",
    "no redistribution",
    "not for redistribution",
    "copyrighted source",
    "restricted source",
    "proprietary",
)


@dataclass(slots=True)
class LicenseCheckResult:
    status: str
    warnings: list[str] = field(default_factory=list)


def check_tex_license(path: Path, source_url: str = "") -> LicenseCheckResult:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    locator = source_url or str(path)
    if any(marker in text for marker in RESTRICTED_MARKERS):
        return LicenseCheckResult(
            status="restricted",
            warnings=[f"Source `{locator}` contains restricted-license markers and was rejected."],
        )
    if any(marker in text for marker in ALLOWED_MARKERS):
        return LicenseCheckResult(status="allowed", warnings=[])
    return LicenseCheckResult(
        status="unknown",
        warnings=[f"License for source `{locator}` is unknown; retain only structural features and review before use."],
    )
