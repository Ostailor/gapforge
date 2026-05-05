"""Command line interface for GapForge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.evals.benchmark import run_evals
from gapforge.fulltext.downloader import PdfDownloader
from gapforge.fulltext.pdf_parser import FullTextParser
from gapforge.ingest import ManualIngestor, parse_authors
from gapforge.models import ResearchRunState, to_plain
from gapforge.orchestrator import Orchestrator
from gapforge.reporting import write_final_report
from gapforge.review.audit import render_human_reviews_markdown
from gapforge.review.edits import HumanReviewEditor
from gapforge.sources.coverage import refresh_source_coverage
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
    run_parser.add_argument("--v2", action="store_true", help="Use the v0.2 full-text and prior-work orchestration loop.")
    run_parser.add_argument("--download-pdfs", action="store_true", help="Include PDF download before deep reading.")
    run_parser.add_argument("--parse-fulltext", action="store_true", help="Include full-text parsing before deep reading.")
    run_parser.add_argument("--deep-novelty", action="store_true", help="Run closest-prior-work dossiers instead of shallow novelty.")
    run_parser.add_argument("--strict-report", action="store_true", help="Use strict final-report recommendation gating.")
    run_parser.add_argument("--skip-pdf-download", action="store_true", help="Skip v0.2 PDF download while recording coverage warnings.")
    run_parser.add_argument("--max-expanded-papers", type=int, default=30)

    map_parser = subparsers.add_parser("map", help="Build a field map for a topic or existing run.")
    map_parser.add_argument("topic", nargs="?")
    map_parser.add_argument("--run-id", default=None)

    triage_parser = subparsers.add_parser("triage", help="Rank papers into reading-depth tiers.")
    triage_parser.add_argument("topic", nargs="?")
    triage_parser.add_argument("--run-id", default=None)
    triage_parser.add_argument("--max-tier1", type=int, default=20)

    rank_parser = subparsers.add_parser("rank-papers", help="Rank papers with v0.2 role and diversity scoring.")
    rank_parser.add_argument("--run-id", required=True)
    rank_parser.add_argument("--query-purpose", default="initial_topic")
    rank_parser.add_argument("--recency-preference", choices=["newest", "canonical"], default="newest")
    rank_parser.add_argument("--source-diversity-target", type=int, default=2)
    rank_parser.add_argument("--role-diversity-target", type=int, default=2)

    read_parser = subparsers.add_parser("read", help="Create abstract-aware paper notes for selected papers.")
    read_parser.add_argument("--run-id", default=None)
    read_parser.add_argument("--tier", type=int, default=None)
    read_parser.add_argument("--paper-id", default=None)
    read_parser.add_argument("--fulltext-only", action="store_true")
    read_parser.add_argument("--allow-abstract-only", action=argparse.BooleanOptionalAction, default=True)

    mine_parser = subparsers.add_parser("mine-gaps", help="Mine evidence-linked research gaps.")
    mine_parser.add_argument("--run-id", required=True)
    mine_parser.add_argument("--min-confidence", choices=["low", "medium", "high"], default="low")
    mine_parser.add_argument("--include-low-confidence", action="store_true")
    mine_parser.add_argument("--force", action="store_true", help="Overwrite locked generated gap artifacts.")

    analogies_parser = subparsers.add_parser("analogies", help="Generate skeptical cross-domain analogy queries.")
    analogies_parser.add_argument("--run-id", required=True)
    analogies_parser.add_argument("--search", action="store_true")
    analogies_parser.add_argument("--promote-evidence-only", action="store_true")

    novelty_parser = subparsers.add_parser("novelty-check", help="Check candidate gaps against closest prior work.")
    novelty_parser.add_argument("--run-id", default=None)
    novelty_parser.add_argument("--gap-id", default=None)
    novelty_parser.add_argument("--deep", action="store_true")

    novelty_dossier_parser = subparsers.add_parser("novelty-dossier", help="Write or refresh a closest-prior-work dossier.")
    novelty_dossier_parser.add_argument("--run-id", required=True)
    novelty_dossier_parser.add_argument("--gap-id", required=True)

    design_all_parser = subparsers.add_parser("design-experiments", help="Convert non-rejected gaps into experiment plans.")
    design_all_parser.add_argument("--run-id", required=True)
    design_all_parser.add_argument("--allow-rejected", action="store_true")
    design_all_parser.add_argument("--force", action="store_true", help="Overwrite locked generated experiment artifacts.")

    design_one_parser = subparsers.add_parser("design-experiment", help="Design an experiment for one gap.")
    design_one_parser.add_argument("--run-id", default=None)
    design_one_parser.add_argument("--gap-id", required=True)
    design_one_parser.add_argument("--allow-rejected", action="store_true")
    design_one_parser.add_argument("--force", action="store_true", help="Overwrite locked generated experiment artifacts.")

    review_parser = subparsers.add_parser("review", help="Simulate serious conference-review objections.")
    review_parser.add_argument("--run-id", default=None)
    review_parser.add_argument("--experiment-id", default=None)

    download_parser = subparsers.add_parser("download-pdfs", help="Download available PDFs for papers in a run.")
    download_parser.add_argument("--run-id", required=True)
    download_parser.add_argument("--paper-id", default=None)
    download_parser.add_argument("--max-papers", type=int, default=None)
    download_parser.add_argument("--skip-existing", action="store_true")

    parse_parser = subparsers.add_parser("parse-fulltext", help="Extract PDF text and sectionize available paper artifacts.")
    parse_parser.add_argument("--run-id", required=True)
    parse_parser.add_argument("--paper-id", default=None)

    add_paper_parser = subparsers.add_parser("add-paper", help="Manually add or merge paper metadata into a run.")
    add_paper_parser.add_argument("--run-id", required=True)
    add_paper_parser.add_argument("--title", required=True)
    add_paper_parser.add_argument("--authors", default="")
    add_paper_parser.add_argument("--year", type=int, default=0)
    add_paper_parser.add_argument("--url", default="")
    add_paper_parser.add_argument("--pdf-url", default="")
    add_paper_parser.add_argument("--doi", default="")
    add_paper_parser.add_argument("--arxiv-id", default="")

    add_arxiv_parser = subparsers.add_parser("add-arxiv", help="Add or merge a paper by arXiv ID.")
    add_arxiv_parser.add_argument("--run-id", required=True)
    add_arxiv_parser.add_argument("arxiv_id")

    add_doi_parser = subparsers.add_parser("add-doi", help="Add or merge a paper by DOI.")
    add_doi_parser.add_argument("--run-id", required=True)
    add_doi_parser.add_argument("doi")

    add_pdf_parser = subparsers.add_parser("add-pdf", help="Add a local PDF artifact and optional metadata.")
    add_pdf_parser.add_argument("--run-id", required=True)
    add_pdf_parser.add_argument("pdf_path")
    add_pdf_parser.add_argument("--title", default="")
    add_pdf_parser.add_argument("--authors", default="")
    add_pdf_parser.add_argument("--year", type=int, default=0)
    add_pdf_parser.add_argument("--parse", action="store_true")

    add_url_parser = subparsers.add_parser("add-url", help="Add an arbitrary URL as manually supplied metadata.")
    add_url_parser.add_argument("--run-id", required=True)
    add_url_parser.add_argument("url")

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
    eval_parser.add_argument("--v2", action="store_true", help="Run v0.2 full-text/evidence/dossier evaluation fixtures.")
    eval_parser.add_argument("--write-report", action="store_true")

    report_parser = subparsers.add_parser("report", help="Write final_report.md or final_report.json.")
    report_parser.add_argument("--run-id", default="latest", help="Run ID to report on, or 'latest' (default).")
    report_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    report_parser.add_argument(
        "--strict",
        action="store_true",
        help="Refuse to recommend a top direction when coverage/evidence/novelty gates are weak.",
    )

    coverage_parser = subparsers.add_parser("coverage", help="Regenerate source and full-text coverage reports.")
    coverage_parser.add_argument("--run-id", default="latest", help="Run ID to cover, or 'latest' (default).")

    graph_parser = subparsers.add_parser("build-citation-graph", help="Build citation graph from available paper metadata.")
    graph_parser.add_argument("--run-id", required=True)

    expand_parser = subparsers.add_parser("expand-related-work", help="Run conservative citation/related-work expansion searches.")
    expand_parser.add_argument("--run-id", required=True)
    expand_parser.add_argument("--max-new-papers", type=int, default=30)
    expand_parser.add_argument("--paper-id", default=None)

    list_gaps_parser = subparsers.add_parser("list-gaps", help="List gap candidates with human review status.")
    list_gaps_parser.add_argument("--run-id", required=True)

    approve_gap_parser = subparsers.add_parser("approve-gap", help="Record a human approval for a gap.")
    approve_gap_parser.add_argument("--run-id", required=True)
    approve_gap_parser.add_argument("--gap-id", required=True)
    approve_gap_parser.add_argument("--note", default="")
    approve_gap_parser.add_argument("--reviewer", default="human")

    reject_gap_parser = subparsers.add_parser("reject-gap", help="Record a human rejection for a gap.")
    reject_gap_parser.add_argument("--run-id", required=True)
    reject_gap_parser.add_argument("--gap-id", required=True)
    reject_gap_parser.add_argument("--reason", required=True)
    reject_gap_parser.add_argument("--reviewer", default="human")

    annotate_claim_parser = subparsers.add_parser("annotate-claim", help="Attach a human note to a claim.")
    annotate_claim_parser.add_argument("--run-id", required=True)
    annotate_claim_parser.add_argument("--claim-id", required=True)
    annotate_claim_parser.add_argument("--note", required=True)
    annotate_claim_parser.add_argument("--reviewer", default="human")

    mark_claim_parser = subparsers.add_parser("mark-claim", help="Change a claim status with an audit record.")
    mark_claim_parser.add_argument("--run-id", required=True)
    mark_claim_parser.add_argument("--claim-id", required=True)
    mark_claim_parser.add_argument("--status", choices=["supported", "contested", "uncertain", "falsified"], required=True)
    mark_claim_parser.add_argument("--reviewer", default="human")

    add_evidence_parser = subparsers.add_parser("add-evidence", help="Add manual evidence to a claim.")
    add_evidence_parser.add_argument("--run-id", required=True)
    add_evidence_parser.add_argument("--claim-id", required=True)
    add_evidence_parser.add_argument("--paper-id", required=True)
    add_evidence_parser.add_argument("--quote", required=True)
    add_evidence_parser.add_argument("--locator", default="")
    add_evidence_parser.add_argument("--reviewer", default="human")

    lock_object_parser = subparsers.add_parser("lock-object", help="Lock or unlock a reviewed object against automated overwrite.")
    lock_object_parser.add_argument("--run-id", required=True)
    lock_object_parser.add_argument("--object-type", required=True)
    lock_object_parser.add_argument("--object-id", required=True)
    lock_object_parser.add_argument("--note", default="")
    lock_object_parser.add_argument("--reviewer", default="human")
    lock_object_parser.add_argument("--unlock", action="store_true")
    lock_object_parser.add_argument("--force", action="store_true")

    audit_log_parser = subparsers.add_parser("audit-log", help="Print the human review audit log.")
    audit_log_parser.add_argument("--run-id", required=True)

    prompt_pack_parser = subparsers.add_parser("prompt-pack", help="Write a Codex-readable prompt pack for an optional LLM skill.")
    prompt_pack_parser.add_argument("--run-id", required=True)
    prompt_pack_parser.add_argument("--skill", required=True, choices=["deep-reading", "gap-mining", "novelty-gate", "reviewer-simulation"])
    prompt_pack_parser.add_argument("--gap-id", default=None)

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
    if args.command == "rank-papers":
        state = orchestrator.rank_papers_v2(
            run_id=args.run_id,
            query_purpose=args.query_purpose,
            recency_preference=args.recency_preference,
            source_diversity_target=args.source_diversity_target,
            role_diversity_target=args.role_diversity_target,
        )
        ranked = len(state.paper_ranking.decisions) if state.paper_ranking else 0
        print(f"Wrote {ranked} ranked papers to {Path(state.run_dir) / 'paper_ranking.md'}")
        return 0
    if args.command == "read":
        state = orchestrator.read(
            run_id=args.run_id,
            tier=args.tier,
            paper_id=args.paper_id,
            fulltext_only=args.fulltext_only,
            allow_abstract_only=args.allow_abstract_only,
        )
        print(f"Wrote {len(state.paper_notes)} paper notes to {Path(state.run_dir) / 'paper_notes.md'}")
        return 0
    if args.command == "mine-gaps":
        state = orchestrator.mine_gaps(
            run_id=args.run_id,
            min_confidence=args.min_confidence,
            include_low_confidence=args.include_low_confidence or args.min_confidence == "low",
            force=args.force,
        )
        print(f"Wrote {len(state.gaps)} gap candidates to {Path(state.run_dir) / 'gaps.md'}")
        return 0
    if args.command == "analogies":
        state = orchestrator.analogies(
            run_id=args.run_id,
            search=args.search,
            promote_evidence_only=args.promote_evidence_only,
        )
        print(f"Wrote {len(state.cross_domain_analogies)} analogies to {Path(state.run_dir) / 'cross_domain_analogies.md'}")
        return 0
    if args.command == "novelty-check":
        state = orchestrator.novelty_check(run_id=args.run_id, gap_id=args.gap_id, deep=args.deep)
        print(f"Wrote {len(state.novelty_assessments)} novelty assessments to {Path(state.run_dir) / 'novelty_gate.md'}")
        return 0
    if args.command == "novelty-dossier":
        state = orchestrator.novelty_check(run_id=args.run_id, gap_id=args.gap_id, deep=True)
        print(f"Wrote {len(state.novelty_dossiers)} novelty dossiers to {Path(state.run_dir) / 'novelty_dossiers.md'}")
        return 0
    if args.command == "design-experiments":
        state = orchestrator.design_experiments(run_id=args.run_id, allow_rejected=args.allow_rejected, force=args.force)
        print(f"Wrote {len(state.experiments)} experiments to {Path(state.run_dir) / 'experiments.md'}")
        return 0
    if args.command == "design-experiment":
        state = orchestrator.design_experiments(
            run_id=args.run_id,
            gap_id=args.gap_id,
            allow_rejected=args.allow_rejected,
            force=args.force,
        )
        print(f"Wrote {len(state.experiments)} experiments to {Path(state.run_dir) / 'experiments.md'}")
        return 0
    if args.command == "review":
        state = orchestrator.review(run_id=args.run_id, experiment_id=args.experiment_id)
        print(f"Wrote {len(state.reviewer_objections)} reviewer objections to {Path(state.run_dir) / 'reviewer_simulation.md'}")
        return 0
    if args.command == "download-pdfs":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        artifacts = PdfDownloader(config.cache_dir).download_for_state(
            state,
            paper_id=args.paper_id,
            max_papers=args.max_papers,
            skip_existing=args.skip_existing,
        )
        manager.save_run(state)
        available = sum(1 for artifact in artifacts if artifact.status == "available")
        failed = sum(1 for artifact in artifacts if artifact.status == "failed")
        skipped = sum(1 for artifact in artifacts if artifact.status == "skipped")
        print(
            f"PDF download complete: {available} available, {failed} failed, {skipped} skipped. "
            f"Coverage: {Path(state.run_dir) / 'full_text_coverage.md'}"
        )
        return 0
    if args.command == "parse-fulltext":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        sections = FullTextParser().parse_for_state(state, paper_id=args.paper_id)
        manager.save_run(state)
        print(
            f"Parsed {len(sections)} paper sections. "
            f"Sections: {Path(state.run_dir) / 'paper_sections.json'} Coverage: {Path(state.run_dir) / 'full_text_coverage.md'}"
        )
        return 0
    if args.command == "add-paper":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        paper = ManualIngestor(config).add_paper(
            state,
            title=args.title,
            authors=parse_authors(args.authors),
            year=args.year,
            url=args.url,
            pdf_url=args.pdf_url,
            doi=args.doi,
            arxiv_id=args.arxiv_id,
        )
        manager.save_run(state)
        print(f"Added paper {paper.id}. Papers: {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "add-arxiv":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        paper = ManualIngestor(config).add_arxiv(state, args.arxiv_id)
        manager.save_run(state)
        print(f"Added arXiv paper {paper.id}. Papers: {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "add-doi":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        paper = ManualIngestor(config).add_doi(state, args.doi)
        manager.save_run(state)
        print(f"Added DOI paper {paper.id}. Papers: {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "add-pdf":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        title = args.title or Path(args.pdf_path).stem
        paper, artifact = ManualIngestor(config).add_pdf(
            state,
            Path(args.pdf_path),
            title=title,
            authors=parse_authors(args.authors),
            year=args.year,
            parse=args.parse,
        )
        manager.save_run(state)
        print(f"Added PDF artifact {artifact.id} for {paper.id}. Artifacts: {Path(state.run_dir) / 'paper_artifacts.json'}")
        return 0
    if args.command == "add-url":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        paper = ManualIngestor(config).add_url(state, args.url)
        manager.save_run(state)
        print(f"Added URL paper {paper.id}. Papers: {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "run":
        state = orchestrator.run(
            args.topic,
            max_papers=args.max_papers,
            iterations=args.iterations,
            sources=_source_names(args.sources),
            dry_run=args.dry_run,
            v2=args.v2,
            download_pdfs=args.download_pdfs,
            parse_fulltext=args.parse_fulltext,
            deep_novelty=args.deep_novelty,
            strict_report=args.strict_report,
            skip_pdf_download=args.skip_pdf_download,
            max_expanded_papers=args.max_expanded_papers,
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
        report = run_evals(fixture=args.fixture, output_dir=config.root, write_report=True, v2=args.v2)
        target = report.report_path or (config.root / "eval_report.md")
        print(f"Wrote evaluation report to {target}")
        print(f"Overall score: {report.overall_score:.3f}")
        return 0
    if args.command == "report":
        state = _load_report_state(config, args.run_id)
        path = write_final_report(state, output_format=args.format, strict=args.strict)
        print(f"Wrote final report to {path}")
        return 0
    if args.command == "coverage":
        manager = ResearchStateManager(config)
        coverage_state = manager.load_latest() if args.run_id == "latest" else manager.load_run(args.run_id)
        if coverage_state is None:
            raise FileNotFoundError('No run state found. Start with `gapforge run "your topic"`.')
        refresh_source_coverage(coverage_state, [str(item) for item in coverage_state.config.get("_coverage_warnings", []) if str(item)])
        manager.save_run(coverage_state)
        print(
            f"Wrote coverage reports to {Path(coverage_state.run_dir) / 'source_coverage.md'} "
            f"and {Path(coverage_state.run_dir) / 'full_text_coverage.md'}"
        )
        return 0
    if args.command == "build-citation-graph":
        state = orchestrator.build_citation_graph(run_id=args.run_id)
        graph = state.citation_graph
        edge_count = len(graph.edges) if graph else 0
        unresolved = len(graph.unresolved_references) if graph else 0
        print(
            f"Wrote citation graph with {edge_count} edges and {unresolved} unresolved references "
            f"to {Path(state.run_dir) / 'citation_graph.md'}"
        )
        return 0
    if args.command == "expand-related-work":
        before = len(ResearchStateManager(config).load_run(args.run_id).papers)
        state = orchestrator.expand_related_work(
            run_id=args.run_id,
            max_new_papers=args.max_new_papers,
            paper_id=args.paper_id,
        )
        added = max(0, len(state.papers) - before)
        print(f"Expanded related work with {added} new paper(s). Report: {Path(state.run_dir) / 'related_work_expansion.md'}")
        return 0
    if args.command == "list-gaps":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        print(_format_gap_list(state))
        return 0
    if args.command == "approve-gap":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().approve_gap(state, args.gap_id, note=args.note, reviewer=args.reviewer)
        manager.save_run(state)
        print(f"Approved gap {args.gap_id}; audit record {record.id}.")
        return 0
    if args.command == "reject-gap":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().reject_gap(state, args.gap_id, reason=args.reason, reviewer=args.reviewer)
        manager.save_run(state)
        print(f"Rejected gap {args.gap_id}; audit record {record.id}.")
        return 0
    if args.command == "annotate-claim":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().annotate_claim(state, args.claim_id, note=args.note, reviewer=args.reviewer)
        manager.save_run(state)
        print(f"Annotated claim {args.claim_id}; audit record {record.id}.")
        return 0
    if args.command == "mark-claim":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().mark_claim(state, args.claim_id, status=args.status, reviewer=args.reviewer)
        manager.save_run(state)
        print(f"Marked claim {args.claim_id} as {args.status}; audit record {record.id}.")
        return 0
    if args.command == "add-evidence":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().add_evidence(
            state,
            args.claim_id,
            paper_id=args.paper_id,
            quote=args.quote,
            locator=args.locator,
            reviewer=args.reviewer,
        )
        manager.save_run(state)
        print(f"Added evidence to claim {args.claim_id}; audit record {record.id}.")
        return 0
    if args.command == "lock-object":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        editor = HumanReviewEditor()
        if args.unlock:
            record = editor.unlock_object(
                state,
                args.object_type,
                args.object_id,
                note=args.note,
                reviewer=args.reviewer,
            )
            verb = "Unlocked"
        else:
            record = editor.lock_object(
                state,
                args.object_type,
                args.object_id,
                note=args.note,
                reviewer=args.reviewer,
                force=args.force,
            )
            verb = "Locked"
        manager.save_run(state)
        print(f"{verb} {args.object_type}:{args.object_id}; audit record {record.id}.")
        return 0
    if args.command == "audit-log":
        state = ResearchStateManager(config).load_run(args.run_id)
        print(render_human_reviews_markdown(state), end="")
        return 0
    if args.command == "prompt-pack":
        path = orchestrator.write_prompt_pack(run_id=args.run_id, skill_name=args.skill, gap_id=args.gap_id)
        print(f"Wrote prompt pack to {path}")
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


def _format_gap_list(state: ResearchRunState) -> str:
    from gapforge.review.audit import is_locked, is_rejected, latest_action

    if not state.gaps:
        return "No gaps recorded."
    lines = [f"Gaps for {state.run_id}:"]
    for gap in state.gaps:
        action = latest_action(state, "gap", gap.id) or "unreviewed"
        markers = []
        if is_rejected(state, "gap", gap.id):
            markers.append("rejected")
        if is_locked(state, "gap", gap.id):
            markers.append("locked")
        marker_text = f" [{', '.join(markers)}]" if markers else ""
        lines.append(f"- {gap.id}: {gap.title or gap.description} ({gap.confidence}, {gap.novelty_status}, review={action}){marker_text}")
    return "\n".join(lines)


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
