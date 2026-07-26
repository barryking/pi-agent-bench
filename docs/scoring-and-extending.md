# Make and score benchmark cases

A case is one finished outcome.

## Create a draft

```bash
pi-bench new-case \
  --id outcome-example \
  --dataset evals/custom/outcome-example-v1.jsonl
```

This creates:

- the JSONL case;
- a starting repository folder; and
- a protected verifier that fails until you finish it.

Draft cases cannot run.

## Write a good instruction

Say what the user should be able to observe when the work is done.

Include:

- required behaviour;
- behaviour that must not change;
- important errors and limits;
- public tests the agent should add; and
- documentation that must change.

Do not tell the model how the protected verifier works.

## Build the starting repository

The starting repository is the clean code given to the agent. It should be:

- small enough to understand;
- realistic enough to matter;
- free of secrets;
- pinned to one version; and
- unchanged after every run.

Pi Agent Bench copies it into Docker. The original folder stays clean.

## Build the verifier

The verifier runs after Pi finishes. It prints one final JSON object:

```json
{
  "score": 0.8,
  "components": {
    "old_behaviour": 1,
    "new_behaviour": 1,
    "public_tests": 1,
    "documentation": 0
  },
  "explanation": "The behaviour works, but the documentation is missing."
}
```

Quality is from `0` to `1`.

Success requires:

1. quality at or above `success_threshold`; and
2. every `required_components` item to pass.

## Prove the case

A useful case must fail before the work and pass after a known-good solution:

```bash
pi-bench validate evals/custom/outcome-example-v1.jsonl
pi-bench build-sandbox

pi-bench prove-case \
  evals/custom/outcome-example-v1.jsonl \
  --known-good-diff <private-known-good.diff> \
  --output results/case-proofs/outcome-example.json
```

You can prove a case while it is still a draft. Keep private reference
solutions outside a public repository.

## Finish the draft

When the starting repository, verifier, proof, limits, and instructions are
ready, set:

```json
"draft": false
```

Then run:

```bash
pi-bench validate evals/custom/outcome-example-v1.jsonl
```

## Recommended limits

A normal case should usually fit inside:

- 30 minutes;
- 45 turns; and
- 150,000 total tokens.

Use smaller limits for small jobs. Confirm the case is possible with a strong
cloud model before using it to compare local models.
