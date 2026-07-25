# Implementation handoff

## Purpose

This document tells a local Codex session what to build next. Read
`project-context.md`, `decisions.md`, `architecture.md` and
`evaluation-strategy.md` first.

## Current state

The repository has:

- a Python package scaffold;
- golden-case dataclasses and JSONL loading;
- schema and synthetic cases;
- deterministic concept scoring;
- a small Pi JSON-mode process wrapper;
- unit tests; and
- CI configuration.

It does not yet execute a complete Inspect-controlled Pi evaluation.

## Next milestone

Implement one reproducible planning case and one reproducible coding case using
Inspect AI, Pi and a configurable OpenAI-compatible model provider.

Do not add a dashboard, database, hosted service or DGX-specific deployment
automation in this milestone.

## Required execution path

```text
Inspect task
  -> fresh Docker sandbox
  -> Pi CLI in JSON mode with an ephemeral session
  -> Inspect sandbox model bridge
  -> model configured on the Inspect run
  -> task verifier/scorer
  -> structured result and Inspect log
```

## Work package

### 1. Reproducible environment

Add a Docker image suitable for Inspect coding tasks. It should contain:

- Python supported by the project;
- Node.js supported by Pi;
- Pi installed using a pinned version;
- the package under evaluation; and
- only the utilities needed by synthetic fixtures.

Do not bake credentials or provider URLs into the image.

### 2. Pi Inspect agent

Create an Inspect custom agent, tentatively `pi_agent()`, which:

1. starts `sandbox_agent_bridge()`;
2. injects a temporary Pi provider configuration pointing to the bridge;
3. uses model id `inspect`;
4. invokes Pi in JSON event mode with `--no-session`;
5. supplies the golden-case instruction;
6. collects stdout, stderr and exit state;
7. returns the bridge state and preserves the Pi trajectory; and
8. respects the case timeout.

Keep provider configuration creation in a small adapter with unit tests.

Confirm from current Inspect and Pi documentation whether generation
configuration should be controlled by Inspect or forwarded from Pi. Record the
decision in `decisions.md`.

### 3. Planning task

Implement an Inspect task backed by `evals/planning/sample.jsonl`.

Requirements:

- read-only sandbox behaviour;
- deterministic required/forbidden concept score;
- a placeholder extension point for independent rubric grading;
- outcome and wall-clock metrics; and
- raw Inspect logs.

### 4. Coding fixture and task

Create the missing synthetic fixture referenced by
`code-health-endpoint-001`. Keep it deliberately small but realistic:

- a minimal Python web service;
- existing tests;
- documented start command; and
- no health endpoint initially.

Create hidden verifier tests outside the model-visible working tree where the
framework supports that separation.

The coding task must:

- copy or initialise a fresh fixture;
- allow Pi file and shell tools only inside the sandbox;
- run the verifier after Pi finishes;
- report partial and complete success;
- retain the final diff; and
- destroy or replace the workspace before the next trial.

### 5. Result contract

Define a serialisable run record containing at least:

```text
run id
case id and dataset version
phase
trial number
model configuration identity
harness and Pi version
Inspect version
start time and wall duration
success and component scores
verifier results
input, cached-input and output tokens when available
model turns and tool calls
compactions, retries and errors
artifact paths
```

Do not duplicate the full Inspect transcript inside this record; reference the
Inspect log artifact.

### 6. Local smoke provider

Make it possible to run the scaffold against a configurable
OpenAI-compatible test endpoint without a DGX. The endpoint, model and key must
come from environment or ignored local configuration.

The smoke path exists to validate orchestration. It is not a benchmark result.

## Acceptance criteria

- `pytest` and `ruff check .` pass.
- A documented command runs the planning smoke case.
- A documented command runs the coding smoke case.
- Each run starts with a new task workspace and Pi session.
- Changing only the Inspect model configuration can redirect the same task from
  one provider to another.
- Coding verification is independent of the agent's final prose.
- A result artifact records configuration, outcome and timing.
- Missing Pi, Docker, endpoint or credentials fail with actionable errors.
- No secret or private evaluation content is committed.
- Architecture or configuration decisions discovered during implementation are
  reflected in `docs/decisions.md`.

## Suggested implementation order

1. Pin and build the sandbox image.
2. Prove the Inspect bridge with a one-message Pi run.
3. Capture and test Pi JSON events.
4. Implement planning case execution and scoring.
5. Add the coding fixture and verifier.
6. Add the result record.
7. Run the same smoke case against two model configurations.
8. Update documentation with actual commands and limitations.

## Explicitly deferred

- Leadership dashboard.
- Statistical confidence tooling beyond basic aggregation.
- Harbor adapter.
- Private datasets.
- DGX installation automation.
- Model hot-swapping.
- Multi-user throughput.
- Energy and hardware amortisation.

## Prompt for a local Codex session

Use this as the initial implementation prompt:

> Read AGENTS.md and every document it lists under Required context. Review the
> current scaffold and implement the next milestone in
> docs/implementation-handoff.md. Begin with the reproducible sandbox and the
> smallest Pi-to-Inspect bridge smoke test. Verify current Inspect and Pi APIs
> from their official documentation before encoding them. Keep examples
> synthetic and public-safe. Run tests and update docs/decisions.md whenever
> implementation evidence changes an assumption. Do not start dashboard or
> production infrastructure work.
