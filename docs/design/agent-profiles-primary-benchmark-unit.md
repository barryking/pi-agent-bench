# Agent Profiles as the Primary Benchmark Unit

> Status: archived historical design input. Current behaviour and supported commands are
> documented in `docs/architecture.md`, `docs/decisions.md`,
> `docs/running-evaluations.md`, and `docs/metrics.md`. Some implementation and
> dashboard details below were superseded during validation.

## Summary

Pi Agent Bench should pivot from mainly comparing models to comparing
reproducible agent profiles.

The current design treats a benchmark setup as one model profile plus one agent
profile. That is useful for clean model-vs-model checks, but it undersells the
more realistic question:

> Which configured agent system produces the best finished outcome for the
> time and cost?

In practice, the thing teams deploy is not just a model. It is an agent system:
instructions, tools, skills, extensions, review behaviour, compaction settings,
MCP access, and one or more available models. A profile may use only one cloud
model, only one local model, several cloud models, several local models, or a
local/cloud mix.

The benchmark should therefore make the complete runnable `AgentProfile` the
first-class comparison unit. Reusable Pi and model definitions still exist, but
they are components of an agent profile rather than the main thing the
dashboard asks users to compare.

## Design Change

### Old Default Question

The current default framing answers:

> How does model A compare with model B under the same Pi setup?

That remains useful for controlled model baselines, especially when evaluating
local candidates against hosted controls.

### New Default Question

The more useful default framing is:

> How does profile A compare with profile B on the same cases?

A profile is the full repeatable agent setup. It includes, directly or by
reference:

- Pi instructions and system-prompt changes;
- tools;
- skills;
- extensions;
- prompt templates;
- Pi settings;
- MCP access;
- available model resources; and
- the default model resource used when Pi starts.

Under this framing, a model-vs-model benchmark still works. It is represented
as two otherwise-identical profiles:

```text
profile-cloud-frontier = vanilla harness + frontier cloud model as primary
profile-local-32b      = vanilla harness + local 32B model as primary
```

The dashboard can still show the model used by each profile, but the row, dot,
or ranking belongs to the profile.

## Why This Matters

Model-only comparison is often too narrow. A smaller local model with better
tools, stronger instructions, and a cloud reviewer may beat a larger model used
through a weak harness. A cloud-only profile may be fast and expensive. A
local-first profile may be slower, cheap, and nearly as good. A frontier profile
may be best on quality but not best on cost-adjusted value.

The benchmark should make those tradeoffs visible:

```text
Profile              Quality   Time    Run cost
local-primary        0.78      14m     0.00
cloud-primary        0.88       8m     0.31
local-cloud-review   0.86      11m     0.07
frontier-agent       0.94       9m     0.64
```

That is closer to the decision users need to make:

> Which agent setup should we run for this class of work?

## Concepts

### Model Definition

A model profile remains a reusable definition of one inference setup:

- provider;
- model identifier;
- endpoint and credential environment names;
- reasoning or thinking level;
- context/runtime limits;
- cost identity; and
- public-safe fingerprint.

Model profiles are still needed because they prevent duplicating endpoint and
credential details across agent profiles.

The normal execution target is an Inspect model. A model profile provides the
Inspect model specification plus resource-specific endpoint, authentication,
model arguments, generation configuration, and model capabilities needed to
construct that model and expose an accurate Pi catalog entry.

Some models, notably the OpenAI Codex subscription/OAuth provider implemented
by Pi but not Inspect, may instead declare a Pi-direct execution target. That
target provides the Pi provider/model identifiers and named authentication
source required to stage it in the isolated Pi home.

Secret values remain outside all profile files. Bridged credentials stay on the
Inspect host; direct credentials are staged only for the selected direct
resources.

#### Model Profile Contract

Model profile names become agent-profile resource names and bridged Pi model
aliases. They must match `[a-z0-9][a-z0-9._-]*`; `/`, whitespace, and provider
syntax are not allowed in a resource name.

The implementation should replace the current generic process-wide
`runtime_env` plus optional `pi_direct` shape with an explicit `execution`
object. No compatibility layer is required.

A local model served from a DGX through an OpenAI-compatible API is bridged:

