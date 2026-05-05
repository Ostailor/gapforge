from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ingest import ManualIngestor
from gapforge.llm.base import LLMResponse
from gapforge.llm.transcripts import LLMTranscriptLogger
from gapforge.models import EvidenceSpan, SourceCoverageReport
from gapforge.project_memory import ProjectMemoryManager
from gapforge.redaction import redact_text
from gapforge.reporting import write_final_report
from gapforge.safety import audit_project_artifacts, audit_run_artifacts, export_safe_project_bundle
from gapforge.state import ResearchStateManager


def test_secret_redaction_common_patterns() -> None:
    text = "OPENAI_API_KEY=sk-testsecret1234567890 and Authorization: Bearer abcdefghijklmnop"

    redacted = redact_text(text)

    assert "sk-testsecret" not in redacted
    assert "abcdefghijklmnop" not in redacted
    assert "[REDACTED]" in redacted


def test_transcript_redacts_prompt_response_and_summary(tmp_path: Path) -> None:
    logger = LLMTranscriptLogger(tmp_path)

    logger.record(
        call_id="call-1",
        skill_name="test",
        model="fake",
        response_status="ok",
        prompt="Use api_key=sk-testsecret1234567890",
        response=LLMResponse(text="token: ghp_abcdefghijklmnopqrstuvwxyz123456", model="fake"),
        reasoning_summary="Authorization: Bearer abcdefghijklmnop",
    )

    raw = json.loads((tmp_path / "llm_transcripts.json").read_text(encoding="utf-8"))
    serialized = json.dumps(raw)
    assert "sk-testsecret" not in serialized
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in serialized
    assert "abcdefghijklmnop" not in serialized
    assert "[REDACTED]" in serialized


def test_report_redacts_secret_like_warnings(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = ResearchStateManager(config).create_run("secret report")
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        coverage_warnings=["OPENAI_API_KEY=sk-testsecret1234567890 leaked by caller"],
        confidence="low",
    )

    path = write_final_report(state)

    text = path.read_text(encoding="utf-8")
    assert "sk-testsecret" not in text
    assert "[REDACTED]" in text


def test_artifact_audit_flags_pdfs_and_transcripts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run("artifact audit")
    pdf = tmp_path / "audit.pdf"
    pdf.write_bytes(_tiny_pdf("Artifact audit PDF."))
    ManualIngestor(config).add_pdf(state, pdf, title="Audit PDF")
    LLMTranscriptLogger(state.run_dir).record(
        call_id="call-1",
        skill_name="test",
        model="fake",
        response_status="ok",
        prompt="secret=sk-testsecret1234567890",
        response=LLMResponse(text="ok", model="fake"),
    )
    manager.save_run(state)

    classifications = audit_run_artifacts(config, state.run_id)

    assert any(item.contains_user_pdf and not item.safe_to_commit for item in classifications)
    assert any(item.contains_model_transcript and not item.safe_to_commit for item in classifications)
    assert (Path(state.run_dir) / "artifacts_audit.md").exists()


def test_safe_bundle_excludes_pdfs_by_default_and_redacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    state = state_manager.create_run("safe bundle")
    pdf = tmp_path / "bundle.pdf"
    pdf.write_bytes(_tiny_pdf("Safe bundle PDF."))
    ManualIngestor(config).add_pdf(state, pdf, title="Bundle PDF")
    state.evidence_spans.append(
        EvidenceSpan(
            id="span-1",
            paper_id=state.papers[0].id,
            quote="Snippet with api_key=sk-testsecret1234567890",
            locator="p1:Abstract:p1",
        )
    )
    state_manager.save_run(state)
    program = project_manager.create_project("Safe Bundle Project")
    project_manager.attach_run(program.project.id, state.run_id)

    bundle = export_safe_project_bundle(config, program.project.id)

    assert bundle.exists()
    assert not list(bundle.rglob("*.pdf"))
    evidence = (bundle / "evidence_snippets.json").read_text(encoding="utf-8")
    assert "sk-testsecret" not in evidence
    assert "[REDACTED]" in evidence
    classifications = audit_project_artifacts(config, program.project.id)
    assert any(item.path.startswith("safe_bundles/") and not item.safe_to_commit for item in classifications)


def _tiny_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n",
        b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
        b"5 0 obj<< /Length " + str(len(stream)).encode() + b" >>stream\n" + stream + b"\nendstream\nendobj\n",
    ]
    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        body += f"{offset:010d} 00000 n \n".encode()
    body += f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return body
