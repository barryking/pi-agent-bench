# Project context

## Executive summary

The purpose of this project is to determine whether local inference has reached
a level of quality and usability that justifies investment for real software
planning and coding workflows.

The target hardware is an NVIDIA DGX Spark. A developer works from a Mac using
the Pi coding harness. Pi reads and edits the developer's local workspace and
uses the Spark as a remote OpenAI-compatible inference provider. Hosted models
run through the same harness as controls.

The decision cannot be made from parameter count or tokens per second alone.
The evidence must show whether the complete agent workflow:

- understands representative planning and coding tasks;
- produces correct, maintainable outcomes;
- completes them in an acceptable amount of time;
- remains reliable across repeated runs;
- behaves acceptably with realistic context; and
- offers a worthwhile quality, privacy, cost and operational trade-off against
  hosted inference.

This repository contains the public framework and synthetic examples. It must
not contain proprietary source code, internal standards, protected prompts or
private golden cases.

## Problem

Local model comparisons are often misleading because they measure isolated
generation speed or generic academic questions. Neither closely represents a
developer asking an agent to inspect a repository, use tools, recover from
errors, modify code and prove that the result works.

The relevant unit of evaluation is therefore:

```text
task + context + harness + model + runtime + tools + verifier
```

Changing any of these may change the result. Every benchmark record must make
that configuration visible.

## Users and decisions

### Primary user

A technical evaluator running repeatable experiments from a Mac against a DGX
Spark and hosted models.

### Audience

Engineering and architecture leadership deciding whether to:

- purchase or expand local inference hardware;
- adopt local models for specific planning or coding workflows;
- keep hosted inference as the default;
- use a hybrid routing model; or
- continue experimenting until local capability improves.

### Decision supported

The framework should enable a statement such as:

> On version X of our representative dataset, local configuration Y completed
> Z% of tasks versus A% for the hosted control. Median successful-task duration
> was B versus C, with the following material capability gaps and operational
> trade-offs.

## Target developer workflow

The normal interactive workflow is:

```text
Mac
  Pi coding harness
  local repository and tools
        |
        | OpenAI-compatible HTTPS/LAN request
        v
DGX Spark
  vLLM or another measured serving runtime
  selected open-weight model
```

The Spark performs inference only. Pi remains responsible for the agent loop,
file access and tool execution on the Mac.

Network overhead on a local wired network is expected to be small relative to
prompt processing and generation, but it must still be measured rather than
assumed.

## Evaluation workflow

For automated evaluation, the repository is replaced with a disposable task
workspace:

```text
Golden case
    |
    v
Inspect AI controller
    |
    v
Disposable container containing Pi and the task fixture
    |
    v
Inspect model bridge
    |
    +----> DGX Spark inference
    |
    +----> hosted control inference
```

Inspect AI is the proposed primary controller because it supplies the dataset,
solver, scorer, sandbox, limits, logs and analysis abstractions. Pi is still
the system under test; Inspect must not replace Pi's agent loop.

Harbor may later provide external calibration through recognised terminal and
coding benchmarks, but the first implementation should use one framework to
avoid duplicated orchestration and reporting.

## Evaluation phases

### Planning

A planning case supplies a problem and controlled context. The model may inspect
read-only files and produces a bounded architecture or implementation artifact.

Planning is scored against:

- explicit constraints that must be recognised;
- important decisions or alternatives;
- risks and unknowns;
- prohibited recommendations;
- completeness; and
- clarity and actionability.

Planning usually cannot be graded by exact output equality. Objective facts
should be checked deterministically. Semantic quality should use a calibrated
rubric, an independent judge model and sampled human review.

### Coding

A coding case starts from a clean synthetic or privately mounted repository
fixture. Pi can read, edit and execute commands inside the disposable
environment.

Coding is primarily scored using hidden tests, build checks, static analysis,
required behaviour and forbidden-change assertions. Similarity to a reference
patch is supporting information only.

Every coding task starts a new Pi session. Previous tasks must not consume
context or leak information.

### End to end

An end-to-end case produces a planning artifact and then starts a separate
coding session. The coding session receives the frozen final plan, not the
planning transcript. This reflects the intended working pattern and keeps the
coding context focused.

## Initial context profiles

The initial operating profile is 128K for both planning and coding, with
separate context-band experiments.

Planning bands:

- 32K;
- 64K;
- 128K;
- 192K stress; and
- 224K boundary.

Coding bands:

- 32K;
- 64K;
- 96K;
- 128K; and
- approximately 160K stress when the runtime supports it.

The context window includes system instructions, tool definitions, supplied
material, model output and the accumulated agent trajectory. The usable source
budget is therefore lower than the configured model limit.

Context tests must use meaningful relevant and distracting material. Repeating
or padding arbitrary text does not establish whether the model can find and
apply information in a realistic task.

## Initial model hypotheses

These are candidates to test, not adopted choices:

- Qwen3.6-35B-A3B for fast thinking and planning;
- Qwen3.5-122B-A10B in a measured quantisation for stronger planning;
- Qwen3-Coder-Next FP8 for agentic coding; and
- hosted quality and cost controls.

Model identity includes weights, quantisation, runtime, attention backend,
context limit, KV-cache configuration, prefix caching and sampling. Results
must not collapse materially different configurations under the same name.

## Evidence needed

### Outcome

- pass@1 and success across repeated runs;
- perfect-task and partial-verifier rates;
- planning-rubric score;
- regression rate;
- human preference on a sample; and
- failure categories.

### Time

- total wall-clock duration;
- time to first token;
- time to first useful action;
- cold prompt-processing duration;
- warm-turn duration;
- model time versus tool and verifier time; and
- p50 and p95 successful-task duration.

### Agent efficiency and reliability

- input, cached and output tokens;
- output tokens per second;
- model turns;
- tool calls and failures;
- retries and recovery;
- peak context and compactions;
- timeouts; and
- infrastructure errors.

### Economics and operation

- hosted token cost;
- local hardware amortisation assumptions;
- energy measurements when available;
- runtime maintenance effort; and
- concurrency and utilisation constraints.

## Public/private boundary

This public repository may contain:

- schemas;
- framework code;
- synthetic fixtures;
- generated test data;
- public model and runtime configuration examples; and
- aggregate results that are safe to publish.

It must not contain:

- private repositories or patches;
- internal architecture or policy documents;
- production prompts or traces;
- personal or customer data;
- credentials or private endpoints; or
- private golden expected outputs.

Private datasets should conform to the public schema and be mounted at runtime
or referenced from a separate access-controlled repository.

## Non-goals for the first implementation

- Building a general-purpose model-serving platform.
- Fine-tuning or training models.
- Producing a polished web dashboard.
- Replacing Pi with a custom agent.
- Making a production deployment decision from a tiny synthetic sample.
- Treating an LLM judge as unquestioned ground truth.
- Optimising for multi-user throughput before single-user usefulness is known.

## What success looks like for the first milestone

One planning case and one coding case can run end to end through:

```text
Inspect -> disposable Pi environment -> configurable model endpoint -> scorer
```

The run produces a structured artifact containing configuration, outcome,
wall-clock time, model usage, tool trajectory, verifier result and errors. The
same cases can be executed against a local and hosted endpoint without changing
their task definition.
