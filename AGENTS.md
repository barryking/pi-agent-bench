# Repository guidance

## Goal

Build a reproducible framework for comparing complete planning and coding-agent
workflows across local and hosted models.

## Required context

Before proposing architecture or making substantial changes, read:

1. `docs/project-context.md`
2. `docs/decisions.md`
3. `docs/architecture.md`
4. `docs/evaluation-strategy.md`
5. `docs/implementation-handoff.md`

Treat those documents as the current project contract. If implementation
evidence invalidates an assumption, update the relevant document in the same
change rather than silently diverging from it.

## Working rules

- Keep all committed examples synthetic and safe for a public repository.
- Treat planning and coding as separate evaluation phases.
- Prefer deterministic verifiers over output similarity or model judging.
- Run agents only inside an isolated disposable workspace.
- Record model, quantisation, inference runtime, harness and dataset versions.
- Do not claim an integration or metric is complete unless it is exercised by
  an automated test.
- Keep provider-specific behaviour behind small adapters.
- Implement the smallest current milestone in `docs/implementation-handoff.md`;
  do not jump ahead to dashboards or production infrastructure.

## Commands

```bash
python -m pip install -e ".[dev]"
pytest
dgx-agent-evals validate evals/planning/sample.jsonl
dgx-agent-evals validate evals/coding/sample.jsonl
```

## Definition of done

- Tests cover the changed behaviour.
- Public examples contain no private or company-specific information.
- Documentation distinguishes measured results from estimates.
- Benchmark changes remain comparable or explicitly version the dataset.
