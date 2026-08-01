# Rules for people and AI helpers

## The goal

Build a fair, repeatable way to compare coding-agent outcomes. The same
tests must work with local models and cloud models.

## Read these pages first

Before changing how the framework works, read:

1. `README.md`
2. `docs/decisions.md`
3. `docs/architecture.md`
4. `docs/scoring-and-extending.md`
5. `docs/roadmap.md`

Read `docs/agent-profiles.md` too when changing Pi tools, instructions, skills,
extensions, prompt templates, settings, or MCP support.

These pages describe the choices the project has made. If the code proves that
a choice is wrong, update the page as part of the same change.

## Rules

- Only commit examples that are safe to make public.
- Score the finished outcome with repeatable evidence.
- Prefer repeatable tests over asking another model to judge.
- Run every agent in a new throw-away workspace.
- Record the model, model version, server, agent profile, harness, Pi, and
  dataset versions.
- Do not say a feature works until an automated test has checked it.
- Keep new or materially changed cases as drafts until a maintainer proof shows
  untouched failure and known-good success.
- Trial proved candidates before accepting them into a maintained dataset.
- Keep special provider behaviour in a small adapter.
- Keep `docs/roadmap.md` honest when work is completed or added.

## Checks

```bash
python -m pip install -e ".[dev]"
scripts/check-all.sh
```

This builds and fingerprints the sandbox, runs `ruff` and the Python tests,
validates both datasets, proves the starter cases and agent-profile examples,
and tests the dashboard statistics. `ruff` is installed by `.[dev]`.

## A change is done when

- tests cover the new behaviour;
- public examples contain no private information;
- docs say which numbers were measured and which were guessed; and
- changed cases get a new dataset version when old and new results should not
  be compared.
