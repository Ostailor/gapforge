"""Artifact-backed manuscript figure generation."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import ManuscriptFigure
from gapforge.manuscript.tables import (
    _artifact_backed_execution_ids,
    _asset_context,
    _execution_by_id,
    _load_assets,
    _next_asset_id,
    _unique,
)
from gapforge.models import Provenance, to_plain
from gapforge.results.parser import ResultParser
from gapforge.state import utc_now_iso

FIGURE_TYPES = {"metric_plot", "error_analysis", "comparison", "power_curve", "custom"}


class ManuscriptFigureGenerator:
    """Generate conservative figure artifacts from recorded result artifacts."""

    def __init__(self, config) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.result_parser = ResultParser(config)

    def generate(self, manuscript_id: str, figure_type: str) -> ManuscriptFigure:
        if figure_type not in FIGURE_TYPES:
            raise ValueError(f"Unsupported manuscript figure type: {figure_type}")
        state = self.manuscript_manager.load_state(manuscript_id)
        context = _asset_context(self.workspace_manager, self.result_parser, state)
        if not context.artifacts:
            raise ValueError("No result artifacts are available; manuscript figures cannot be generated.")
        figure_id = _next_asset_id(self.manuscript_manager.manuscript_root(manuscript_id) / "figures", figure_type)
        figure_path = Path("figures") / f"{figure_id}.svg"
        title = _figure_title(figure_type)
        caption = _caption(figure_type, context)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        (root / figure_path).write_text(_render_metric_svg(title, context), encoding="utf-8")
        figure = ManuscriptFigure(
            id=figure_id,
            manuscript_id=manuscript_id,
            title=title,
            caption=caption,
            source_artifact_ids=[artifact.id for artifact in context.artifacts],
            path=str(figure_path),
            figure_type=figure_type,
            status="generated",
            provenance=Provenance(
                created_by_skill="manuscript-figure",
                source_ids=[manuscript_id, *[artifact.id for artifact in context.artifacts]],
                timestamp=utc_now_iso(),
                reasoning_summary="Generated a manuscript figure from recorded metric/result artifacts; no results were invented.",
            ),
        )
        (root / "figures" / f"{figure.id}.json").write_text(json.dumps(to_plain(figure), indent=2) + "\n", encoding="utf-8")
        (root / "figures" / f"{figure.id}.md").write_text(_render_figure_markdown(figure), encoding="utf-8")
        state.figure_ids = _unique([*state.figure_ids, figure.id])
        self.manuscript_manager._save_state(state)
        return figure

    def list_figures(self, manuscript_id: str) -> list[ManuscriptFigure]:
        root = self.manuscript_manager.manuscript_root(manuscript_id) / "figures"
        return _load_assets(root, ManuscriptFigure)


def _render_metric_svg(title, context) -> str:
    values: list[tuple[str, float]] = []
    for summary in context.summaries:
        for metric in summary.metric_results:
            values.append((metric.metric_id[-18:] or metric.id[-8:], metric.value))
    if not values:
        values = [("failed", 0.0)]
    max_value = max([abs(value) for _label, value in values] + [1.0])
    width = 640
    height = 120 + 36 * len(values)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img" aria-label="{title}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="24" y="32" font-family="Arial" font-size="18" fill="#111">{_escape(title)}</text>',
    ]
    for index, (label, value) in enumerate(values):
        y = 68 + index * 34
        bar_width = int((abs(value) / max_value) * 360)
        lines.append(f'<text x="24" y="{y + 14}" font-family="Arial" font-size="12" fill="#222">{_escape(label)}</text>')
        lines.append(f'<rect x="190" y="{y}" width="{bar_width}" height="18" fill="#4267b2"/>')
        lines.append(f'<text x="{200 + bar_width}" y="{y + 14}" font-family="Arial" font-size="12" fill="#222">{value:g}</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _render_figure_markdown(figure: ManuscriptFigure) -> str:
    return (
        f"# {figure.title}\n\n"
        f"{figure.caption}\n\n"
        f"- Figure type: `{figure.figure_type}`\n"
        f"- Source artifacts: {', '.join(f'`{item}`' for item in figure.source_artifact_ids) or 'none'}\n"
        f"- Path: `{figure.path}`\n"
    )


def _caption(figure_type: str, context) -> str:
    executions = [_execution_by_id(context.executions, execution_id) for execution_id in _artifact_backed_execution_ids(context)]
    run_types = _unique([_run_type_from_manifest_id(execution.manifest_id) for execution in executions])
    return (
        f"Artifact-backed {figure_type.replace('_', ' ')} generated from recorded result artifacts. "
        f"Run type labels visible: {', '.join(run_types) or 'none'}. "
        "Smoke and pilot points are descriptive only and are not main-result evidence."
    )


def _figure_title(figure_type: str) -> str:
    return {
        "metric_plot": "Metric Plot",
        "error_analysis": "Error Analysis Figure",
        "comparison": "Comparison Figure",
        "power_curve": "Power Curve",
    }.get(figure_type, "Custom Figure")


def _run_type_from_manifest_id(manifest_id: str) -> str:
    for value in ("smoke", "pilot", "main", "ablation", "negative_control", "reproduction"):
        if value in manifest_id:
            return value
    return "unknown"


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
