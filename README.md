# DGX Agent Evals

An open framework for evaluating coding-agent workflows against local and hosted
language models.

The initial use case is comparing a coding harness such as
[Pi](https://pi.dev/) across:

- local inference served from an NVIDIA DGX Spark;
- hosted inference exposed through an OpenAI-compatible API; and
- reference cloud models used as controls.

The benchmark measures the complete agent task, not only model generation
speed. It records outcome quality, wall-clock duration, model usage, tool
activity, retries, context pressure, and failures.

## Status

This repository is an early scaffold. It currently provides:

- a versioned golden-case format;
- dataset validation;
- basic deterministic planning-output scoring;
- a Pi JSON-event runner;
- synthetic planning and coding examples; and
- design documentation for the Inspect AI integration.

The containerised Pi-to-Inspect execution adapter and leadership report are the
next implementation milestones.

## Evaluation shape

```text
Golden cases
    |
    v
Evaluation runner -> isolated task workspace -> Pi harness
                                               |
                                               v
                                  OpenAI-compatible inference
                                  (DGX Spark or cloud control)
    |
    v
Deterministic verifiers + rubric scoring + performance metrics
```

## Principles

1. **Evaluate the system.** Model, harness, tools, context management and
   inference runtime all affect the result.
2. **Prefer objective verification.** Tests, builds and policy assertions take
   precedence over model judging.
3. **Separate planning from coding.** They have different context profiles,
   outputs and scoring needs.
4. **Keep comparisons reproducible.** Record model, quantisation, runtime,
   harness, sampling and dataset versions with every run.
5. **Keep the public benchmark synthetic.** Private golden cases should live in
   a separate private dataset or repository.

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
dgx-agent-evals validate evals/planning/sample.jsonl
dgx-agent-evals validate evals/coding/sample.jsonl
```

Installing the optional Inspect integration dependencies:

```bash
python -m pip install -e ".[inspect]"
```

## Documentation

- [Project context](docs/project-context.md) — start here
- [Decisions and open questions](docs/decisions.md)
- [Architecture](docs/architecture.md)
- [Evaluation strategy](docs/evaluation-strategy.md)
- [Model and context baselines](docs/model-baselines.md)
- [Implementation handoff](docs/implementation-handoff.md)
- [Roadmap](docs/roadmap.md)

## Public and private data

Do not commit proprietary repositories, internal prompts, architecture
standards, credentials, production traces, or protected golden cases here.
Use the public schemas and runners with a separately controlled dataset.

## License

No licence has been selected yet. Until a licence is added, normal copyright
rules apply.
