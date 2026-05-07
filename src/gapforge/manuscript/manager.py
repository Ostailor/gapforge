"""Manager for durable manuscript project state."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript.models import (
    MANUSCRIPT_CLAIM_USE_TYPES,
    MANUSCRIPT_STATUSES,
    ManuscriptClaimUse,
    ManuscriptProject,
    ManuscriptSection,
    ManuscriptState,
)
from gapforge.manuscript.sections import build_section, next_section_id, render_section_stub, validate_section_status
from gapforge.manuscript.state import ManuscriptStateStore
from gapforge.models import Provenance, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso


class ManuscriptManager:
    """Create, persist, and report first-class manuscript project state."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)

    def create_manuscript(
        self,
        *,
        project_id: str,
        direction_id: str,
        workspace_id: str,
        title: str,
        campaign_id: str = "",
        short_title: str = "",
        target_venue: str = "",
    ) -> ManuscriptState:
        program = self.project_manager.load_project(project_id)
        manuscript_id = _unique_manuscript_id(Path(program.project.root_dir) / "manuscripts", title or direction_id)
        now = utc_now_iso()
        manuscript = ManuscriptProject(
            id=manuscript_id,
            project_id=project_id,
            campaign_id=campaign_id,
            direction_id=direction_id,
            workspace_id=workspace_id,
            title=title,
            short_title=short_title,
            target_venue=target_venue,
            status="planned",
            created_at=now,
            updated_at=now,
            provenance=Provenance(
                created_by_skill="manuscript-project",
                source_ids=[project_id, direction_id, workspace_id, campaign_id],
                timestamp=now,
                reasoning_summary=(
                    "Created first-class manuscript project state. This references project evidence but does not replace evidence state."
                ),
            ),
        )
        state = ManuscriptState(
            manuscript=manuscript,
            provenance=[
                Provenance(
                    created_by_skill="manuscript-project",
                    source_ids=[project_id, direction_id, workspace_id],
                    timestamp=now,
                    reasoning_summary="Initialized durable manuscript state under the project artifacts directory.",
                )
            ],
        )
        self._store_for_path(Path(program.project.root_dir) / "manuscripts" / manuscript_id).save(state)
        self._write_report_files(state)
        return state

    def manuscript_root(self, manuscript_id: str) -> Path:
        for project_dir in sorted(self.config.project_root.glob("*")):
            candidate = project_dir / "manuscripts" / manuscript_id
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"No manuscript found for {manuscript_id}")

    def load_state(self, manuscript_id: str) -> ManuscriptState:
        return self._store(manuscript_id).load()

    def create_section(
        self,
        *,
        manuscript_id: str,
        section_type: str,
        title: str = "",
        source_claim_ids: list[str] | None = None,
        source_paper_ids: list[str] | None = None,
        source_result_ids: list[str] | None = None,
        source_artifact_ids: list[str] | None = None,
        status: str = "missing",
        warnings: list[str] | None = None,
    ) -> ManuscriptSection:
        state = self.load_state(manuscript_id)
        section = build_section(
            manuscript_id=manuscript_id,
            section_id=next_section_id(state.sections, section_type),
            section_type=section_type,
            title=title,
            status=status,
            source_claim_ids=source_claim_ids,
            source_paper_ids=source_paper_ids,
            source_result_ids=source_result_ids,
            source_artifact_ids=source_artifact_ids,
            warnings=warnings,
        )
        state.sections.append(section)
        if state.manuscript.status == "planned":
            state.manuscript.status = "drafting"
        self._touch(state)
        self._save_state(state)
        section_path = self.manuscript_root(manuscript_id) / section.content_path
        if not section_path.exists():
            section_path.write_text(render_section_stub(section), encoding="utf-8")
        self._write_report_files(state)
        return section

    def link_claim_use(
        self,
        *,
        manuscript_id: str,
        section_id: str,
        claim_id: str,
        claim_text: str,
        use_type: str,
        support_status: str,
        evidence_locators: list[str] | None = None,
        citation_keys: list[str] | None = None,
        requires_softening: bool = False,
    ) -> ManuscriptClaimUse:
        if use_type not in MANUSCRIPT_CLAIM_USE_TYPES:
            allowed = ", ".join(sorted(MANUSCRIPT_CLAIM_USE_TYPES))
            raise ValueError(f"Unsupported manuscript claim use type: {use_type}. Expected one of: {allowed}")
        state = self.load_state(manuscript_id)
        section = _require_section(state, section_id)
        locators = _unique(evidence_locators or [])
        citations = _unique(citation_keys or [])
        now = utc_now_iso()
        claim_use = ManuscriptClaimUse(
            id=_unique_claim_use_id(state.claim_uses, section_id, claim_id),
            manuscript_id=manuscript_id,
            section_id=section_id,
            claim_id=claim_id,
            claim_text=claim_text,
            use_type=use_type,
            support_status=support_status,
            evidence_locators=locators,
            citation_keys=citations,
            requires_softening=requires_softening,
            provenance=Provenance(
                created_by_skill="manuscript-claim-use",
                source_ids=[manuscript_id, section_id, claim_id, *locators, *citations],
                timestamp=now,
                reasoning_summary="Linked a manuscript claim use to existing evidence and citation identifiers.",
            ),
        )
        state.claim_uses = _replace_claim_use(state.claim_uses, claim_use)
        section.source_claim_ids = _unique([*section.source_claim_ids, claim_id])
        section.source_paper_ids = _unique([*section.source_paper_ids, *_paper_ids_from_locators(locators)])
        if requires_softening:
            section.warnings = _unique([*section.warnings, f"Claim `{claim_id}` requires softening before submission use."])
        if section.status == "missing":
            section.status = "needs_review"
        self._touch(state)
        self._save_state(state)
        self._write_section_file(section)
        self._write_report_files(state)
        return claim_use

    def update_section_links(
        self,
        *,
        manuscript_id: str,
        section_id: str,
        source_claim_ids: list[str] | None = None,
        source_paper_ids: list[str] | None = None,
        source_result_ids: list[str] | None = None,
        source_artifact_ids: list[str] | None = None,
        status: str | None = None,
        warnings: list[str] | None = None,
    ) -> ManuscriptSection:
        state = self.load_state(manuscript_id)
        section = _require_section(state, section_id)
        if source_claim_ids is not None:
            section.source_claim_ids = _unique([*section.source_claim_ids, *source_claim_ids])
        if source_paper_ids is not None:
            section.source_paper_ids = _unique([*section.source_paper_ids, *source_paper_ids])
        if source_result_ids is not None:
            section.source_result_ids = _unique([*section.source_result_ids, *source_result_ids])
        if source_artifact_ids is not None:
            section.source_artifact_ids = _unique([*section.source_artifact_ids, *source_artifact_ids])
        if status is not None:
            section.status = validate_section_status(status)
        if warnings is not None:
            section.warnings = _unique([*section.warnings, *warnings])
        self._touch(state)
        self._save_state(state)
        self._write_section_file(section)
        self._write_report_files(state)
        return section

    def sections_json(self, manuscript_id: str) -> str:
        state = self.load_state(manuscript_id)
        return json.dumps(to_plain(state.sections), indent=2) + "\n"

    def status_markdown(self, manuscript_id: str) -> str:
        return render_status_markdown(self.load_state(manuscript_id))

    def report_markdown(self, manuscript_id: str) -> str:
        return render_report_markdown(self.load_state(manuscript_id))

    def write_report(self, manuscript_id: str) -> str:
        state = self.load_state(manuscript_id)
        report = render_report_markdown(state)
        root = self.manuscript_root(manuscript_id)
        (root / "submission" / "manuscript_report.md").write_text(report, encoding="utf-8")
        (root / "submission" / "manuscript_report.json").write_text(json.dumps(to_plain(state), indent=2) + "\n", encoding="utf-8")
        return report

    def _store(self, manuscript_id: str) -> ManuscriptStateStore:
        return self._store_for_path(self.manuscript_root(manuscript_id))

    def _store_for_path(self, root_dir: Path) -> ManuscriptStateStore:
        return ManuscriptStateStore(root_dir)

    def _save_state(self, state: ManuscriptState) -> None:
        if state.manuscript.status not in MANUSCRIPT_STATUSES:
            allowed = ", ".join(sorted(MANUSCRIPT_STATUSES))
            raise ValueError(f"Unsupported manuscript status: {state.manuscript.status}. Expected one of: {allowed}")
        self._store(state.manuscript.id).save(state)

    def _touch(self, state: ManuscriptState) -> None:
        state.manuscript.updated_at = utc_now_iso()

    def _write_section_file(self, section: ManuscriptSection) -> None:
        path = self.manuscript_root(section.manuscript_id) / section.content_path
        path.write_text(render_section_stub(section), encoding="utf-8")

    def _write_report_files(self, state: ManuscriptState) -> None:
        root = self.manuscript_root(state.manuscript.id)
        (root / "submission" / "status.md").write_text(render_status_markdown(state), encoding="utf-8")