```json
{
  "kind": "local",
  "model": "openai/nvidia/Qwen3.6-35B-A3B-NVFP4",
  "execution": {
    "mode": "inspect-bridge",
    "model_args": {},
    "model_args_env": {
      "base_url": "DGX_BASE_URL",
      "api_key": "DGX_API_KEY"
    },
    "generate_config": {
      "temperature": 0
    }
  },
  "capabilities": {
    "context_tokens": 131072,
    "max_output_tokens": 32768,
    "reasoning": true,
    "input": ["text"]
  },
  "configuration": {
    "weights": "nvidia/Qwen3.6-35B-A3B-NVFP4@exact-revision",
    "runtime": "vllm",
    "runtime_version": "exact-version",
    "quantisation": "NVFP4"
  }
}
```

An ordinary cloud API or OpenRouter resource has the same bridged shape. Its
`model` uses the Inspect model specification, and `model_args_env` supplies only
the named host environment variables needed by that instance:

```json
{
  "kind": "hosted",
  "model": "openrouter/openai/example-model",
  "execution": {
    "mode": "inspect-bridge",
    "model_args": {},
    "model_args_env": {
      "api_key": "OPENROUTER_API_KEY"
    },
    "generate_config": {
      "reasoning_effort": "high"
    }
  },
  "capabilities": {
    "context_tokens": 131072,
    "max_output_tokens": 32768,
    "reasoning": true,
    "input": ["text"]
  },
  "configuration": {
    "provider": "OpenRouter",
    "model_revision": "exact-version-or-snapshot"
  }
}
```

An OpenAI Codex subscription resource is Pi direct:

```json
{
  "kind": "hosted",
  "model": "openai-codex/example-model",
  "execution": {
    "mode": "pi-direct",
    "provider": "openai-codex",
    "model": "example-model",
    "auth_file_env": "PI_AUTH_FILE"
  },
  "capabilities": {
    "context_tokens": 131072,
    "max_output_tokens": 32768,
    "reasoning": true,
    "input": ["text"]
  },
  "configuration": {
    "billing": "ChatGPT subscription",
    "authentication": "Pi OAuth",
    "model_revision": "exact-version-or-snapshot",
    "thinking_level": "high"
  }
}
```

The fields have these rules:

- `model_args` contains public-safe keyword arguments passed to the Inspect
  model constructor;
- `model_args_env` maps an Inspect model-constructor argument to the host
  environment variable containing its value;
- each bridged model is constructed independently with its resolved arguments;
  the implementation must not expose one resource by mutating process-wide
  provider environment variables around the whole evaluation;
- `generate_config` contains public-safe Inspect generation defaults for that
  resource;
- `capabilities` is required and generates the corresponding Pi model metadata;
- the case `context_tokens` limit caps `capabilities.context_tokens`, while
  `max_output_tokens` must not exceed either the real model limit or the capped
  context window;
- `configuration` contains public reproducibility facts and is fingerprinted;
- names of credential environment variables are fingerprinted, but resolved
  values are not; and
- secret-like fields are invalid in `model_args`, `generate_config`,
  `capabilities`, and `configuration`.

Local profiles (`kind: "local"`) have complete zero inference cost. Hosted
profiles (`kind: "hosted"`) take cost from provider or runtime telemetry;
missing cloud cost produces partial or unavailable coverage rather than zero.

### Pi Profile

A Pi profile is a reusable definition of Pi's harness behaviour:

- tools;
- instructions and system-prompt changes;
- skills;
- extensions;
- prompt templates;
- settings;
- runtime environment variable names; and
- MCP access.

This is the object that the current code calls `AgentProfile`. The implementation
should rename it to `PiProfile` because it is only one component of the complete
runnable agent.

### Agent Profile

An agent profile is the complete benchmarkable setup. It composes:

- one Pi profile;
- one or more model resources; and
- one default model resource.

It is the object users select, run, compare, and see in reports. It should answer:

- what Pi can do;
- what guidance Pi receives;
- which extensions or MCP tools are available;
- which concrete model resources Pi can access;
- which model Pi starts with; and
- what version/fingerprint of all of that was tested.

### Model Resources

