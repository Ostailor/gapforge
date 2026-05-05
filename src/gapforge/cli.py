"""Command line interface for GapForge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.evals.benchmark import run_evals
from gapforge.models import ResearchRunState, to_plain
from gapforge.orchestrator import Orchestrator
from gapforge.reporting import write_final_report
from gapforge.sources.http_client import cache_summary
from gapforge.state import ResearchStateManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gapforge",
        description="GapForge: a skills-based research ideation OS for evidence-linked research gaps.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-topic", help="Create a durable run directory for a topic.")
    init_parser.add_argument("topic")

    run_parser = subparsers.add_parser("run", help="Run the full research loop and write final_report.md.")
    run_parser.add_argument("topic")
    run_parser.add_argument("--max-papers", type=int, default=50)
    run_parser.add_argument("--iterations", type=int, default=1)
    run_parser.add_argument("--sources", default="", help="Comma-separated sources, for example arxiv,crossref,dblp.")
    run_parser.add_argument("--dry-run", action="store_true")

    map_parser = subparsers.add_parser("map", help="Build a field map for a topic or existing run.")
    map_parser.add_argument("topic", nargs="?")
    map_parser.add_argument("--run-id", default=None)

    triage_parser = subparsers.add_parser("triage", help="Rank papers into reading-depth tiers.")
    triage_parser.add_argument("topic", nargs="?")
    triage_parser.add_argument("--run-id", default=None)
    triage_parser.add_argument("--max-tier1", type=int, default=20)

    read_parser = subparsers.add_parser("read", help="Create abstract-aware paper notes for selected papers.")
    read_parser.add_argument("--run-id", default=None)
    read_parser.add_argument("--tier", type=int, default=None)
    read_parser.add_argument("--paper-id", default=None)

    mine_parser = subparsers.add_parser("mine-gaps", help="Mine evidence-linked research gaps.")
    mine_parser.add_argument("--run-id", required=True)

    analogies_parser = subparsers.add_parser("analogies", help="Generate skeptical cross-domain analogy queries.")
    analogies_parser.add_argument("--run-id", required=True)

    novelty_parser = subparsers.add_parser("novelty-check", help="Check candidate gaps against closest prior work.")
    novelty_parser.add_argument("--run-id", default=None)
    novelty_parser.add_argument("--gap-id", default=None)

    design_all_parser = subparsers.add_parser("design-experiments", help="Convert non-rejected gaps into experiment plans.")
    design_all_parser.add_argument("--run-id", required=True)
    design_all_parser.add_argument("--allow-rejected", action="store_true")

    design_one_parser = subparsers.add_parser("design-experiment", help="Design an experiment for one gap.")
    design_one_parser.add_argument("--run-id", default=None)
    design_one_parser.add_argument("--gap-id", required=True)
    design_one_parser.add_argument("--allow-rejected", action="store_true")

    review_parser = subparsers.add_parser("review", help="Simulate serious conference-review objections.")
    review_parser.add_argument("--run-id", default=None)
    review_parser.add_argument("--experiment-id", default=None)

    resume_parser = subparsers.add_parser("resume", help="Resume a previously interrupted run.")
    resume_parser.add_argument("--run-id", required=True)

    status_parser = subparsers.add_parser("status", help="Print orchestrator status as JSON.")
    status_parser.add_argument("--run-id", required=True)

    search_parser = subparsers.add_parser("search", help="Search source connectors and write papers.json.")
    search_parser.add_argument("topic")
    search_parser.add_argument("--max-results", type=int, default=20)
    search_parser.add_argument("--sources", default="", help="Comma-separated sources, for example arxiv,crossref,dblp.")
    search_parser.add_argument("--newest-first", action="store_true", default=True)
    search_parser.add_argument("--date-from", default=None)
    search_parser.add_argument("--date-to", default=None)

    eval_parser = subparsers.add_parser("eval", help="Run offline fixture evaluations.")
    eval_parser.add_argument("--fixture", default=None)
    eval_parser.add_argument("--write-report", action="store_true")

    report_parser = subparsers.add_parser("report", help="Write final_report.md or final_report.json.")
    report_parser.add_argument("--run-id", default="latest", help="Run ID to report on, or 'latest' (default).")
    report_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")

    subparsers.add_parser("cache-info", help="Print source cache diagnostics as JSON.")
    subparsers.add_parser("show-state", help="Print latest state.json.")
    subparsers.add_parser("validate-state", help="Validate the latest run state.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = GapForgeConfig.from_env_or_cwd()
    orchestrator = Orchestrator(config)

    try:
        return _dispatch(args, config, orchestrator, parser)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"gapforge: error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("gapforge: interrupted", file=sys.stderr)
        return 130


def _dispatch(
    args: argparse.Namespace,
    config: GapForgeConfig,
    orchestrator: Orchestrator,
    parser: argparse.ArgumentParser,
) -> int:
    if args.command == "init-topic":
        state = orchestrator.init_topic(args.topic)
        print(state.run_dir)
        return 0
    if args.command == "search":
        state = orchestrator.search(
            args.topic,
            max_results=args.max_results,
            sources=_source_names(args.sources),
            newest_first=args.newest_first,
            date_from=args.date_from,
            date_to=args.date_to,
        )
        print(f"Wrote {len(state.papers)} papers to {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "map":
        if not args.topic and not args.run_id:
            parser.error("map requires a topic or --run-id")
        state = orchestrator.map_topic(args.topic, run_id=args.run_id)
        clusters = len(state.field_map.clusters) if state.field_map else 0
        print(f"Wrote field map with {clusters} clusters to {Path(state.run_dir) / 'field_map.md'}")
        return 0
    if args.command == "triage":
        if not args.topic and not args.run_id:
            parser.error("triage requires a topic or --run-id")
        state = orchestrator.triage(args.topic, run_id=args.run_id, max_tier1=args.max_tier1)
        decisions = len(state.paper_triage.decisions) if state.paper_triage else 0
        print(f"Wrote {decisions} triage decisions to {Path(state.run_dir) / 'paper_triage.md'}")
        return 0
    if args.command == "read":
        state = orchestrator.read(run_id=args.run_id, tier=args.tier, paper_id=args.paper_id)
        print(f"Wrote {len(state.paper_notes)} paper notes to {Path(state.run_dir) / 'paper_notes.md'}")
        return 0
    if args.command == "mine-gaps":
        state = orchestrator.mine_gaps(run_id=args.run_id)
        print(f"Wrote {len(state.gaps)} gap candidates to {Path(state.run_dir) / 'gaps.md'}")
        return 0
    if args.command == "analogies":
        state = orchestrator.analogies(run_id=args.run_id)
        print(f"Wrote {len(state.cross_domain_analogies)} analogies to {Path(state.run_dir) / 'cross_domain_analogies.md'}")
        return 0
    if args.command == "novelty-check":
        state = orchestrator.novelty_check(run_id=args.run_id, gap_id=args.gap_id)
        print(f"Wrote {len(state.novelty_assessments)} novelty assessments to {Path(state.run_dir) / 'novelty_gate.md'}")
        return 0
    if args.command == "design-experiments":
        state = orchestrator.design_experiments(run_id=args.run_id, allow_rejected=args.allow_rejected)
        print(f"Wrote {len(state.experiments)} experiments to {Path(state.run_dir) / 'experiments.md'}")
        return 0
    if args.command == "design-experiment":
        state = orchestrator.design_experiments(
            run_id=args.run_id,
            gap_id=args.gap_id,
            allow_rejected=args.allow_rejected,
        )
        print(f"Wrote {len(state.experiments)} experiments to {Path(state.run_dir) / 'experiments.md'}")
        return 0
    if args.command == "review":
        state = orchestrator.review(run_id=args.run_id, experiment_id=args.experiment_id)
        print(f"Wrote {len(state.reviewer_objections)} reviewer objections to {Path(state.run_dir) / 'reviewer_simulation.md'}")
        return 0
    if args.command == "run":
        state = orchestrator.run(
            args.topic,
            max_papers=args.max_papers,
            iterations=args.iterations,
            sources=_source_names(args.sources),
            dry_run=args.dry_run,
        )
        _print_run_result(state)
        return 0
    if args.command == "resume":
        state = orchestrator.resume(run_id=args.run_id)
        _print_run_result(state)
        return 0
    if args.command == "status":
        status_result = orchestrator.status(run_id=args.run_id)
        print(json.dumps(to_plain(status_result), indent=2))
        return 0
    if args.command == "eval":
        report = run_evals(fixture=args.fixture, output_dir=config.root, write_report=True)
        target = report.report_path or (config.root / "eval_report.md")
        print(f"Wrote evaluation report to {target}")
        print(f"Overall score: {report.overall_score:.3f}")
        return 0
    if args.command == "report":
        state = _load_report_state(config, args.run_id)
        path = write_final_report(state, output_format=args.format)
        print(f"Wrote final report to {path}")
        return 0
    if args.command == "cache-info":
        print(json.dumps(cache_summary(config.cache_dir), indent=2))
        return 0
    if args.command == "show-state":
        raw = ResearchStateManager(config).load_latest_raw()
        print(json.dumps(raw or {"message": "No run state found."}, indent=2))
        return 0
    if args.command == "validate-state":
        validation_result = ResearchStateManager(config).validate_latest()
        if validation_result.ok:
            print("State is valid: no validation issues found.")
            return 0
        print("State is invalid:")
        for issue in validation_result.issues:
            target_text = f" [{issue.object_id}]" if issue.object_id else ""
            print(f"- {issue.severity.upper()} {issue.code}{target_text}: {issue.message}")
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


def _source_names(raw: str) -> list[str] | None:
    return [name.strip() for name in raw.split(",") if name.strip()] if raw else None


def _load_report_state(config: GapForgeConfig, run_id: str) -> ResearchRunState:
    manager = ResearchStateManager(config)
    if run_id == "latest":
        state = manager.load_latest()
        if state is None:
            raise FileNotFoundError('No run state found. Start with `gapforge run "your topic"`.')
        return state
    return manager.load_run(run_id)


def _print_run_result(state: ResearchRunState) -> None:
    status = state.orchestrator_result.status if state.orchestrator_result else "unknown"
    report_path = Path(state.run_dir) / "final_report.md"
    suffix = f" Report: {report_path}" if report_path.exists() else ""
    print(f"{_status_verb(status)} run {state.run_id} in {state.run_dir}.{suffix}")


def _status_verb(status: str) -> str:
    return {
        "complete": "Completed",
        "planned": "Planned",
        "interrupted": "Interrupted",
        "failed": "Failed",
        "running": "Running",
    }.get(status, status.capitalize())


if __name__ == "__main__":
    raise SystemExit(main())
