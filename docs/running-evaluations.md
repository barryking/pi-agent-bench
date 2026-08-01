# Run evaluations

## 1. Activate and initialise

```bash
source .venv/bin/activate
pi-bench init
```

Edit `.env.local`, model resources, Pi profiles, and composed agent profiles.

## 2. Check one complete profile

```bash
pi-bench doctor \
  --agent-profile local-primary-agent \
  --agent-profiles-file configs/agent-profiles.local.json \
  --pi-profiles-file configs/pi-profiles.local.json \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local
```

`ready` means the Mac, Docker sandbox, Pi resources, every referenced model
resource, endpoint, and selected direct authentication are available.

## 3. Build the protected sandbox

```bash
pi-bench build-sandbox
```

Runs refuse a stale image when protected source or pinned versions change.

Use a maintained dataset for comparisons. `evals/starter/cases.jsonl` is
bundled and ready to run. Files under `evals/candidates/` are maintainer work;
benchmark commands reject them while `metadata.draft` is true. Normal users do
not run `prove-case` before using the starter suite.

## 4. Establish controlled baselines

Represent a model-only comparison as single-resource agent profiles using the
same Pi profile:

```bash
pi-bench benchmark \
  --agent-profile codex-sol-agent \
  --agent-profile codex-luna-agent \
  --agent-profiles-file configs/agent-profiles.local.json \
  --pi-profiles-file configs/pi-profiles.local.json \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name starter-cloud-controls-v1 \
  --epochs 3 \
  --resume
```

## 5. Compare deployed-style systems

```bash
pi-bench benchmark \
  --agent-profile local-primary-agent \
  --agent-profile cloud-primary-agent \
  --agent-profile local-cloud-review \
  --agent-profiles-file configs/agent-profiles.local.json \
  --pi-profiles-file configs/pi-profiles.local.json \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name starter-agent-systems-v1 \
  --epochs 3 \
  --resume
```

The model-resource set is available capability. Pi begins with the default; a
profiled extension decides whether to switch. A run is valid even when it uses
only the default.

## 6. Inspect and export

```bash
pi-bench view --results-dir results --logs-dir logs --inspect
pi-bench export --logs-dir logs --results-dir results
pi-bench report --results-dir results --output results/summary.md
```

Inspect logs are canonical. Dashboard records and reports are rebuildable.

## Resume and failures

`--resume` gives each agent profile its own eval-set directory and lets Inspect
continue interrupted work. `--retry-attempts` controls infrastructure retries.

Incomplete logs, sample errors, and invalid scores go to `results/_invalid/`;
they do not become quality failures or ranking evidence.

## Limits

Case wall, turn, context, and total-token limits come from the dataset. Every Pi
invocation is wrapped by the profile-wide guard. Inspect independently enforces
bridged limits.

`--cost-limit` works only for bridge-only profiles. It is rejected when any
Pi-direct resource is configured because cumulative hybrid cost cannot yet be
supervised safely.

## Comparability

The generated cohort fingerprint includes the shared use cases, repositories,
verifiers, scoring contracts, limits, cache and cost conditions, Pi/Inspect
versions, execution protocol, and sandbox runtime. Agent profiles and planned
trial count are deliberately excluded: they are respectively the comparison
arms and campaign sampling plan.

Every `benchmark` invocation prints a generated `benchmark_id` shared by its
selected profiles. Use `--benchmark-id` to name or extend a particular
campaign. `run_name` remains a reusable label. Reports still require equal case
coverage and completed trials before ranking profiles.