Model resources are the concrete model profiles made available to an agent
profile. They describe capability, not purpose.

Examples:

- `local-32b`;
- `frontier-cloud`;
- `cheap-cloud`;
- `subscription-cloud`.

One resource is the default. Pi starts with it. The selected Pi profile's
extensions may use Pi's native model registry and `setModel` support to switch
among the configured resources.

## Agent Profile Shape

There is one user-facing runnable profile shape:

```json
{
  "version": 1,
  "profiles": {
    "frontier-agent": {
      "description": "Vanilla Pi using one frontier cloud model.",
      "pi_profile": "vanilla",
      "model_resources": ["frontier-cloud"],
      "default_model_resource": "frontier-cloud"
    },
    "local-cloud-review": {
      "description": "Local primary work with cloud review available.",
      "pi_profile": "team-agent",
      "model_resources": ["local-32b", "frontier-cloud"],
      "default_model_resource": "local-32b"
    }
  }
}
```

The entries in `model_resources` reference existing model profiles. The
`pi_profile` entry references one reusable Pi profile. Agent profiles do not
embed credentials or secret values.

`model_resources` is ordered. The implementation must preserve and fingerprint
that order because model cycling or an extension may observe it. Bridged
resource names become model aliases and must be unique. Direct provider/model
pairs must also be unique. Direct resources that share a Pi provider key must
resolve to the same provider configuration and authentication entry;
conflicting definitions are invalid.

There is deliberately no `routing_policy` field. The Pi profile contains the
extensions, skills, prompts, and settings that produce the agent's behaviour.
If an extension switches models, it uses Pi's native model-selection API. That
extension and its configuration are already part of the Pi profile fingerprint.

An agent profile records available capability, not a promise that every
resource will be used in every run. A valid multi-resource profile may complete
a case using only its default model.

### Native Pi Model Selection

Pi already provides the required model-selection mechanism:

- `models.json` defines custom providers and models;
- `--provider` and `--model` select the starting model;
- `--models` scopes the configured models;
- extensions can access `ctx.modelRegistry`;
- extensions can call `pi.setModel(...)`; and
- Pi emits model-selection and message events where telemetry is available.

The benchmark should configure these native features rather than build a
separate router. For each run it should:

1. resolve every model resource referenced by the agent profile;
2. construct one Inspect model alias for each bridged resource;
3. generate an isolated Pi model catalog containing the bridged aliases and any
   direct resources;
4. resolve bridged credentials on the host and stage authentication only for
   direct resources;
5. pass the configured resource set to Pi;
6. start Pi with the default resource; and
7. let the selected Pi profile determine whether and when models are switched.

The model resource set is a reproducible profile contract, not a hostile-code
security boundary. Selected extensions are trusted components of the profile
and are fingerprinted with it. They are expected to select only configured
resources. Any observed use of a model outside that set invalidates the run.

### Inspect Bridge and Direct Resources

The pinned Inspect `sandbox_agent_bridge()` is multi-model capable. It accepts a
`model_aliases` mapping; each incoming alias resolves to a separate Inspect
`Model`, and the bridge calls that model's normal `generate()` method.

The current repository only creates one `inspect-bridge/inspect` entry in Pi's
`models.json`. That is a limitation of the current adapter configuration, not
of Inspect's bridge.

For each bridged resource, the implementation should:

1. construct an Inspect `Model` using that resource's resolved model
   specification, endpoint, credential, model arguments, and generation config;
2. map the resource name to that model through `model_aliases`; and
3. add the same resource name as a model under the Pi `inspect-bridge`
   provider.

Pi then sees entries such as `inspect-bridge/local-32b` and
`inspect-bridge/frontier-cloud`. An extension switches between them through
Pi's normal model registry and `setModel` API. Every bridged call still passes
through Inspect, so Inspect records the real model name, transcript, tokens,
latency, and provider-reported cost in `sample.model_usage`. Inspect's token and
cost limits continue to apply to those calls.

Pi-direct resources remain available for models Inspect cannot instantiate.
The Pi catalog may contain both bridge aliases and direct provider entries:

