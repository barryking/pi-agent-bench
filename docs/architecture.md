# How Pi Agent Bench works

Pi Agent Bench measures finished repository outcomes produced by complete agent
profiles.

## Runtime boundary

The host runs the CLI, Inspect, Docker, reporting, and bridged model clients.
The clean Docker container runs Pi, `/workspace`, the selected Pi resources,
the Pi limit guard, and the protected verifier.

One trial:

1. Inspect creates a fresh container and copies the starting repository.
2. The selected `PiProfile` is staged into a private global Pi home.
3. Every model resource is resolved and capped to the case context limit.
4. Each bridged resource gets its own Inspect `Model` and bridge alias.
5. Direct provider models and only their selected authentication are staged.
6. Pi receives one isolated catalog, starts with the declared default, and may
   switch resources through its native model registry.
7. The guard supervises all Pi turns and assistant-message tokens while the
   sandbox process timeout enforces wall time.
8. The root-owned verifier checks the final repository.
9. Inspect saves the canonical trajectory, score, timing, and bridged usage.
10. Pi Agent Bench exports composed identity, cohort identity, path-level usage,
    cost coverage, and the finished diff.
11. The container is discarded. The host starting repository is unchanged.

## Profiles

`PiProfile` contains tools, global context, system-prompt changes, skills,
extensions, prompt templates, settings, runtime environment names, and MCP
descriptions.

`ModelProfile` contains resource name, local/hosted kind, Inspect model
specification, explicit bridge/direct execution details, capabilities, and
public reproducibility configuration.

`AgentProfile` binds one Pi profile to ordered model resources and a default
resource. It is the CLI selection, report row, chart point, and ranking unit.

## Repository boundaries

- `src/pi_agent_bench/` contains the Python runtime. Profile modules own
  definition and validation; `inspect_tasks`, `inspect_agent`, and
  `inspect_scorers` own evaluation integration; `run_records` owns canonical-log
  export; `usage_records` owns bridged/direct accounting; and the reporting
  modules consume only exported records.
- `src/pi_agent_bench/viewer/` contains the dependency-free dashboard, split
  into state, statistics, charts, and presentation assets.
- `configs/` contains tracked templates and editor-facing schemas. Resolved
  local configuration stays in ignored `*.local.json` files.
- `evals/`, `starting-repos/`, and `verifiers/` contain the three explicit case
  inputs: contracts, starting code, and protected checks.
- `examples/` contains executable integration fixtures; `tests/` contains unit
  and browser-side checks; `scripts/` contains repository validation entry
  points; and `docs/design/` retains accepted design specifications.

Dependencies point inward from CLI and Inspect integration toward profiles and
small value-normalization modules. The Python package has no circular imports;
dashboard code does not participate in benchmark execution.

## Cases and datasets

A case is one repository-outcome contract. A dataset is a versioned JSONL list
of cases intended to run together. Runtime code has only enabled and draft
cases; it has no separate pilot or candidate execution class.

Case maturity is a repository workflow:

```text
draft → validate → prove → candidate trials → maintained dataset
```

Draft cases are rejected by execution. Structural validation resolves the
starting repository and verifier. Proof runs the protected verifier against
both untouched code and a maintainer's known-good diff. After proof, the case
can be enabled for candidate trials. Acceptance adds it to a maintained dataset
and changes that dataset's version.

Project-owned starting code lives under `starting-repos/`. Ignored external or
private checkouts live under `local-repos/`; location is an ownership boundary,
not a case type.

## Multi-model execution

Bridged resources are passed to Inspect's `sandbox_agent_bridge` with
`model_aliases`. Pi sees matching `inspect-bridge/<resource>` entries.
Pi-direct entries share the same catalog and model allowlist.

The available set records capability, not required use. A valid multi-resource
profile may finish using only its default. Use outside the configured set
invalidates the benchmark claim.

## Usage accounting

```text
merged usage = Inspect bridged usage + Pi direct-attributed usage
merged cost  = Inspect bridged reported cost + Pi direct-attributed reported cost
```

Pi events for `inspect-bridge/*` are retained as explanatory selection evidence
but excluded from merged totals. A merged token or timing field is available
only when every used path provides a compatible measurement. Partial cost is
stored as a numeric lower bound with explicit coverage.

## Evidence identities

The agent-profile fingerprint contains component fingerprints, ordered resource
bindings, aliases, and the default. Display names, descriptions, and resolved
secrets are excluded.

The cohort fingerprint contains the ordered use cases, starting repositories
and source commits, protected verifiers, scoring contracts, limits, cache and
cost-limit conditions, Pi/Inspect versions, behaviour-affecting execution
source, and the common sandbox runtime fingerprint. It excludes the agent
profiles being compared, planned/completed trial counts, raw paths, dataset
formatting, framework display version, reporting/dashboard code, documentation,
logs, and results.

One generated `benchmark_id` identifies a campaign across every selected agent
profile. Repeated campaigns may share a cohort fingerprint and can be pooled,
while matched repetitions use the benchmark ID to avoid pairing unrelated runs.
`run_name` remains a reusable human label.

Inspect `.eval` files remain authoritative. JSON, CSV, JSONL, Markdown, and the
dashboard are disposable views.
