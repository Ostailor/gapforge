"""Build and render project-level claim graphs."""

from __future__ import annotations

from datetime import UTC, datetime

from gapforge.claims.contradiction import contradiction_reason
from gapforge.claims.entailment import are_duplicate_claims, normalize_claim_text
from gapforge.models import Claim, ClaimEdge, ClaimGraph, ClaimNode, Provenance, ResearchRunState


class ClaimGraphBuilder:
    """Sync run-level claim ledgers into cumulative project claim graphs."""

    def build(
        self,
        *,
        project_id: str,
        runs: list[ResearchRunState],
        existing: ClaimGraph | None = None,
    ) -> ClaimGraph:
        graph = existing or ClaimGraph(project_id=project_id, provenance=_provenance("claim-graph", [], "Claim graph initialized."))
        nodes = list(graph.nodes)
        edges = [edge for edge in graph.edges if edge.relation not in {"duplicates", "contradicts"}]
        for state in runs:
            span_ids_by_claim = _span_ids_by_claim(state)
            for claim in state.claims:
                candidate = _node_from_claim(project_id, state, claim, span_ids_by_claim)
                duplicate = _find_duplicate(nodes, candidate)
                if duplicate is None:
                    nodes.append(candidate)
                else:
                    contradiction = contradiction_reason(duplicate.text, candidate.text)
                    if contradiction:
                        nodes.append(candidate)
                        edges.append(
                            ClaimEdge(
                                source_claim_id=duplicate.id,
                                target_claim_id=candidate.id,
                                relation="contradicts",
                                confidence="medium",
                                evidence=[contradiction],
                                provenance=_provenance(
                                    "claim-contradiction",
                                    [duplicate.id, candidate.id],
                                    "Deterministic contradiction rule overrode duplicate merging.",
                                ),
                            )
                        )
                    else:
                        _merge_node(duplicate, candidate)
                        edges.append(
                            ClaimEdge(
                                source_claim_id=candidate.id,
                                target_claim_id=duplicate.id,
                                relation="duplicates",
                                confidence="high",
                                evidence=[f"{candidate.text} ~= {duplicate.text}"],
                                provenance=_provenance(
                                    "claim-graph",
                                    [candidate.id, duplicate.id],
                                    "Merged near-identical run-level claims into one project claim node.",
                                ),
                            )
                        )
        edges.extend(_contradiction_edges(nodes))
        graph.nodes = sorted(nodes, key=lambda node: node.id)
        graph.edges = _dedupe_edges(edges)
        graph.unresolved_contradictions = _unresolved_contradictions(graph)
        graph.provenance = _provenance("claim-graph", [run.run_id for run in runs], "Project claim graph rebuilt from attached runs.")
        return graph


