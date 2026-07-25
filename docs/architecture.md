# Architecture

## Scope

The framework evaluates an agentic task as an end-to-end execution:

```text
task -> harness -> model -> tools -> workspace changes -> verifier
```

It is not intended to be a raw language-model benchmark. Tokens per second is
useful diagnostic data, but it does not establish whether an agent completes a
task correctly.

## Proposed components

### Evaluation controller

[Inspect AI](https://inspect.aisi.org.uk/) is the proposed controller. It
provides datasets, solvers, scorers, sandboxes, execution limits, model
comparison, logs and analysis.

### Agent harness

Pi is executed as the real coding harness rather than reimplementing its tool
loop. It should run in JSON event mode using an ephemeral session.

### Agent bridge

Inspect's sandbox agent bridge exposes a local OpenAI-compatible endpoint to
the agent process. Pi calls that endpoint, while Inspect routes requests to the
model selected for the run and captures model activity.

### Model providers

The first providers should be:

1. a DGX Spark vLLM endpoint;
2. one strong hosted model as a quality control; and
3. one cost-efficient hosted model as a price/performance control.

Provider endpoints and credentials are runtime configuration. They must never
be committed.

### Task environments

Every coding case runs in a new disposable container or equivalent isolated
workspace. A case defines:

- starting fixture;
- natural-language instruction;
- limits;
- verification command; and
- expected properties.

Planning cases are read-only by default. They may include a controlled context
pack but must not modify a repository.

## Execution sequence

```text
1. Load a versioned golden case.
2. Create a clean task environment.
3. Start Inspect and the model bridge.
4. Start a fresh Pi session in the task environment.
5. Execute until completion or a configured limit.
6. Run deterministic verification.
7. Apply optional rubric or independent model grading.
8. Store outcome, timing, usage, trajectory and configuration.
9. Destroy the task environment.
```

## Security boundary

The public repository contains framework code and synthetic examples only.
Private golden data should be mounted at runtime from a separately controlled
location. Agent containers should receive only the case fixture and the minimum
credentials needed to reach the evaluation proxy.

## Important implementation decisions

- Prefix caching is part of the runtime configuration and must be recorded.
- Cold-start and warm-turn latency are reported separately.
- The candidate model must not grade itself.
- Planning transcripts are not copied into coding sessions. Coding receives a
  frozen planning artifact when an end-to-end case requires one.
- Quantisation changes create a new model configuration; they are not silently
  grouped under the same model result.
