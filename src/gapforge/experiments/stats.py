"""Statistical recommendation helpers for experiment protocols."""

from __future__ import annotations


def statistical_tests_for_metrics(metrics: list[str]) -> list[str]:
    tests = ["bootstrap confidence intervals for primary metrics", "paired permutation test against strongest baseline"]
    normalized = " ".join(metrics).lower()
    if any(term in normalized for term in ["false-positive", "false positive", "fpr", "precision", "recall", "specificity"]):
        tests.extend(
            [
                "exact/binomial-style confidence intervals for alert-level proportions",
                "McNemar or paired proportion test for detector disagreement at fixed alert budgets",
            ]
        )
    if any(term in normalized for term in ["auc", "roc", "ranking"]):
        tests.append("paired bootstrap comparison for ranking metrics")
    if any(term in normalized for term in ["runtime", "latency", "memory", "throughput"]):
        tests.append("median and interquartile range across repeated runs")
    return _dedupe(tests)


def power_or_sample_size_notes(metrics: list[str], datasets: list[str]) -> str:
    text = " ".join([*metrics, *datasets]).lower()
    if any(term in text for term in ["false-positive", "false positive", "fpr", "specificity"]):
        return (
            "For low-FPR claims, predefine the alert budget and report exact/binomial-style intervals. "
            "Use enough negative examples for the target FPR; very low rates need large negative pools or a clearly scoped pilot claim."
        )
    if "runtime" in text or "latency" in text:
        return "Run at least 5 repeated measurements per condition and report median, IQR, and hardware."
    return "Predefine minimum detectable effect, run multiple seeds, and report uncertainty rather than only point estimates."


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
