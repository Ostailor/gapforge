"""Claim ledger for auditable research assertions."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.models import Claim, Evidence, Provenance, to_plain
from gapforge.state import utc_now_iso

VALID_CLAIM_TYPES = {"background", "method", "novelty", "gap", "result", "limitation", "analogy"}
VALID_STATUSES = {"unsupported", "supported", "contested", "uncertain", "falsified"}
VALID_CONFIDENCE = {"low", "medium", "high"}


class ClaimLedger:
    """Mutable ledger for claims, evidence, counterevidence, and verification status."""

    def __init__(self, claims: list[Claim] | None = None) -> None:
        self.claims: list[Claim] = list(claims or [])

    def add_claim(
        self,
        text: str,
        claim_type: str,
        *,
        created_by_skill: str,
        confidence: str = "medium",
        source_paper_ids: list[str] | None = None,
        notes: str = "",
        needs_verification: bool = True,
        closest_prior_work: list[str] | None = None,
        reasoning_summary: str = "",
    ) -> Claim:
        if claim_type not in VALID_CLAIM_TYPES:
            raise ValueError(f"Unsupported claim type: {claim_type}")
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Unsupported confidence: {confidence}")

        source_ids = source_paper_ids or []
        claim = Claim(
            id=self._next_id(),
            text=text,
            type=claim_type,
            confidence=confidence,
            source_paper_ids=source_ids,
            created_by_skill=created_by_skill,
            needs_verification=needs_verification,
            notes=notes,
            closest_prior_work=closest_prior_work or [],
            provenance=Provenance(
                created_by_skill=created_by_skill,
                source_ids=source_ids,
                timestamp=utc_now_iso(),
                reasoning_summary=reasoning_summary or f"{created_by_skill} created this {claim_type} claim from linked evidence.",
            ),
        )
        self.claims.append(claim)
        return claim

    def add_evidence(self, claim_id: str, evidence: Evidence) -> Claim:
        claim = self._get(claim_id)
        claim.supporting_evidence.append(evidence)
        self._track_source(claim, evidence)
        return claim

    def add_counterevidence(self, claim_id: str, evidence: Evidence) -> Claim:
        claim = self._get(claim_id)
        claim.counter_evidence.append(evidence)
        self._track_source(claim, evidence)
        if claim.status == "supported":
            claim.status = "contested"
        return claim

    def mark_supported(self, claim_id: str, *, confidence: str | None = None) -> Claim:
        claim = self._get(claim_id)
        claim.status = "supported"
        claim.needs_verification = False
        if confidence is not None:
            self._set_confidence(claim, confidence)
        return claim

    def mark_contested(self, claim_id: str, *, confidence: str | None = None) -> Claim:
        claim = self._get(claim_id)
        claim.status = "contested"
        claim.needs_verification = True
        if confidence is not None:
            self._set_confidence(claim, confidence)
        return claim

    def mark_uncertain(self, claim_id: str, *, confidence: str = "low") -> Claim:
        claim = self._get(claim_id)
        claim.status = "uncertain"
        claim.needs_verification = True
        self._set_confidence(claim, confidence)
        return claim

    def claims_needing_verification(self) -> list[Claim]:
        return [claim for claim in self.claims if claim.needs_verification]

    def claims_without_sources(self) -> list[Claim]:
        return [claim for claim in self.claims if not claim.source_paper_ids]

    def export_markdown(self) -> str:
        lines = ["# Claim Ledger", ""]
        if not self.claims:
            lines.append("No claims recorded.")
            return "\n".join(lines) + "\n"

        for claim in self.claims:
            lines.extend(
                [
                    f"## {claim.id}: {claim.type}",
                    "",
                    claim.text,
                    "",
                    f"- Status: {claim.status}",
                    f"- Confidence: {claim.confidence}",
                    f"- Needs verification: {str(claim.needs_verification).lower()}",
                    f"- Created by: {claim.created_by_skill}",
                    f"- Source papers: {', '.join(claim.source_paper_ids) if claim.source_paper_ids else 'none'}",
                    "",
                    "### Supporting Evidence",
                    "",
                ]
            )
            lines.extend(_evidence_lines(claim.supporting_evidence))
            lines.extend(["", "### Counterevidence", ""])
            lines.extend(_evidence_lines(claim.counter_evidence))
            if claim.notes:
                lines.extend(["", "### Notes", "", claim.notes])
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(to_plain(self.claims), indent=2) + "\n", encoding="utf-8")

    def save_markdown(self, path: Path) -> None:
        path.write_text(self.export_markdown(), encoding="utf-8")

    def add(self, text: str, claim_type: str, evidence: list[Evidence] | None = None, status: str = "unsupported") -> Claim:
        """Backward-compatible adapter for the initial scaffold."""

        claim = self.add_claim(text=text, claim_type=claim_type, created_by_skill="unknown")
        for item in evidence or []:
            self.add_evidence(claim.id, item)
        if status == "supported":
            self.mark_supported(claim.id)
        elif status == "contested":
            self.mark_contested(claim.id)
        elif status == "uncertain":
            self.mark_uncertain(claim.id)
        elif status in VALID_STATUSES:
            claim.status = status
        return claim

    def _next_id(self) -> str:
        return f"claim-{len(self.claims) + 1}"

    def _get(self, claim_id: str) -> Claim:
        for claim in self.claims:
            if claim.id == claim_id:
                return claim
        raise KeyError(f"Unknown claim: {claim_id}")

    def _set_confidence(self, claim: Claim, confidence: str) -> None:
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Unsupported confidence: {confidence}")
        claim.confidence = confidence

    def _track_source(self, claim: Claim, evidence: Evidence) -> None:
        source_paper_id = evidence.source_paper_id or evidence.source_id
        if source_paper_id and source_paper_id not in claim.source_paper_ids:
            claim.source_paper_ids.append(source_paper_id)


def _evidence_lines(evidence: list[Evidence]) -> list[str]:
    if not evidence:
        return ["- none"]
    return [f"- `{item.source_id}` ({item.confidence}): {item.quote} [{item.locator}]" for item in evidence]