```text
Resource             Example                              Request path
dgx-local            inspect-bridge/dgx-local              Inspect bridge
cloud-api-key        inspect-bridge/cloud-api-key          Inspect bridge
openrouter-api-key   inspect-bridge/openrouter-api-key     Inspect bridge
codex-subscription   openai-codex/subscription-model      Pi direct
```

This is still Pi-native model selection, not benchmark-owned routing. Pi chooses
the current resource; the selected provider entry determines whether that call
uses the bridge or a direct provider.

`direct` describes the request path, not whether a model is local or cloud. A
direct call is one where Pi calls the model provider itself. Local
OpenAI-compatible endpoints, ordinary cloud API-key models, and OpenRouter
should normally be bridged. Pi direct is the fallback for a provider or
authentication method that Inspect cannot instantiate; in the first design,
that means OpenAI Codex subscription/OAuth resources.

The runtime must:

- reject conflicting direct provider or authentication definitions;
- cap every Pi catalog entry's advertised context window at the case
  `context_tokens` limit without exceeding the real model capacity;
- stage the Pi JSON-event guard and wrap every bridge-only, direct-only, and
  hybrid Pi invocation with it;
- use that guard as the profile-wide turn and token limit across bridged and
  direct calls;
- use the sandbox process timeout for the case wall-time limit;
- use Inspect model usage as the authoritative source for bridged calls;
- use Pi events as the source for direct-call usage; and
- merge those sources without double-counting bridged calls.

The Pi guard is a benchmark limit supervisor, not a trust mechanism. It streams
Pi JSON events, counts `turn_start` events and assistant-message token usage,
terminates Pi when the case turn or total-token limit is exceeded, and emits
exit code `75` so the limit is distinguishable from an ordinary crash. Inspect
may independently enforce limits on bridged model calls; Inspect remains the
authoritative bridged usage record.

Hybrid accounting uses this exact rule:

```text
total usage = Inspect bridged usage + Pi direct-only usage
total cost  = Inspect bridged reported cost + Pi direct-only reported cost
```

Pi events for `inspect-bridge/*` calls may be retained as model-selection
evidence but must be excluded from the merged totals. Only Pi assistant-message
events attributed to a configured direct provider/model contribute direct
usage. If Pi cannot attribute an event to its execution path, the affected
aggregate field is unavailable; the implementation must not infer it by
subtracting unlike token accounts.

A bridge-only profile retains Inspect cost-limit enforcement when every cloud
model has cost metadata. A profile containing any direct resource must reject
`--cost-limit` until the Pi guard can enforce cumulative cost across both paths.
Cost reporting remains valid with the documented
`complete`/`partial`/`unavailable` coverage state.

## CLI Direction

Prefer a profile-first command:

```bash
pi-bench benchmark \
  --agent-profile local-cloud-review \
  --agent-profiles-file configs/agent-profiles.local.json \
  --pi-profiles-file configs/pi-profiles.local.json \
  --model-profiles-file configs/model-baselines.local.json \
  --dataset evals/starter/cases.jsonl \
  --run-name starter-agent-systems-v1 \
  --epochs 3 \
  --resume
```

For controlled model-only baselines, define two profiles with the same Pi
profile and exactly one different model resource each.

The framework is not yet in use, so this design does not preserve the existing
model-profile-plus-agent-profile CLI. The implementation should move directly
to profile-first commands rather than carry a second public configuration path.

## PRD-Style Use Cases

Cases can already include a detailed PRD-style request because `instruction` is
a free text field. A case instruction can contain:

- product requirements;
- acceptance criteria;
- non-functional requirements;
- constraints;
- examples;
- migration notes;
- documentation expectations; and
- required public tests.

This is useful and should be explicitly supported. Real coding-agent benchmarks
should include some cases that read like realistic work tickets or PRDs, not
only small puzzle prompts.

The case should still avoid telling the agent how the protected verifier works.
The PRD says what finished behaviour should exist; the verifier independently
checks whether the result satisfies it.

## Verification Boundary

Verification must remain outside the AI solution.

Current repo-grounded facts:

- the case instruction is passed to Pi as the task input;
- the starting repository is copied to `/workspace`;
- Pi edits `/workspace`;
- the current loader only checks that the verifier command contains
  `/opt/verifiers/<case-id>/verify.py`;
