# Decisions and open questions

This file records current project decisions. Change it when evidence changes a
decision; do not let implementation silently become the architecture.

## Accepted decisions

### Evaluate complete agent workflows

The benchmark evaluates task completion through Pi, not raw model completions.

**Reason:** Harness behaviour, tools, context management and recovery materially
affect real outcomes.

### Use Inspect AI as the initial controller

Inspect AI is the primary framework for datasets, agent execution, sandboxes,
scoring, limits, logs and analysis.

**Reason:** It supports agent and coding evaluations and provides an agent
bridge suitable for an OpenAI-compatible CLI harness.

### Keep Pi as the agent under test

The framework invokes the real Pi harness rather than recreating its loop inside
Inspect.

**Reason:** Replacing the harness would answer a different question from the
developer workflow being considered.

### Run tasks in disposable environments

Coding cases run inside fresh isolated workspaces. Planning cases are read-only
unless a specific case requires otherwise.

**Reason:** This prevents cross-task contamination and limits the effects of
model-generated commands.

### Start a fresh session for every task

Planning and coding cases never reuse another case's Pi session.

**Reason:** Results must be independent and comparable.

### Separate planning from coding

End-to-end cases pass a final frozen planning artifact into a new coding
session, not the entire planning transcript.

**Reason:** Planning and coding have different context and scoring needs.

### Prefer deterministic coding verification

Tests and explicit assertions are the primary coding score.

**Reason:** Reference-patch similarity and model judging can penalise correct
alternative implementations.

### Use independent and calibrated planning grading

The candidate model does not grade itself. Model grading is calibrated against
human review.

**Reason:** Planning quality is semantic, but an uncalibrated judge introduces
another uncontrolled model dependency.

### Use the same harness for local and hosted controls

All compared models run through the same Pi version, task, tools and limits.

**Reason:** Otherwise the experiment confounds model and harness quality.

### Default to a 128K operating profile

Initial comparisons use 128K before testing larger boundary profiles.

**Reason:** It covers the expected 20–60K task inputs while leaving meaningful
room for tools and output, without making maximum-context latency the default.

### Keep public and private datasets separate

This repository remains public-safe. Protected golden cases live elsewhere.

**Reason:** The framework can be reusable without publishing proprietary
evaluation material.

## Provisional choices

These should be tested before becoming accepted decisions:

- Qwen3.6-35B-A3B as a fast planner.
- Qwen3.5-122B-A10B as a stronger planning candidate.
- Qwen3-Coder-Next FP8 as the first specialist coder.
- vLLM as the first DGX serving runtime.
- Prefix caching enabled for production-like coding runs.
- Three trials per case during exploration.
- 20–30 planning and 30–50 coding cases before leadership conclusions.

## Open questions

### Model/runtime

- Which model provides the best planning quality on a single Spark?
- Is a separate planning and coding model materially better than one resident
  model, given model-loading time?
- Which quantisation preserves enough reliability?
- What vLLM/SGLang/other runtime version is stable on GB10?
- What context and KV-cache configuration gives the best usable trade-off?

### Harness integration

- Does Pi need a small extension for richer telemetry, or is JSON event mode
  sufficient?
- How should Pi's custom provider configuration be injected into each
  container?
- Which generation parameters must the Inspect bridge forward?
- How should prefix-cache hits be correlated with Pi turns?

### Dataset

- Which real completed planning and coding tasks can be converted into private
  golden cases?
- How will private task fixtures be versioned without leaking expected outputs?
- What distribution of task difficulty and context size is representative?
- How will benchmark contamination be detected?

### Scoring

- Which independent judge model and rubric are sufficiently stable?
- How many human-reviewed cases are required to calibrate planning scores?
- How should partial coding success be weighted?
- Which failure categories need human adjudication?

### Reporting and decision threshold

- What minimum quality relative to the hosted control makes local inference
  investable?
- What latency is acceptable for planning versus interactive coding?
- How should hardware cost, energy, privacy and operational effort be weighted?
- Should leadership receive one recommendation or a workload-by-workload
  routing proposal?

### Repository

- Which open-source licence should be selected?
- Should public benchmark results live in this repository or a separate site?
