"""Runner and persistence for v0.5 real-literature campaign profiles."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.models import (
    Provenance,
    RealLiteratureCampaignProfile,
    RealLiteratureCampaignRecord,
    ResearchRunState,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.real_literature.acceptance import evaluate_real_literature_record
from gapforge.real_literature.profiles import (
    default_real_literature_profiles,
    get_real_literature_profile,
    render_real_literature_plan,
)
from gapforge.sources.base import ResearchSource
from gapforge.sources.live_diagnostics import (
    render_live_source_diagnostic_markdown,
    run_live_source_diagnostic,
    write_live_source_diagnostic,
)
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso


class RealLiteratureCampaignManager:
    """Manage live-literature campaign quality profiles and records."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.root = self.config.data_dir / "real_literature"
        self.root.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[RealLiteratureCampaignProfile]:
        return default_real_literature_profiles()

    def plan(self, profile_id: str) -> str:
        return render_real_literature_plan(get_real_literature_profile(profile_id))

    def run(
        self,
        profile_id: str,
        *,
        sources: Iterable[ResearchSource] | None = None,
        run_ids: list[str] | None = None,
    ) -> RealLiteratureCampaignRecord:
        profile = get_real_literature_profile(profile_id)
        diagnostic = run_live_source_diagnostic(self.config, topic=profile.topic, source_profile=profile.source_profile, sources=sources)
        write_live_source_diagnostic(self.config, diagnostic)
        project = ProjectMemoryManager(self.config).create_project(f"real literature {profile.id}")
        campaign_state = CampaignManager(self.config).create_campaign(
            profile.topic,
            project_id=project.project.id,
            title=profile.title,
            mode="codex_task_pack",
            agent_name="codex",
            model="gpt-5.4",
            source_profile=profile.source_profile,
            budget_id="medium",
        )
        loaded_runs = _load_runs(self.config, run_ids or [])
        record = RealLiteratureCampaignRecord(
            id=f"real-lit-{profile.id}-{utc_now_compact()}",
            profile_id=profile.id,
            campaign_id=campaign_state.campaign.id,
            project_id=project.project.id,
            run_ids=[state.run_id for state in loaded_runs],
            live_source_diagnostic_id=diagnostic.id,
            real_paper_count=_diagnostic_real_paper_count(diagnostic),
            fallback_paper_count=_diagnostic_fallback_paper_count(diagnostic),
            provenance=Provenance(
                created_by_skill="real-literature-runner",
                source_ids=[diagnostic.id, campaign_state.campaign.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a v0.5 real-literature campaign record from live source diagnostics.",
            ),
        )
        record = evaluate_real_literature_record(profile, diagnostic, record, runs=loaded_runs)
        self.save_record(record, profile=profile, diagnostic_markdown=render_live_source_diagnostic_markdown(diagnostic))
        return record

    def load_record(self, record_id: str) -> RealLiteratureCampaignRecord:
        path = self._record_path(record_id)
        if not path.exists():
            raise FileNotFoundError(f"No real-literature campaign record found for {record_id}")
        return from_dict(RealLiteratureCampaignRecord, json.loads(path.read_text(encoding="utf-8")))

    def save_record(
        self,
        record: RealLiteratureCampaignRecord,
        *,
        profile: RealLiteratureCampaignProfile | None = None,
        diagnostic_markdown: str = "",
    ) -> Path:
        record_dir = self._record_dir(record.id)
        record_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(to_plain(record), indent=2) + "\n"
        (record_dir / "record.json").write_text(payload, encoding="utf-8")
        (record_dir / "real_literature_campaign_record.json").write_text(payload, encoding="utf-8")
        if profile is not None:
            (record_dir / "plan.md").write_text(render_real_literature_plan(profile), encoding="utf-8")
        if diagnostic_markdown:
            (record_dir / "live_source_diagnostic.md").write_text(diagnostic_markdown, encoding="utf-8")
        return record_dir / "record.json"

    def _record_dir(self, record_id: str) -> Path:
        return self.root / record_id

    def _record_path(self, record_id: str) -> Path:
        return self._record_dir(record_id) / "record.json"


def _load_runs(config: GapForgeConfig, run_ids: list[str]) -> list[ResearchRunState]:
    manager = ResearchStateManager(config)
    runs: list[ResearchRunState] = []
    for run_id in run_ids:
        runs.append(manager.load_run(run_id))
    return runs


def _diagnostic_real_paper_count(diagnostic) -> int:
    return sum(check.result_count for check in diagnostic.source_health_checks if check.status == "healthy")


def _diagnostic_fallback_paper_count(diagnostic) -> int:
    count = 0
    for check in diagnostic.source_health_checks:
        if check.status == "degraded" and "fallback" in f"{check.warning} {check.error}".lower():
            count += check.result_count
    return count


def real_literature_record_summary(record: RealLiteratureCampaignRecord) -> str:
    status = "accepted" if record.accepted else "not accepted"
    lines = [
        f"# Real Literature Campaign Record: {record.id}",
        "",
        f"- Profile: `{record.profile_id}`",
        f"- Campaign: `{record.campaign_id}`",
        f"- Project: `{record.project_id}`",
        f"- Live source diagnostic: `{record.live_source_diagnostic_id}`",
        f"- Status: {status}",
        f"- Real papers: {record.real_paper_count}",
        f"- Fallback papers: {record.fallback_paper_count}",
        f"- Full-text papers: {record.full_text_count}",
        f"- Abstract-only notes: {record.abstract_only_count}",
        f"- Novelty dossiers: {record.novelty_dossier_count}",
    ]
    if record.rejection_reason:
        lines.extend(["", "## Rejection Reason", "", record.rejection_reason])
    return "\n".join(lines).rstrip() + "\n"
