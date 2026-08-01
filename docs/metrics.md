# What Pi Agent Bench measures

The primary comparison unit is a complete agent profile.

## Primary chart

One bubble represents one profile in one valid generated cohort:

- x: median total wall time across all valid runs;
- y: macro mean quality, averaging trials within each case and then cases;
- bubble area: summed reported inference cost across cohort runs; and
- label: agent profile name.

The chart exposes the trade-off without declaring one region preferable. A
point directly above another has better quality at about the same time. A
similarly positioned smaller bubble achieves the same outcome at lower
reported cost.

Partial cost uses a distinct dashed outline. Unavailable cloud cost uses a fixed
hollow marker with no implied size.

## Quality and success

Quality ranges from `0` to `1` and comes from protected executable checks.
Success requires quality at or above the case threshold and every required
component to pass.

Inspect also supplies repeated-trial reductions such as mean, `pass@k`, and
`pass^k`. At least three trials per profile and case are required before small
differences should be trusted.

## Time

Records include:

- total trial wall time;
- Pi process wall time;
- Inspect working time;
- bridged model working time;
- tool working time; and
- median and slow-end statistics across runs.

The primary chart uses every valid run, including unsuccessful attempts.

## Usage by execution path

Every result stores:

```json
{
  "usage": {
    "bridged": {
      "call_count": 3,
      "input_tokens": 12000,
      "cached_input_tokens": 4000,
      "output_tokens": 1800,
      "reasoning_tokens": 700,
      "model_seconds": 42.5,
      "reported_cost": 0.08
    },
    "direct": {
      "call_count": 1,
      "input_tokens": 5000,
      "cached_input_tokens": 0,
      "output_tokens": 900,
      "reasoning_tokens": 300,
      "model_seconds": null,
      "reported_cost": null
    },
    "total": {
      "call_count": 4,
      "input_tokens": 17000,
      "cached_input_tokens": 4000,
      "output_tokens": 2700,
      "reasoning_tokens": 1000,
      "model_seconds": null,
      "reported_cost": 0.08
    },
    "cost_coverage": "partial"
  }
}
```

Inspect is authoritative for bridged calls. Only Pi assistant events attributed
to configured direct provider/model pairs contribute direct usage. Pi bridge
events are excluded from merged totals.

A merged token or timing field is non-null only when every used path supplies a
compatible value. Zero is measured zero; unavailable is `null`.

## Cost coverage

Run cost is:

```text
local inference cost (0) + reported cloud inference costs
```

Coverage is deterministic:

- `complete`: local-only, or every used cloud call reports cost;
- `partial`: at least one used cloud call reports cost and at least one does
  not;
- `unavailable`: cloud inference occurred but no used cloud call supplied cost.

Partial numeric cost is a lower bound. No currency field or provider breakdown
is required. This is inference cost, not hardware amortisation, energy,
maintenance, or operator cost.

## Agent behaviour

Pi events record turns, tool calls, failed tool calls, retries, compactions,
return code, selected provider/model where available, and model changes where
Pi emits them. Observed provider/model detail is explanatory and optional; a
run can remain valid without it.

## Comparison validity

Profiles share a chart only when they have:

- the same generated cohort fingerprint;
- identical case coverage;
- identical completed trial counts;
- matching verifier, limits, Pi, Inspect, execution-protocol, and sandbox
  runtime evidence.

The composed profile fingerprint is not a grouping key: different profile
identities are the arms being compared.

Several campaigns may contribute to one cohort. Matched quality deltas and
repetition ranks use `benchmark_id + case_id + trial_number`, so repetitions
from different campaigns cannot be paired accidentally.

## Evidence files

- `logs/**/*.eval`: canonical Inspect evidence.
- `results/*.json`: rebuildable per-trial records.
- `results/*.diff`: final repository changes.
- `results/runs.csv`: one wide row per trial.
- `results/metrics.jsonl`: one chart metric per line.
- `results/_invalid/`: incomplete, errored, or unscored attempts excluded from
  rankings.

Rebuild exports with:

```bash
pi-bench export --logs-dir logs --results-dir results
```

Planned measurements remain first-token delay, local server queue/prompt speed,
GPU/power/energy facts, and clearer failure groups.