- the scorer executes the complete case-supplied verifier command as root;
- verifier source is copied into the Docker image under `/opt/verifiers`; and
- the current image makes `/opt/verifiers` root-owned and mode `700`, while Pi
  runs as the unprivileged `eval` user; and
- the protected verifier runs after Pi finishes.

That means the AI does not receive the verifier source as part of the starting
repository. It can infer requirements from the task, public tests, and visible
code, but it should not be able to inspect or patch the protected verifier as
its solution.

The design should preserve this boundary:

- never copy verifier source into `/workspace`;
- keep verifier paths fixed under `/opt/verifiers`;
- keep verifier files owned and permissioned as benchmark infrastructure;
- require the exact verifier command
  `["python3", "/opt/verifiers/<case-id>/verify.py"]`, with no extra executable,
  arguments, or shell content;
- keep known-good patches outside public examples when needed; and
- record verifier and sandbox fingerprints with the result.

This does not make cheating impossible in a malicious-container sense, but it
keeps normal agent work separated from the hidden scoring contract and makes
benchmark claims repeatable.

## Reporting

The primary dashboard should compare agent profiles.

Recommended main views:

- profile ranking by success and mean quality;
- quality vs total wall time;
- quality vs run cost;
- quality vs time with bubble size for cost;
- profile detail with configured model resources and any observed model usage;
  and
- failed-case drilldown linking back to Inspect evidence.

### Quality, Time, and Cost Chart

The chart is one bubble per agent profile in the selected valid comparison
cohort:

- x-axis: median total wall time across all valid runs;
- y-axis: macro mean quality, calculated by averaging trials within each case
  and then averaging the cases;
- bubble area: summed run cost across all runs in the selected cohort; and
- point label: agent profile name, not model name.

The upper-left area should be visibly labelled `Preferred region`: higher
quality and lower elapsed time are better. This is an interpretation aid, not a
pass/fail threshold.

The chart must include a bubble-size legend and this short reading guide:

> A point directly above another has better quality at roughly the same time.
> A similarly positioned but smaller bubble achieves the same outcome at lower
> cost.

Only profiles with matching case coverage, trial counts, verifier, limits, Pi
version, Inspect version, and sandbox identity belong in the same chart.
Partial or unavailable cloud cost must be visibly marked in the point and
tooltip and must not be plotted as zero. A partial value may size the bubble
from the reported lower-bound amount but needs a distinct outline; an
unavailable value should use a fixed hollow marker with no implied bubble size.
The tooltip should show profile name, quality, median wall time, summed run cost
and cost coverage, configured model resources, and observed models when
available.

Cost is intentionally simple:

```text
run cost = local model cost (0) + reported cloud model costs
```

The benchmark records a numeric observed cost and a
`complete`/`partial`/`unavailable` coverage state for each outcome/run. There is
no currency field and no required per-provider/per-model cost breakdown.
Local-only inference has complete zero run cost. If a cloud call occurs and its
cost is not available, the run cost must be marked unavailable or partial
rather than treating that cloud call as free. Profile cost is the sum of
observed run amounts plus the combined coverage state.

Coverage is deterministic:

- `complete`: every used cloud call has reported cost, or the run is local-only;
- `partial`: at least one used cloud call has reported cost and at least one
  used cloud call does not; and
- `unavailable`: cloud inference occurred but no cloud call supplied cost.

This number is useful for comparing profiles, but it is not total cost of
ownership. Hardware amortization, energy, and operator cost remain outside the
first design.

## Observed Usage

Each result should record configured identity:

- agent profile name;
- Pi profile name;
- available model resources;
- default model resource;
- bridge or direct execution path for each resource;
- Pi profile fingerprint;
- model profile fingerprints;
- composed agent profile fingerprint;
- verifier fingerprint;
- sandbox image identity; and
- shared cohort/harness fingerprint.

The composed agent profile fingerprint and shared cohort fingerprint are
different identities:

- the agent profile fingerprint changes when its Pi profile, model resources, or
  default resource changes; and
- the cohort fingerprint remains shared by profiles that used the same case
  inputs, starting repositories, verifiers, limits, run conditions, Pi version,
  Inspect version, benchmark harness, and sandbox.

