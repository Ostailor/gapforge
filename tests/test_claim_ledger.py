from __future__ import annotations

from gapforge.claim_ledger import ClaimLedger
from gapforge.models import Evidence


def test_add_claims_and_evidence() -> None:
    ledger = ClaimLedger()
    claim = ledger.add_claim(
        "Existing benchmarks under-measure costly false positives.",
        "limitation",
        created_by_skill="deep-reading",
        source_paper_ids=["paper-1"],
    )
    ledger.add_evidence(
        claim.id,
        Evidence(
            source_id="paper-1",
            source_paper_id="paper-1",
            quote="The benchmark reports aggregate accuracy only.",
            locator="https://example.test/paper-1",
        ),
    )
    ledger.mark_supported(claim.id, confidence="high")

    assert claim.status == "supported"
    assert claim.confidence == "high"
    assert not claim.needs_verification
    assert claim.supporting_evidence


def test_add_counterevidence_marks_supported_claim_contested() -> None:
    ledger = ClaimLedger()
    claim = ledger.add_claim("A baseline is missing.", "novelty", created_by_skill="novelty-gate")
    ledger.add_evidence(claim.id, Evidence(source_id="paper-1", quote="Missing baseline", locator="url"))
    ledger.mark_supported(claim.id)

    ledger.add_counterevidence(claim.id, Evidence(source_id="paper-2", quote="Baseline exists", locator="url"))

    assert claim.status == "contested"
    assert claim.counter_evidence


def test_claim_queries_and_markdown_export() -> None:
    ledger = ClaimLedger()
    sourced = ledger.add_claim("Sourced but uncertain.", "background", created_by_skill="paper-triage")
    ledger.add_evidence(sourced.id, Evidence(source_id="paper-1", quote="Evidence", locator="url"))
    unsourced = ledger.add_claim("Unsourced claim.", "analogy", created_by_skill="cross-domain-analogy")
    ledger.mark_uncertain(unsourced.id)

    markdown = ledger.export_markdown()

    assert unsourced in ledger.claims_needing_verification()
    assert unsourced in ledger.claims_without_sources()
    assert "# Claim Ledger" in markdown
    assert "Unsourced claim." in markdown
    assert "### Counterevidence" in markdown
