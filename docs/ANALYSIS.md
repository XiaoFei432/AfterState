# Run-level analysis

The analysis input is a linked run-level ledger. Paper aggregates are stored separately.

## Pairing and estimand

`afterstate analyze` requires a rectangular site × configuration × repeat grid for one feedback/resource setting. Blocks link identical site, configuration, repeat, feedback and budget across requested controllers and PRE/REAL. Duplicate records, missing partners, mismatched boundary hashes, inconsistent site metadata and unresolved infrastructure errors are rejected. Separate analyses are performed for different resource or wording conditions.

Within a site/controller/protocol, repeats and configurations are averaged equally. The primary mean then weights sites equally, matching the balanced-grid estimand in Equation (5). Failed and budget-exhausted continuations are included. Framework action means also include unsuccessful runs.

The primary contrast is PRE minus REAL success, in percentage points. A controller interaction is `(REAL advantage of first over second) - (PRE advantage of first over second)`, as in Equation (6). All pairwise interactions among selected controllers are emitted. Paired outcomes distinguish success, silent failure and other failure in a 3 × 3 cross-tabulation.

## Uncertainty

Bootstrap samples draw repositories with replacement and retain every linked site/controller/protocol observation in each sampled repository, including cluster multiplicity. By default 10,000 seeded resamples yield a 95% percentile interval. With one repository, the interval is `null`. Equivalence is reported only when the whole interval lies within ±2 percentage points.

The implementation additionally offers a two-sided **centered bootstrap approximation** to a null p-value, followed by Holm correction across the emitted controller-pair family. The paper does not specify its exact p-value algorithm; the implementation uses this approximation. Intervals are calculated for the supplied records.

## Held-out policy selection

```console
python -m afterstate select policy.jsonl replication.jsonl --tie-order Native Retry-1 Reflexion Self-Refine Inspect-3 --output selection.json
```

The example tie order is a caller parameter; the PDF's fixed original order is unavailable. The selected PRE and REAL policies are frozen before evaluation. Repository and site overlap are rejected. The command requires matched PRE/REAL records for the frozen policies in REPLICATION, enabling both their REAL comparison and held-out interaction. It does not tune policy selection on REPLICATION outcomes.

Discovery prevalence has a different denominator and is never multiplied by a conditional recovery gap. Balanced category averages are not deployment prevalence estimates.

