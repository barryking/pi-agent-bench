# Scoring and making cases

A case is more than a prompt. It also says how to check the answer.

Most new cases do not need new framework code.

- A planning case needs JSON and a rubric.
- A coding case needs JSON, starting files, and a verifier.

The built-in Inspect tasks and scorers do the rest.

## Quality and success

Quality is a number from `0` to `1`.

Success is quality compared with the case's success line.

```text
quality >= success threshold  → success
quality < success threshold   → failure
```

Changing the task, rubric, verifier, or success line changes the case. Give the
dataset a new version when this happens.

## Planning cases

A planning case asks for a plan. It does not ask the AI to change code.

The case contains:

- important facts the plan must notice;
- bad ideas it must avoid;
- a rubric;
- a success line; and
- optional files the AI may read.

A rubric is a short score guide.

Example:

```json
{
  "id": "rollout",
  "description": "The plan explains a safe release, checks, and rollback.",
  "weight": 1
}
```

The grader gives each rubric part a score from `0` to `4`:

- `0` — missing or wrong;
- `1` — very weak;
- `2` — partly useful;
- `3` — good;
- `4` — complete and ready to use.

Pi Agent Bench turns these scores into a number from `0` to `1`.

The grader is still an AI. People must check a hidden sample of its grades.

## Coding cases

A coding case gives Pi a clean copy of some files.

After Pi stops, a protected verifier checks the work.

A good verifier checks things such as:

- required behaviour;
- old behaviour still working;
- tests;
- build or type checks;
- required files;
- forbidden changes; and
- useful documentation.

It must not require one exact patch. Two different correct solutions should
both pass.

The verifier prints one JSON object:

```json
{
  "score": 0.75,
  "components": {
    "required_behaviour": 1,
    "regression": 1,
    "tests": 0,
    "documentation": 1
  },
  "explanation": "The public tests are missing."
}
```

The component names must also appear in `metadata.score_components`.

## Create a safe draft

Planning:

```bash
pi-bench new-case planning \
  --id plan-example-001 \
  --dataset evals/custom/planning-example-v1.jsonl
```

Coding:

```bash
pi-bench new-case coding \
  --id code-example-001 \
  --dataset evals/custom/coding-example-v1.jsonl
```

The draft cannot run. This is on purpose.

An AI can help finish it. Ask the AI to:

1. inspect the repository;
2. write one clear task;
3. list every rule the answer must follow;
4. make deterministic checks;
5. show that the untouched fixture fails;
6. show that a known-good answer passes; and
7. explain every score component.

Only then set:

```json
"draft": false
```

For a coding case, keep the known-good patch outside the public repository.
Then prove both sides:

```bash
pi-bench prove-case \
  evals/custom/code-example-001/coding.jsonl \
  --known-good-diff <private-known-good.diff> \
  --output results/case-proofs/code-example-001.json
```

The saved proof contains the patch hash and both scores. It does not copy the
patch.

## Planning case shape

```json
{
  "id": "plan-example-001",
  "phase": "planning",
  "instruction": "Write a plan for ...",
  "context_files": [],
  "tags": ["planning"],
  "limits": {
    "seconds": 900,
    "turns": 18,
    "context_tokens": 65536,
    "total_tokens": 65536
  },
  "expected": {
    "required_concepts": ["rollback"],
    "forbidden_concepts": [],
    "verifier_command": [],
    "success_threshold": 0.75,
    "rubric": [
      {
        "id": "rollout",
        "description": "Explains release checks and rollback.",
        "weight": 1
      }
    ]
  },
  "metadata": {
    "dataset_version": "1.0",
    "draft": false,
    "synthetic": false
  }
}
```

## Coding case shape

```json
{
  "id": "code-example-001",
  "phase": "coding",
  "instruction": "Add ...",
  "context_files": [],
  "tags": ["coding"],
  "limits": {
    "seconds": 1800,
    "turns": 45,
    "context_tokens": 65536,
    "total_tokens": 150000
  },
  "expected": {
    "required_concepts": [],
    "forbidden_concepts": [],
    "verifier_command": [
      "python3",
      "/opt/verifiers/code-example-001/verify.py"
    ],
    "success_threshold": 1
  },
  "metadata": {
    "dataset_version": "1.0",
    "fixture": "fixtures/code-example-001",
    "score_components": ["requirements", "regression", "tests"],
    "draft": false,
    "synthetic": false
  }
}
```

## Understand the limits

- `seconds` is the most time one case may use.
- `turns` is the most back-and-forth model steps.
- `context_tokens` is the most text one model request may hold.
- `total_tokens` is the most text used by the whole trial.

One coding case should normally fit inside:

- 30 minutes;
- 45 turns;
- 150,000 total tokens.

The normal path should use less. The limit leaves room for mistakes and
recovery.

## Accept a new case

Before using a case for ranking:

1. freeze the task and starting files;
2. freeze the rubric or verifier;
3. prove the untouched coding fixture fails;
4. prove a known-good coding answer passes;
5. run at least two capable cloud models;
6. run three trials per cloud model;
7. inspect disagreements and close scores;
8. fix unclear rules;
9. give the final dataset a new version; and
10. run local models without changing the case.

The first two pilots live under `evals/pilots/`. Start with
`user-list-filter`. It is smaller than the idempotency case.

## Add a model

Copy the example profile file with:

```bash
pi-bench init
```

A profile records the exact model and server settings. Secrets stay in
`.env.local`.

Check it:

```bash
pi-bench doctor \
  --profile <profile-name> \
  --profiles configs/model-baselines.local.json \
  --env-file .env.local
```

## Subscription models

A Pi subscription profile uses a Pi login file instead of an API key.

Pi Agent Bench copies only the chosen login into the temporary container. It does
not save the secret in results.

Subscription cost is not the same as a price for one request. The cost field is
left empty instead of pretending the cost is zero.

## Human check for planning grades

This is still required before trusting planning rankings:

1. hide the model name;
2. give the same rubric to at least two people;
3. have them score the same plans;
4. discuss large disagreements;
5. compare the human scores with the AI grader;
6. fix unclear rubric text; and
7. repeat this check from time to time.

Automation can prepare the evidence. It cannot invent honest human judgment.
