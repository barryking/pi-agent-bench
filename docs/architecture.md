# How the system is built

Pi Agent Bench tests a whole coding workflow.

```text
case + Pi + model + tools + starting files + verifier
```

It does not test a model using only one text answer.

Inspect is the framework underneath this project. We use its normal tasks,
samples, scorers, logs, repeated trials, limits, and viewer. We do not keep a
second detailed run log.

## Main parts

### Pi Agent Bench

This repository provides:

- cases;
- model profiles;
- agent profiles;
- protected verifiers;
- small result records; and
- the comparison dashboard.

## Code map

The Python package is under `src/pi_agent_bench/`.

- `cli.py` connects command names to small handlers.
- `cli_parser.py` describes command-line options.
- `cli_commands.py` handles setup, cases, exports, and reports.
- `cli_execution.py` checks models and starts Inspect runs.
- `agent_profiles.py` checks and fingerprints selected Pi resources.
- `inspect_tasks.py`, `inspect_agent.py`, and `inspect_scorers.py` are the
  Inspect integration.
- `verification.py` reads scores and protected verifier output.
- `workspace.py` prepares temporary coding workspaces.
- `run_records.py` and `reporting.py` make rebuildable comparison files.
- `viewer/` contains separate HTML, CSS, data, statistics, chart, and startup
  files for the local dashboard.

These boundaries keep the command entry point and dashboard from becoming one
large file.

### Inspect AI

Inspect controls the evaluation.

It:

- loads cases;
- starts trials;
- creates Docker sandboxes;
- applies time and token limits;
- stores full logs;
- runs scorers; and
- calculates result statistics.

### Pi

Pi is the coding agent being tested.

Pi reads files, asks the model questions, uses tools, and changes code. We use
the real Pi loop instead of making a smaller copy of it.

An agent profile chooses Pi's tools and optional resources. A model profile
chooses the inference model. Keeping them separate lets one model be tested
with several agent setups.

### Docker

Every trial gets a clean Docker container.

The container holds:

- Pi;
- the starting files;
- allowed tools; and
- only the secret needed for that run.

The container is removed after the trial.

### Model server

The model may run:

- on a DGX;
- on another local computer;
- through a cloud API; or
- through a Pi subscription login.

Changing the profile changes the model route. It does not change the case.

Changing the agent profile changes Pi's tools or instructions. It does not
change the model.

## Normal model route

For API and OpenAI-compatible models:

```text
Pi in Docker
  └─ Inspect bridge on the Mac
       └─ chosen model
```

The bridge lets Inspect see model requests and usage. Pi receives a temporary
bridge key, not the real provider key.

## Subscription route

Some subscription models are called directly by Pi:

```text
Pi in Docker
  └─ chosen subscription provider
```

Pi Agent Bench copies only the chosen provider login into the temporary Pi home.
It destroys the copy with the container.

This route gives Inspect less direct model information. Pi event records are
used to count turns and tokens.

## One trial

```text
1. Load one case.
2. Copy the starting files.
3. Copy only the chosen agent-profile resources into a new Pi home.
4. Start a clean container and Pi session.
5. Connect Pi to one model.
6. Let Pi work until it finishes or reaches a limit.
7. Run the protected verifier or planning grader.
8. Save the full Inspect log.
9. Save the small result record and code diff.
10. Remove the container.
```

## Planning and coding stay separate

A planning trial asks for a plan.

A coding trial asks for code changes.

If we later join them, coding will receive only the final saved plan. It will
not receive the whole planning conversation. This keeps the coding context
clean.

## Limits

Each case has its own:

- time limit;
- turn limit;
- one-request context limit; and
- whole-trial token limit.

Cases with different run limits become different Inspect tasks. A small case
does not inherit a larger case's limits.

## Scoring

Inspect stores separate fields for:

- quality;
- success; and
- each declared rubric or verifier part.

Coding cases may mark some verifier parts as required. Quality still shows
partial progress, but success is false when any required part fails.

The small Pi Agent Bench record is made from the Inspect score. Inspect remains
the main evidence.

Rebuild the small chart records from Inspect with:

```bash
pi-bench export --logs-dir logs --results-dir results
```

Only complete and error-free scores enter comparisons.

## Coding replay

The original coding container no longer exists after a run.

To check the score again, Pi Agent Bench:

1. copies the original fixture;
2. applies the saved code diff;
3. starts the pinned Docker image with no network;
4. runs the protected verifier; and
5. compares the old and new score.

The host fixture is not changed.

## Security rules

- The AI runs as a normal, non-root user.
- Protected verifiers are outside the AI-readable workspace.
- Verifiers run only after Pi stops.
- Personal Pi skills and sessions are disabled.
- Pi update checks and package downloads are disabled during trials.
- Only resources named by the agent profile can be added.
- Agent resource contents and secrets are not written into result records.
- Private credentials are not written into results.
- The DGX receives model text, not a mounted Mac filesystem.
- Public examples must not contain private company data.

## Where work happens

```text
Mac
  Inspect, Docker, cases, verifiers, logs, dashboard

Temporary Docker container
  Pi, tools, copied fixture

Model server
  model inference only
```
