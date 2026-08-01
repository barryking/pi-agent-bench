# Owned starter suite

This suite has five complete repository jobs:

- user filtering and pagination validation;
- configuration precedence with false and empty values;
- webhook signature checking;
- cursor pagination in a Node client; and
- durable SQLite idempotency.

The starting repositories and verifiers are owned by this project. No outside
repository is downloaded.

Each case must fail before the requested work and pass after a known-good
solution. Maintainers check all five with:

```bash
python scripts/check-starter-verifiers.py
```

That proof is part of repository maintenance. Normal benchmark users do not
need to run `prove-case` or supply reference solutions.

Validate the dataset:

```bash
pi-bench validate evals/starter/cases.jsonl
```

Run one model:

```bash
pi-bench run \
  --model-profile hosted-quality \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name starter-outcome-v1
```

Run several models or agent profiles with `pi-bench benchmark`. Every setup gets
the same starting repositories and final verifiers.
