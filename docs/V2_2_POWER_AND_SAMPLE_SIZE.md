# GapForge v2.2 Power and Sample-Size Plan

v2.2 low-FPR claims are power-gated. The pilot must define what sample size can and cannot support before monitor outputs are inspected.

## Core Rule

The benchmark may report observed false-positive counts at any size, but it may claim a low false-positive rate only when the honest negative sample size, sequential correction, and uncertainty interval support that claim.

Zero false positives is not proof of operational specificity. It is an estimate with an upper confidence bound.

## Claim Levels

| Claim Level | Minimum Evidence | Allowed Language |
| --- | --- | --- |
| Smoke wiring | small deterministic fixtures | metrics computed; no low-FPR evidence |
| Pilot exploratory | expanded negatives, hard negatives, full baselines, uncertainty | pilot estimate within stated uncertainty |
| Pilot powered for target | sample size supports the target alpha after correction | low-FPR claim for that target only |
| Main benchmark | locked version, sufficient sample size, replication and review | benchmark-level specificity claim with uncertainty |

## Required Inputs

The pilot power report must record:

- target per-window specificity
- target sequence-level specificity
- requested alpha claims, including any `0.001` target
- honest trace count
- hard-negative trace count
- audit windows per trace
- effective number of looks after sequential correction
- confidence level
- acceptable upper confidence bound for false-positive rate
- expected false-positive base rate
- minimum detectable sensitivity difference, if comparing monitors
- planned handling for abstentions and malformed windows

## Negative Count Gate

For a false-positive rate target `p`, the pilot must have enough honest negative evidence to make the upper confidence bound meaningful after repeated-look correction.

Practical release rules:

- If the pilot observes zero false positives, report an upper confidence bound rather than `FPR = 0`.
- If the upper confidence bound is above the target `p`, the target is unsupported.
- If sequential windows are correlated, use a conservative effective sample size or report the correlation limitation.
- If hard negatives are underrepresented, do not generalize specificity beyond ordinary negatives.

For `alpha=0.001`, the pilot must not claim operational specificity unless the negative count and corrected uncertainty bound support that target. If they do not, the report must say `unsupported_alpha_0_001`.

## Sequential Correction

The pilot must account for repeated audit windows:

- per-window false positives
- per-trace false positives
- family-wise false-alarm probability
- time-to-first-false-alarm
- number of looks per trace
- stopping rule
- window overlap and dependency assumptions

If exact correction is unavailable, use a conservative correction and mark the result as approximate.

## Hard-Negative Power

Hard negatives require separate reporting:

- hard-negative trace count
- hard-negative window count
- hard-negative false positives
- hard-negative upper confidence bound
- hard-negative families covered and missing

An ordinary-negative specificity result cannot be used as evidence that the monitor handles hard negatives.

## Sensitivity Comparison Gate

Monitor comparison claims require:

- fixed monitor thresholds before outcome inspection
- same pilot traces for compared monitors
- uncertainty for sensitivity estimates
- minimum detectable difference or explicit underpowered status
- multiple-comparison warning when many monitors are compared

If the pilot is not powered for monitor comparisons, the report may discuss failure modes but must not claim superiority.

## Required Classifications

Every low-FPR target must be classified:

- `supported`: sample size and uncertainty support the stated target
- `underpowered`: artifacts exist, but uncertainty is too wide
- `unsupported`: required data or correction is missing
- `not_requested`: target was not part of the locked manifest

Every result table must include the classification next to the metric.

## Pilot Failure Conditions

The pilot power gate fails when:

- sample-size targets are chosen after seeing results
- the report omits confidence intervals or uncertainty bands
- sequential correction is missing
- `alpha=0.001` is claimed from underpowered evidence
- hard-negative specificity is inferred without hard-negative counts
- monitor superiority is claimed without comparison power
- synthetic pilot data is described as deployment evidence

## Main Benchmark Handoff

The v2.2 power report must list what the main benchmark still needs:

- larger honest negative counts for target alpha levels
- broader hard-negative families
- independently reviewed scenario design
- fixed baselines and thresholds
- replication package
- prior-work and related-work gate completion

For the selected benchmark, `alpha=0.01` is the intended pilot target when the honest/null negative count and confidence bound support it. `alpha=0.001` is main-scale by default and must remain blocked unless the observed negative count and corrected upper bound support it. Reporting zero false positives at pilot scale is allowed only with the upper confidence bound and the underpowered-target table.

## v2.3 Power Questions

v2.3 must answer the questions that v2.2 cannot:

- how many independent honest/null traces are needed for any `alpha=0.001` claim after sequential correction
- whether hard-negative traces require their own larger sample-size target
- whether monitor comparison power is adequate for superiority claims
- whether correlated audit windows reduce the effective negative count
- whether synthetic pilot distributions should be replaced, augmented, or externally reviewed before main claims
