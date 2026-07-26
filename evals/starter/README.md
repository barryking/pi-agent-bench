# Owned starter suite

These five cases use code owned by this project. A fresh clone already has
everything needed to run them.

The suite covers:

1. filtering and validating an API-style user list;
2. fixing configuration precedence for false and empty values;
3. checking signed webhooks safely;
4. collecting cursor-paginated API results in Node; and
5. making SQLite user creation durable and idempotent.

Each job has a planning case and a coding case. The coding checks are protected
from Pi inside Docker.

Maintainers prove all five coding cases in both directions with:

```bash
python scripts/check-starter-verifiers.py
```

The untouched fixture must fail. The reference overlay must pass every
critical check. Reference overlays are test evidence and are not mounted into
an agent trial.

Start with one cloud profile:

```bash
pi-bench run coding \
  --dataset evals/starter/coding.jsonl \
  --profile hosted-quality \
  --profiles configs/model-baselines.local.json \
  --env-file .env.local \
  --campaign starter-check
```

Use three trials per model for a comparison:

```bash
pi-bench campaign coding \
  --dataset evals/starter/coding.jsonl \
  --run-profile hosted-quality \
  --run-profile local-candidate \
  --profiles configs/model-baselines.local.json \
  --env-file .env.local \
  --campaign starter-baseline-v1 \
  --epochs 3 \
  --resume
```
