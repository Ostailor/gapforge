# v0.3 Canary Runs

Canary runs are private/manual validation runs that exercise GapForge with real Codex/GPT-5.4 assistance and human review. They are release gates, not CI tests.

## Canary Principles

- Never fake a canary pass.
- Never present canary output as exhaustive literature review.
- Do not commit private PDFs, source cache, transcripts, or generated runs.
- Use `gapforge audit-artifacts` before sharing any bundle.
- Record human review decisions in state or project memory.

## Required Canary A: Codex/GPT-5.4 Literature Run

Purpose: validate actual LLM-assisted research skills.

Minimum workflow:

```bash
gapforge init-project "v0.3 canary research"
gapforge run "low false positive collusion detection" --v3 --project-id v0-3-canary-research --build-index --source-profile ai_safety
run_id=$(ls -td runs/* | head -1 | xargs basename)
GAPFORGE_LLM_MODE=prompt-pack gapforge read-llm --run-id "$run_id" --tier 1 --dry-run-prompts
# Execute the prompts with Codex/GPT-5.4 using the private/manual workflow.
gapforge novelty-check --run-id "$run_id" --deep
gapforge report --run-id "$run_id" --strict
gapforge review-queue --run-id "$run_id"
```

Acceptance checks:

- LLM-assisted outputs are grounded in known paper IDs and locators where available.
- No unsupported high-confidence claims.
- Novelty dossiers include closest prior work or `unknown`.
- Strict report does not overclaim.
- Human review records are saved.

## Required Canary B: Local PDF Full-Text Run

Purpose: validate artifact ingestion, parsing, evidence spans, and full-text-aware reading.

Minimum workflow:

```bash
gapforge init-topic "private local PDF full text canary"
run_id=$(ls -td runs/* | head -1 | xargs basename)
gapforge add-pdf --run-id "$run_id" /path/to/allowed-paper.pdf --title "Paper Title" --authors "A;B" --year 2024 --parse
gapforge parse-structure --run-id "$run_id"
gapforge read --run-id "$run_id" --fulltext-only
gapforge mine-gaps --run-id "$run_id"
gapforge novelty-check --run-id "$run_id" --deep
gapforge report --run-id "$run_id" --strict
```

Acceptance checks:

- `paper_artifacts.json` records the PDF with hash and local path.
- `paper_sections.json` contains parsed sections or clear parser warnings.
- Full-text claims cite EvidenceSpan locators.
- Missing sections and extraction limitations are visible.
- Strict report remains conservative.

## Optional Canary C: Direction Maturation and Export

Purpose: validate project-level workflow from gap to package.

Minimum workflow:

```bash
gapforge sync-project-memory --project-id <project-id>
gapforge create-direction --project-id <project-id> --gap-id <gap-id>
gapforge related-work-matrix --project-id <project-id> --direction-id <direction-id>
gapforge mature-direction --project-id <project-id> --direction-id <direction-id>
gapforge experiment-protocol --project-id <project-id> --direction-id <direction-id>
gapforge review-panel --project-id <project-id> --direction-id <direction-id>
gapforge export-paper-package --project-id <project-id> --direction-id <direction-id>
```

Acceptance checks:

- Direction maturity is evidence-gated.
- Paper package does not contain fake results.
- Bibliography uses known metadata only.
- Missing requirements remain visible.

## Canary Record Template

```text
Canary ID:
Date:
Operator:
Codex/GPT-5.4 available: yes/no
Topic:
Project ID:
Run IDs:
LLM mode:
Local PDFs used:
Commands:
Artifacts inspected:
Human reviewer:
Pass/fail:
Blocking issues:
Notes:
```

If Codex/GPT-5.4 is unavailable, mark the canary as not run. Do not substitute fake LLM or prompt-pack mode for Level 4.

## Latest Canary Execution Notes

Date: May 5, 2026.

`fake_agent_regression` was executed offline and completed successfully. It validates AgentClient task-pack and schema plumbing only; it does not count as actual Codex/GPT-5.4 research validation.

`low_fpr_collusion_codex` and `manual_pdf_fulltext_codex` were planned and then recorded as failed/not passed because the required real-run environment was unavailable:

```bash
GAPFORGE_ENABLE_REAL_RUNS=
GAPFORGE_AGENT_MODE=
GAPFORGE_AGENT_NAME=
GAPFORGE_CODEX_MODEL=
```

Human review records rejected those canaries for this pass. `gapforge real-run-acceptance` correctly reported that no human-reviewed actual Codex/GPT-5.4 canary has been accepted.