Keeping them separate allows differently configured agent profiles to remain in
the same valid comparison cohort.

The cohort identity is generated evidence, not another configurable profile and
not a replacement for `AgentProfile`. There is no `BenchmarkProfile`.

The implementation should calculate `cohort_fingerprint` from canonical JSON
containing:

- the selected dataset version and a content fingerprint of the selected
  dataset file;
- ordered case identifiers and fingerprints of each case instruction, scoring
  contract, and relevant metadata;
- a content fingerprint of each effective starting repository, plus its source
  commit when present;
- each protected verifier fingerprint;
- each case's wall-time, turn, context-token, and total-token limits;
- planned trial count and declared cache state;
- framework, Pi, and Inspect versions;
- a fingerprint of behaviour-affecting benchmark harness source; and
- sandbox image and sandbox-source identities.

The harness-source fingerprint must exclude agent-profile, Pi-profile, and
model-profile definitions because those belong to the composed agent profile
identity. It should also exclude documentation, logs, results, and other files
that cannot affect execution or scoring. The current whole-checkout
`benchmark_fingerprint` and report grouping must be replaced with these
separate identities.

`run_name` remains a human label and is not fingerprint input. Reports may use
it as a filter, but profiles with the same generated cohort fingerprint are
technically comparable. Reports must still verify equal case coverage and
completed trial counts before placing profiles in one chart.

Each result should also record observed usage where Inspect or Pi telemetry
supports it:

- provider;
- model;
- call count;
- input tokens;
- cached input tokens;
- output tokens;
- reasoning tokens;
- model latency;
- and reported cost.

Observed provider/model breakdowns are optional explanatory views. They are not
required for a run to be valid. Aggregate cost and token totals should still be
recorded when either runtime supplies them without per-model detail.

