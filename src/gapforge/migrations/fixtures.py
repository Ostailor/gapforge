"""Historical migration fixtures used by compatibility tests and CLI audits."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.manuscript.models import ManuscriptState
from gapforge.models import ExperimentWorkspace, PilotRunRecord, ResearchCampaign, ResearchProject, ResearchRunState, from_dict

FIXTURE_ROOT = Path("tests") / "fixtures" / "migrations"


@dataclass(slots=True)
class HistoricalMigrationFixture:
    id: str
    version: str
    object_type: str
    path: str
    primary_json: str
    description: str = ""
    expected_warnings: list[str] = field(default_factory=list)
    generated_paths: list[str] = field(default_factory=list)
    safe_to_commit: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HistoricalFixtureLoadResult:
    fixture: HistoricalMigrationFixture
    loaded_object_id: str
    detected_version: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture": self.fixture.to_dict(),
            "loaded_object_id": self.loaded_object_id,
            "detected_version": self.detected_version,
            "warnings": self.warnings,
        }


def fixture_root(config: GapForgeConfig) -> Path:
    return config.root / FIXTURE_ROOT


def list_historical_migration_fixtures(config: GapForgeConfig) -> list[HistoricalMigrationFixture]:
    root = fixture_root(config)
    if not root.exists():
        return []
    fixtures: list[HistoricalMigrationFixture] = []
    for manifest_path in sorted(root.glob("*/manifest.json")):
        payload = _load_json(manifest_path)
        primary_json = str(payload.get("primary_json", ""))
        fixtures.append(
            HistoricalMigrationFixture(
                id=str(payload.get("id") or manifest_path.parent.name),
                version=str(payload.get("version", "unknown")),
                object_type=str(payload.get("object_type", "unknown")),
                path=str(manifest_path.parent.relative_to(config.root)),
                primary_json=primary_json,
                description=str(payload.get("description", "")),
                expected_warnings=[str(item) for item in payload.get("expected_warnings", []) if isinstance(item, str)],
                generated_paths=[str(item) for item in payload.get("generated_paths", []) if isinstance(item, str)],
                safe_to_commit=payload.get("safe_to_commit") is not False,
            )
        )
    return fixtures


def load_historical_migration_fixture(config: GapForgeConfig, fixture: HistoricalMigrationFixture) -> HistoricalFixtureLoadResult:
    root = config.root / fixture.path
    primary_path = root / fixture.primary_json
    payload = _load_json(primary_path)
    warnings = list(fixture.expected_warnings)
    object_id = fixture.id
    if fixture.object_type == "run":
        state = ResearchRunState.from_dict(_run_load_payload(payload, primary_path.parent.name, primary_path.parent))
        object_id = state.run_id
        warnings.extend(_missing_artifact_warnings(root, payload))
    elif fixture.object_type == "project":
        project = from_dict(ResearchProject, _project_load_payload(payload, primary_path.parent.name, primary_path.parent))
        object_id = project.id
    elif fixture.object_type == "campaign":
        campaign = from_dict(ResearchCampaign, payload)
        object_id = campaign.id
    elif fixture.object_type == "workspace":
        workspace = from_dict(ExperimentWorkspace, payload)
        object_id = workspace.id
        warnings.extend(_missing_artifact_warnings(root, payload))
    elif fixture.object_type == "manuscript":
        manuscript_state = from_dict(ManuscriptState, payload)
        object_id = manuscript_state.manuscript.id
        warnings.extend(_missing_artifact_warnings(root, payload))
    elif fixture.object_type == "pilot":
        pilot = from_dict(PilotRunRecord, payload)
        object_id = pilot.id
    else:
        raise ValueError(f"Unsupported migration fixture object type: {fixture.object_type}")
    return HistoricalFixtureLoadResult(
        fixture=fixture,
        loaded_object_id=object_id,
        detected_version=_fixture_version(payload, fixture.version),
        warnings=_dedupe(warnings),
    )


def render_migration_fixtures_list(fixtures: list[HistoricalMigrationFixture]) -> str:
    lines = ["# GapForge Historical Migration Fixtures", ""]
    if not fixtures:
        lines.append("- none")
        return "\n".join(lines).rstrip() + "\n"
    for fixture in fixtures:
        lines.extend(
            [
                f"## `{fixture.id}`",
                "",
                f"- Version: `{fixture.version}`",
                f"- Object type: `{fixture.object_type}`",
                f"- Primary JSON: `{fixture.path}/{fixture.primary_json}`",
                f"- Safe to commit: {str(fixture.safe_to_commit).lower()}",
                f"- Description: {fixture.description or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} JSON root is not an object")
    return payload


def _project_load_payload(payload: dict[str, Any], project_id: str, project_dir: Path) -> dict[str, Any]:
    updated = dict(payload)
    updated.setdefault("id", project_id)
    updated.setdefault("name", project_id)
    updated.setdefault("root_dir", str(project_dir))
    return updated


def _run_load_payload(payload: dict[str, Any], run_id: str, run_dir: Path) -> dict[str, Any]:
    updated = dict(payload)
    updated.setdefault("run_id", run_id)
    updated.setdefault("topic", {"text": run_id, "slug": run_id, "created_at": ""})
    updated.setdefault("run_dir", str(run_dir))
    updated.setdefault("config", {})
    return updated


def _fixture_version(payload: dict[str, Any], fallback: str) -> str:
    config = payload.get("config", {})
    if not isinstance(config, dict):
        config = {}
    return str(
        config.get("gapforge_version")
        or payload.get("gapforge_version")
        or payload.get("storage_version")
        or payload.get("version")
        or fallback
    )


def _missing_artifact_warnings(root: Path, payload: object) -> list[str]:
    warnings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"local_path", "path", "artifact_path"} and isinstance(value, str) and value:
                path = root / value
                if not path.exists():
                    warnings.append(f"missing artifact reference `{value}`")
            else:
                warnings.extend(_missing_artifact_warnings(root, value))
    elif isinstance(payload, list):
        for item in payload:
            warnings.extend(_missing_artifact_warnings(root, item))
    return warnings


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
