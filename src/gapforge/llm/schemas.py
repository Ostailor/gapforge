"""Schema contracts for optional LLM prompt packs."""

from __future__ import annotations

from typing import Any

SCHEMAS: dict[str, dict[str, Any]] = {
    "deep-reading": {
        "type": "object",
        "required": ["paper_notes", "claims", "evidence_spans", "limitations"],
        "properties": {
            "paper_notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["paper_id", "source_basis", "confidence", "core_claims", "main_results", "evidence_locators"],
                    "properties": {
                        "paper_id": {"type": "string"},
                        "source_basis": {"type": "string", "enum": ["full text", "metadata/abstract only"]},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                        "sections_used": {"type": "array", "items": {"type": "string"}},
                        "missing_sections": {"type": "array", "items": {"type": "string"}},
                        "core_claims": {"type": "array", "items": {"type": "string"}},
                        "method": {"type": "array", "items": {"type": "string"}},
                        "datasets": {"type": "array", "items": {"type": "string"}},
                        "metrics": {"type": "array", "items": {"type": "string"}},
                        "main_results": {"type": "array", "items": {"type": "string"}},
                        "limitations": {"type": "array", "items": {"type": "string"}},
                        "evidence_locators": {"type": "array", "items": {"type": "string"}},
                        "reasoning_summary": {"type": "string"},
                    },
                },
            },
            "claims": {"type": "array", "items": {"type": "object"}},
            "evidence_spans": {"type": "array", "items": {"type": "object"}},
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
    },
    "gap-mining": {
        "type": "object",
        "required": ["gaps", "claim_updates", "limitations"],
        "properties": {
            "gaps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "title",
                        "type",
                        "description",
                        "supporting_evidence",
                        "risk_that_gap_is_fake",
                        "counterevidence_search_summary",
                        "confidence",
                    ],
                    "properties": {
                        "title": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "supporting_evidence": {"type": "array", "items": {"type": "string"}},
                        "supporting_locators": {"type": "array", "items": {"type": "string"}},
                        "counterevidence": {"type": "array", "items": {"type": "string"}},
                        "counterevidence_locators": {"type": "array", "items": {"type": "string"}},
                        "counterevidence_search_summary": {"type": "string"},
                        "minimum_experiment_needed": {"type": "string"},
                        "why_existing_work_does_not_solve_it": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "possible_research_questions": {"type": "array", "items": {"type": "string"}},
                        "explicit_reason": {"type": "string"},
                        "novelty_status": {"type": "string"},
                        "risk_that_gap_is_fake": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                        "reasoning_summary": {"type": "string"},
                    },
                },
            },
            "claim_updates": {"type": "array", "items": {"type": "object"}},
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
    },
    "novelty-gate": {
        "type": "object",
        "required": ["target_id", "closest_prior_work", "verdict", "novelty_strength", "missing_searches", "reasoning_summary"],
        "properties": {
            "target_id": {"type": "string"},
            "closest_prior_work": {"type": "array", "items": {"type": "string"}},
            "comparison_table": {"type": "array", "items": {"type": "object"}},
            "what_is_new": {"type": "array", "items": {"type": "string"}},
            "what_is_not_new": {"type": "array", "items": {"type": "string"}},
            "possible_reviewer_objection": {"type": "string"},
            "decisive_difference_needed": {"type": "string"},
            "missing_searches": {"type": "array", "items": {"type": "string"}},
            "verdict": {"type": "string", "enum": ["reject", "revise", "pursue", "unknown"]},
            "novelty_strength": {"type": "string", "enum": ["weak", "medium", "strong", "unknown"]},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "reasoning_summary": {"type": "string"},
        },
    },
    "novelty-comparison": {
        "type": "object",
        "required": [
            "target_id",
            "closest_prior_work",
            "comparison_table",
            "verdict",
            "novelty_strength",
            "missing_searches",
            "reasoning_summary",
        ],
        "properties": {
            "target_id": {"type": "string"},
            "closest_prior_work": {"type": "array", "items": {"type": "string"}},
            "comparison_table": {"type": "array", "items": {"type": "object"}},
            "what_is_new": {"type": "array", "items": {"type": "string"}},
            "what_is_not_new": {"type": "array", "items": {"type": "string"}},
            "possible_reviewer_objection": {"type": "string"},
            "decisive_difference_needed": {"type": "string"},
            "missing_searches": {"type": "array", "items": {"type": "string"}},
            "verdict": {"type": "string", "enum": ["reject", "revise", "pursue", "unknown"]},
            "novelty_strength": {"type": "string", "enum": ["weak", "medium", "strong", "unknown"]},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "reasoning_summary": {"type": "string"},
        },
    },
    "reviewer-simulation": {
        "type": "object",
        "required": ["objections", "submission_readiness_score", "final_recommendation", "reasoning_summary"],
        "properties": {
            "objections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["severity", "category", "objection", "suggested_fix", "blocks_submission"],
                    "properties": {
                        "severity": {"type": "string", "enum": ["minor", "major", "fatal"]},
                        "category": {"type": "string"},
                        "objection": {"type": "string"},
                        "evidence_or_prior_work": {"type": "array", "items": {"type": "string"}},
                        "suggested_fix": {"type": "string"},
                        "blocks_submission": {"type": "boolean"},
                    },
                },
            },
            "submission_readiness_score": {"type": "integer"},
            "final_recommendation": {
                "type": "string",
                "enum": ["not_ready", "workshop_ready", "conference_potential", "strong_submission_candidate"],
            },
            "reasoning_summary": {"type": "string"},
        },
    },
}


def schema_for(schema_name: str) -> dict[str, Any]:
    if schema_name not in SCHEMAS:
        raise KeyError(f"Unknown LLM output schema: {schema_name}")
    return SCHEMAS[schema_name]