The result record should persist source aggregates separately from their merged
total:

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
      "model_seconds": 18.2,
      "reported_cost": null
    },
    "total": {
      "input_tokens": 17000,
      "cached_input_tokens": 4000,
      "output_tokens": 2700,
      "reasoning_tokens": 1000,
      "model_seconds": 60.7,
      "reported_cost": 0.08
    },
    "cost_coverage": "partial"
  }
}
```

Unavailable measurements remain `null`; zero is reserved for a measured zero.
Per-model details may be stored in an optional explanatory collection, but they
are not required to produce these path-level and total aggregates.

A merged token or timing field is non-null only when every used execution path
reports a compatible value. Cost is the exception: a partial reported amount is
stored as a lower bound together with `cost_coverage: "partial"`.

## Pi Project Trust

Pi's `--approve` and `--no-approve` flags control whether project-local Pi
configuration is trusted. They do not ask a human to approve tool calls.

Agent-profile runs should always pass `--no-approve`. The benchmark explicitly
stages the selected instructions, extensions, skills, prompts, and settings in
an isolated global Pi home. Ignoring repository-owned `.pi` settings,
extensions, skills, prompts, and package resources, plus project
`.agents/skills`, prevents an evaluated repository from silently adding
unprofiled harness behaviour.

Context files are different and should remain enabled. Pi loads both:

- the Pi profile's fingerprinted `AGENTS.md`, staged in the isolated global Pi
  home; and
- repository `AGENTS.md` or `CLAUDE.md` files discovered from `/workspace`.

The repository context is part of the case input, is covered by the starting
repository and dataset identity, and is the same for every profile in a valid
comparison cohort. `--no-approve` does not suppress these context files, and
agent-profile runs must not pass `--no-context-files`.

Project trust is therefore a harness isolation rule, not a configurable
`PiProfile` property. Remove the current `trust_mode` field during the rename.
If a future dataset intentionally evaluates repository-supplied Pi
configuration, that must be a separate explicit design with those resources
fingerprinted as part of the runnable agent profile.

## Implementation Plan

### 1. Rename the Existing Harness Profile

Rename the current harness-only `AgentProfile` object and configuration to
`PiProfile`. Preserve its existing responsibilities:

- instructions and system prompts;
- tools;
- skills;
- extensions;
- prompt templates;
- Pi settings;
- runtime environment variable names; and
- MCP access.

Drop the current `trust_mode` field. Agent-profile benchmark runs enforce
`--no-approve` as an isolation invariant.

Update the current profile documentation and examples to use the new term.

### 2. Add Runnable Agent Profiles

Create the new user-facing `AgentProfile` object. Validate that:

- it references a known Pi profile;
- every resource references a known model profile;
- resources are unique;
- one default model resource is selected;
- the default appears in the resource set; and
- provider credentials and secrets are supplied only through named environment
  or authentication files, never embedded in a profile.

Its public identity should contain the resolved public identities of its Pi
profile and model resources. Its fingerprint input should contain the component
configuration fingerprints, the ordered model-resource bindings, and the
default binding, but not top-level display names, descriptions, or secret
values. Resource binding names remain fingerprint input because extensions can
observe and select those aliases.

### 3. Update CLI Around Profiles

Replace the current model-plus-agent selection with profile-first commands:

- list agent profiles;
- list Pi profiles;
- run one or more agent profiles; and
- doctor an agent profile, including every referenced model resource.

No compatibility layer is required because the framework is not yet in use.

### 4. Configure Model Resources and the Bridge

For each selected agent profile:

- resolve all referenced model profiles;
- validate the explicit bridged or direct execution contract and required model
  capabilities for every resource;
- construct resource-specific Inspect `Model` instances for bridged resources;
- resolve each bridged resource's `model_args_env` independently and pass the
  resolved values into that model's constructor without process-wide provider
  environment mutation;
- pass those instances to `sandbox_agent_bridge(model_aliases=...)`;
- generate an isolated Pi `models.json` containing one `inspect-bridge` model
  per bridged alias plus any direct provider/model entries;
- reject duplicate aliases, duplicate direct provider/model pairs, and
  conflicting direct definitions that share a Pi provider key;
- keep bridged credentials on the host and stage credentials only for direct
  resources;
- pass the configured resource set through Pi's native model options;
- start Pi with the declared default resource;
- stage `pi_guard.py` and wrap the Pi process for bridge-only, direct-only, and
  hybrid profiles; and
- retain the selected Pi profile's extensions, skills, prompts, and settings.

Inspect remains the runner, bridge, and scorer. Do not add a benchmark routing
engine: Pi and the selected extensions own model selection. A multi-resource
profile is valid whether it uses one or several configured resources in a run.

Use Inspect usage for bridged calls and only direct-attributed Pi events for
direct calls. Exclude Pi bridge events from merged totals. Capture selected
provider/model and model-change events when available. Preserve Inspect cost
limits for bridge-only profiles with complete model cost metadata; reject
`--cost-limit` for profiles containing direct resources until the Pi guard can
govern both paths.

### 5. Update Reports and Dashboard

Make agent profile the main comparison key.

Add the quality/time/cost bubble chart and profile detail panels showing:

- configured model resources;
- default resource;
- observed model usage, when available;
- run cost;
- cost coverage;
- wall time;
- token totals; and
- failed cases.

Store the composed agent profile fingerprint separately from the shared
cohort/harness fingerprint. Replace the current whole-checkout benchmark
fingerprint as the report cohort key with the canonical generated cohort
fingerprint defined above.

Persist bridged, direct, and merged usage aggregates plus cost coverage in every
result. Keep provider/model detail optional.

### 6. Add Tests

Cover:

- Pi-profile loading and staging after the rename;
- agent-profile validation;
- unknown Pi-profile or model-profile references;
- duplicate or missing model resources;
- invalid default model resource;
- invalid or Pi-unsafe resource aliases;
- bridged and direct model-profile schema validation;
- rejection of secrets in public model fields;
- construction of one resource-specific Inspect `Model` per bridged resource;
- generation of `model_aliases` and matching Pi bridge model entries;
- two bridged OpenAI-compatible resources retaining distinct endpoints and
  credentials;
- absence of process-wide provider environment mutation during multi-resource
  model construction;
- generation of direct Pi catalog entries for direct resources;
- application of the case context-window cap to every configured model;
- bridged credentials remaining host-side;
- staging authentication only for selected direct resources;
- rejection of duplicate aliases and conflicting direct definitions;
- starting Pi with the declared default resource;
- forced `--no-approve` project isolation with no profile override;
- loading both Pi-profile and repository context files while project `.pi`
  resources remain untrusted;
- an owned extension switching between two bridged models through Pi's native
  API;
- Inspect recording both bridged models in transcript and `sample.model_usage`;
- Inspect token and cost limits applying across a bridged model switch;
- a mixed bridged/direct profile selecting both paths;
- the Pi guard wrapping bridge-only, direct-only, and hybrid invocations;
- profile-wide token/turn limits and exit-code `75` handling;
- bridged, direct, and merged usage without double-counting;
- Pi bridge events being excluded from merged totals;
- rejection of `--cost-limit` for profiles containing a direct resource;
- result fingerprint changes when Pi or model bindings change;
- resource alias changes affecting the composed profile fingerprint;
- profile and cohort fingerprints remaining separate;
- cohort fingerprint changes for dataset, starting-repository, verifier, limit,
  version, harness, or sandbox changes;
- cohort fingerprint remaining unchanged when only an agent, Pi, or model
  profile definition changes;
- report aggregation by agent profile;
- chart use of macro mean quality, median all-run wall time, and summed run cost;
- preferred-region label, bubble legend, reading guide, and cost-coverage state;
- zero cost for local-only runs;
- complete cost for cloud runs where every used call reports cost;
- summed local/cloud run cost;
- unavailable or partial cost when cloud cost is missing;
- runs remaining valid without per-model telemetry;
- PRD-length instructions loading correctly;
- an exact protected verifier command under `/opt/verifiers`;
- verifier files being unreadable to the Pi user; and
- the protected verifier still executing successfully as the scorer's root
  user.

### 7. Migrate Documentation and Examples

Update the terminology, commands, configuration examples, identity rules, and
reporting descriptions in:

- `README.md`;
- `docs/decisions.md`;
- `docs/architecture.md`;
- `docs/scoring-and-extending.md`;
- `docs/roadmap.md`;
- `docs/agent-profiles.md`;
- `docs/model-baselines.md`;
- `docs/metrics.md`;
- `examples/agent-profiles/README.md`; and
- the public example profile files.

The documentation change must make `AgentProfile` the composed runnable unit,
rename the existing harness-only concept to `PiProfile`, explain bridge versus
Pi-direct execution, and keep the roadmap honest about implemented versus
designed behaviour.

## Non-Goals

- Do not remove model profiles as reusable model definitions.
- Do not put secrets or provider credentials in agent profile JSON.
- Do not introduce a separate `BenchmarkProfile` concept.
- Do not introduce a benchmark-owned model router or fixed role system.
- Do not introduce semantic roles or usage labels as profile schema.
- Do not require every configured model resource to be used in every run.
- Do not require per-provider/per-model usage detail when Pi does not expose it.
- Do not add compatibility for the current pre-adoption CLI or profile names.
- Do not claim total cost of ownership from provider API cost alone.
- Do not compare profiles across different case versions, verifier
  fingerprints, limits, Pi versions, or sandbox images.
- Do not expose protected verifier code to the agent.
- Do not build a second runner or replace Inspect.

## Recommended First Cut

1. Introduce the explicit bridged/direct model-profile execution contract.
2. Rename the existing harness-only profile to `PiProfile`.
3. Introduce the composed runnable `AgentProfile` as the comparison unit.
4. Expose bridged resources through Inspect `model_aliases` and matching Pi
   catalog entries, retaining Pi-direct entries only where Inspect cannot
   represent the model.
5. Start Pi with the profile's default resource and allow selected extensions to
   switch through Pi's native API.
6. Wrap every Pi invocation with the profile-wide turn/token guard.
7. Record agent profile identity separately from generated cohort identity.
8. Persist bridged, direct, and merged usage without double-counting.
9. Add the quality/time/cost bubble chart using aggregate run cost.
10. Show detailed observed model usage where Inspect or Pi provides it.

This keeps the benchmark honest: compare the deployed-style agent setup, show
the configured model composition and any available observed usage, and ground
every quality claim in protected verification evidence.