def render_status_markdown(state: ManuscriptState) -> str:
    manuscript = state.manuscript
    lines = [
        f"# Manuscript Status `{manuscript.id}`",
        "",
        f"- Title: {manuscript.title}",
        f"- Project ID: `{manuscript.project_id}`",
        f"- Campaign ID: `{manuscript.campaign_id or 'none'}`",
        f"- Direction ID: `{manuscript.direction_id}`",
        f"- Workspace ID: `{manuscript.workspace_id or 'none'}`",
        f"- Target venue: {manuscript.target_venue or 'not set'}",
        f"- Status: `{manuscript.status}`",
        f"- Sections: {len(state.sections)}",
        f"- Claim uses: {len(state.claim_uses)}",
        "",
        "This manuscript is durable project state. It references evidence, result, and artifact IDs; it does not replace evidence state.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_report_markdown(state: ManuscriptState) -> str:
    manuscript = state.manuscript
    soften_count = sum(1 for item in state.claim_uses if item.requires_softening)
    unsupported = [item for item in state.claim_uses if item.support_status in {"unsupported", "uncertain", ""}]
    lines = [
        f"# Manuscript `{manuscript.id}`",
        "",
        f"- Title: {manuscript.title}",
        f"- Short title: {manuscript.short_title or 'not set'}",
        f"- Target venue: {manuscript.target_venue or 'not set'}",
        f"- Status: `{manuscript.status}`",
        f"- Sections: {len(state.sections)}",
        f"- Claim uses: {len(state.claim_uses)}",
        f"- Claims requiring softening: {soften_count}",
        "",
        "## Evidence Boundary",
        "",
        "Manuscript state stores trace links. It does not replace evidence state, result state, or artifact state.",
        "",
        "## Sections",
        "",
    ]
    if state.sections:
        for section in state.sections:
            lines.extend(
                [
                    f"### {section.title}",
                    "",
                    f"- ID: `{section.id}`",
                    f"- Type: `{section.section_type}`",
                    f"- Status: `{section.status}`",
                    f"- Claims: {', '.join(section.source_claim_ids) if section.source_claim_ids else 'none'}",
                    f"- Papers: {', '.join(section.source_paper_ids) if section.source_paper_ids else 'none'}",
                    f"- Results: {', '.join(section.source_result_ids) if section.source_result_ids else 'none'}",
                    f"- Artifacts: {', '.join(section.source_artifact_ids) if section.source_artifact_ids else 'none'}",
                    "",
                ]
            )
            if section.warnings:
                lines.extend(["Warnings:", *[f"- {warning}" for warning in section.warnings], ""])
    else:
        lines.extend(["No manuscript sections have been created.", ""])
    lines.extend(["## Claim Uses", ""])
    if state.claim_uses:
        for claim_use in state.claim_uses:
            soften = " requires softening" if claim_use.requires_softening else ""
            lines.extend(
                [
                    f"- `{claim_use.claim_id}` ({claim_use.use_type}, {claim_use.support_status}){soften}: {claim_use.claim_text}",
                ]
            )
    else:
        lines.append("No manuscript claim uses have been linked.")
    if unsupported:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- Claim `{item.claim_id}` is `{item.support_status or 'unsupported'}` in manuscript use." for item in unsupported)
    return "\n".join(lines).rstrip() + "\n"


def _unique_manuscript_id(base_dir: Path, title: str) -> str:
    base_dir.mkdir(parents=True, exist_ok=True)
    base = f"manuscript-{slugify(title)}"
    candidate = base
    suffix = 2
    while (base_dir / candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _require_section(state: ManuscriptState, section_id: str) -> ManuscriptSection:
    for section in state.sections:
        if section.id == section_id:
            return section
    raise FileNotFoundError(f"No manuscript section {section_id} in {state.manuscript.id}")


def _unique_claim_use_id(claim_uses: list[ManuscriptClaimUse], section_id: str, claim_id: str) -> str:
    ids = {item.id for item in claim_uses}
    base = f"claim-use-{slugify(section_id)}-{slugify(claim_id)}"
    candidate = base
    suffix = 2
    while candidate in ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _replace_claim_use(claim_uses: list[ManuscriptClaimUse], claim_use: ManuscriptClaimUse) -> list[ManuscriptClaimUse]:
    return [item for item in claim_uses if item.id != claim_use.id] + [claim_use]


def _paper_ids_from_locators(locators: list[str]) -> list[str]:
    paper_ids: list[str] = []
    for locator in locators:
        if ":" in locator:
            paper_ids.append(locator.split(":", 1)[0])
    return _unique(paper_ids)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
