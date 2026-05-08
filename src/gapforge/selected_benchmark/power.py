"""Low-FPR power and binomial interval helpers for selected benchmarks."""

from __future__ import annotations

import math

DEFAULT_CONFIDENCE = 0.95


def exact_binomial_confidence_interval(successes: int, total: int, *, alpha: float = 0.05) -> list[float]:
    """Return a deterministic Clopper-Pearson style interval for a binomial rate."""

    if total <= 0:
        return []
    bounded = min(max(successes, 0), total)
    if bounded == 0:
        lower = 0.0
    else:
        lower = _bisect_for_tail(bounded, total, alpha / 2, lower_tail=False)
    if bounded == total:
        upper = 1.0
    else:
        upper = _bisect_for_tail(bounded, total, alpha / 2, lower_tail=True)
    return [max(0.0, lower), min(1.0, upper)]


def zero_false_positive_upper_bound(negative_count: int, *, alpha: float = 0.05) -> float:
    """Return the one-sided exact upper bound when zero false positives are observed."""

    if negative_count <= 0:
        return 1.0
    return 1 - alpha ** (1 / negative_count)


def required_negative_count_for_zero_fp_bound(target_alpha: float, *, confidence: float = DEFAULT_CONFIDENCE) -> int:
    """Negative traces needed for a zero-FP upper bound at or below target_alpha."""

    if target_alpha <= 0 or target_alpha >= 1:
        raise ValueError("target_alpha must be between 0 and 1.")
    miss_probability = 1 - confidence
    return math.ceil(math.log(miss_probability) / math.log(1 - target_alpha))


def underpowered_low_fpr_warnings(
    *,
    run_type: str,
    negative_trace_count: int,
    target_alpha_levels: list[float],
    confidence: float = DEFAULT_CONFIDENCE,
) -> list[str]:
    warnings: list[str] = []
    if run_type == "smoke":
        warnings.append("Smoke results are underpowered and cannot support strong low-FPR claims.")
    for target in target_alpha_levels:
        required = required_negative_count_for_zero_fp_bound(target, confidence=confidence)
        if negative_trace_count < required:
            warnings.append(
                f"Low-FPR claim at alpha={target:g} is underpowered: {negative_trace_count} negative traces observed, "
                f"{required} required for a zero-FP upper bound at {confidence:.0%} confidence."
            )
    return warnings


def _bisect_for_tail(successes: int, total: int, target: float, *, lower_tail: bool) -> float:
    lo = 0.0
    hi = 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        probability = _binomial_cdf(successes, total, mid) if lower_tail else _binomial_survival(successes, total, mid)
        if lower_tail:
            if probability > target:
                lo = mid
            else:
                hi = mid
        elif probability > target:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def _binomial_cdf(successes: int, total: int, probability: float) -> float:
    return sum(_binomial_pmf(k, total, probability) for k in range(successes + 1))


def _binomial_survival(successes: int, total: int, probability: float) -> float:
    return sum(_binomial_pmf(k, total, probability) for k in range(successes, total + 1))


def _binomial_pmf(successes: int, total: int, probability: float) -> float:
    if probability <= 0:
        return 1.0 if successes == 0 else 0.0
    if probability >= 1:
        return 1.0 if successes == total else 0.0
    return math.comb(total, successes) * (probability**successes) * ((1 - probability) ** (total - successes))