def render_claim_graph_markdown(graph: ClaimGraph) -> str:
    lines = [
        f"# Project Claim Graph: {graph.project_id}",
        "",
        f"- Nodes: {len(graph.nodes)}",
        f"- Edges: {len(graph.edges)}",
        f"- Unresolved contradictions: {len(graph.unresolved_contradictions)}",
        "",
        "## Claims",
        "",
    ]
    for node in graph.nodes:
        lines.extend(
            [
                f"- `{node.id}` {node.text}",
                f"  - type={node.claim_type}; status={node.status}; confidence={node.confidence}",
                f"  - runs={', '.join(node.run_ids) or 'none'}; papers={', '.join(node.source_paper_ids) or 'none'}",
            ]
        )
    if not graph.nodes:
        lines.append("- none")
    lines.extend(["", "## Edges", ""])
    for edge in graph.edges:
        lines.append(
            f"- `{edge.source_claim_id}` {edge.relation} `{edge.target_claim_id}` "
            f"({edge.confidence}): {'; '.join(edge.evidence) or 'no evidence note'}"
        )
    if not graph.edges:
        lines.append("- none")
    lines.extend(["", "## Unresolved Contradictions", ""])
    lines.extend([f"- {item}" for item in graph.unresolved_contradictions] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _node_from_claim(
    project_id: str,
    state: ResearchRunState,
    claim: Claim,
    span_ids_by_claim: dict[str, list[str]],
) -> ClaimNode:
    return ClaimNode(
        id=f"claim-node-{_stable_suffix(project_id, claim.text)}",
        project_id=project_id,
        text=claim.text,
        normalized_text=normalize_claim_text(claim.text),
        claim_type=claim.type,
        status=claim.status,
        confidence=claim.confidence,
        linked_claim_ids=[claim.id],
        supporting_evidence_span_ids=span_ids_by_claim.get(claim.id, []),
        counterevidence_span_ids=[],
        source_paper_ids=claim.source_paper_ids,
        run_ids=[state.run_id],
        provenance=_provenance("claim-graph", [state.run_id, claim.id], "Claim node synced from run-level claim ledger."),
    )


def _span_ids_by_claim(state: ResearchRunState) -> dict[str, list[str]]:
    spans_by_paper = {span.paper_id: span.id for span in state.evidence_spans}
    result: dict[str, list[str]] = {}
    for claim in state.claims:
        ids = [spans_by_paper[paper_id] for paper_id in claim.source_paper_ids if paper_id in spans_by_paper]
        result[claim.id] = ids
    return result


def _find_duplicate(nodes: list[ClaimNode], candidate: ClaimNode) -> ClaimNode | None:
    for node in nodes:
        if are_duplicate_claims(node.text, candidate.text):
            return node
    return None


def _merge_node(existing: ClaimNode, candidate: ClaimNode) -> None:
    existing.linked_claim_ids = _unique([*existing.linked_claim_ids, *candidate.linked_claim_ids])
    existing.supporting_evidence_span_ids = _unique([*existing.supporting_evidence_span_ids, *candidate.supporting_evidence_span_ids])
    existing.counterevidence_span_ids = _unique([*existing.counterevidence_span_ids, *candidate.counterevidence_span_ids])
    existing.source_paper_ids = _unique([*existing.source_paper_ids, *candidate.source_paper_ids])
    existing.run_ids = _unique([*existing.run_ids, *candidate.run_ids])
    existing.confidence = _max_confidence(existing.confidence, candidate.confidence)
    if existing.status != "falsified" and candidate.status in {"supported", "contested", "falsified"}:
        existing.status = candidate.status


def _contradiction_edges(nodes: list[ClaimNode]) -> list[ClaimEdge]:
    edges: list[ClaimEdge] = []
    for index, left in enumerate(nodes):
        for right in nodes[index + 1 :]:
            reason = contradiction_reason(left.text, right.text)
            if not reason:
                continue
            edges.append(
                ClaimEdge(
                    source_claim_id=left.id,
                    target_claim_id=right.id,
                    relation="contradicts",
                    confidence="medium",
                    evidence=[reason],
                    provenance=_provenance(
                        "claim-contradiction",
                        [left.id, right.id],
                        "Deterministic contradiction rule matched project claim pair.",
                    ),
                )
            )
    return edges


def _unresolved_contradictions(graph: ClaimGraph) -> list[str]:
    resolved_pairs = {
        tuple(sorted([edge.source_claim_id, edge.target_claim_id])) for edge in graph.edges if edge.relation in {"supersedes", "refines"}
    }
    unresolved: list[str] = []
    for edge in graph.edges:
        if edge.relation != "contradicts":
            continue
        pair = tuple(sorted([edge.source_claim_id, edge.target_claim_id]))
        if pair not in resolved_pairs:
            unresolved.append(f"{edge.source_claim_id} contradicts {edge.target_claim_id}: {'; '.join(edge.evidence)}")
    return _unique(unresolved)


def _dedupe_edges(edges: list[ClaimEdge]) -> list[ClaimEdge]:
    deduped: dict[tuple[str, str, str], ClaimEdge] = {}
    for edge in edges:
        key = (edge.source_claim_id, edge.target_claim_id, edge.relation)
        if key not in deduped:
            deduped[key] = edge
        else:
            deduped[key].evidence = _unique([*deduped[key].evidence, *edge.evidence])
    return sorted(deduped.values(), key=lambda edge: (edge.relation, edge.source_claim_id, edge.target_claim_id))


def _max_confidence(left: str, right: str) -> str:
    rank = {"low": 1, "medium": 2, "high": 3}
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


def _stable_suffix(*parts: str) -> str:
    import hashlib

    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]


def _provenance(skill: str, source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill=skill,
        source_ids=source_ids,
        timestamp=datetime.now(UTC).isoformat(),
        reasoning_summary=summary,
    )


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
