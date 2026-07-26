# Rules for people and AI helpers

## The goal

Build a fair, repeatable way to compare planning and coding agents. The same
tests must work with local models and cloud models.

## Read these pages first

Before changing how the framework works, read:

1. `README.md`
2. `docs/decisions.md`
3. `docs/architecture.md`
4. `docs/scoring-and-extending.md`
5. `docs/roadmap.md`

These pages describe the choices the project has made. If the code proves that
a choice is wrong, update the page as part of the same change.

## Rules

- Only commit examples that are safe to make public.
- Keep planning tests and coding tests separate.
- For coding, prefer repeatable tests over asking another model to judge.
- Run every agent in a new throw-away workspace.
- Record the model, model version, server, harness, Pi, and dataset versions.
- Do not say a feature works until an automated test has checked it.
- Keep special provider behaviour in a small adapter.
- Keep `docs/roadmap.md` honest when work is completed or added.

## Checks

```bash
python -m pip install -e ".[dev]"
docker compose -f docker/compose.yaml build
ruff check .
pytest
pi-bench validate evals/planning/sample.jsonl
pi-bench validate evals/coding/sample.jsonl
pi-bench versions
```

`ruff` is installed by `.[dev]`. It checks Python code for common
mistakes and style problems.

## A change is done when

- tests cover the new behaviour;
- public examples contain no private information;
- docs say which numbers were measured and which were guessed; and
- changed cases get a new dataset version when old and new results should not
  be compared.
