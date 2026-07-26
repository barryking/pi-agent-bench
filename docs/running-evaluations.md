# Running and comparing models

This page shows the safe order for a real comparison.

## Why cloud models go first

Test a new case with strong cloud models before testing a local model.

This answers an important question:

> Is the case clear and possible?

If strong cloud models keep failing, the case may be too large, unclear, or
broken. Fix the case before blaming a local model.

## 1. Check every profile

List the profiles:

```bash
pi-bench profiles \
  --profiles configs/model-baselines.local.json
```

Check each one:

```bash
pi-bench doctor \
  --profile hosted-quality \
  --profiles configs/model-baselines.local.json \
  --env-file .env.local
```

Do not run a profile until `doctor` says it is ready.

## 2. Check the cases

```bash
pi-bench validate evals/planning/sample.jsonl
pi-bench validate evals/coding/sample.jsonl
```

For the first real pilot, use:

```bash
pi-bench validate evals/pilots/user-list-filter/planning.jsonl
pi-bench validate evals/pilots/user-list-filter/coding.jsonl
```

Its coding case has been proved with an untouched failure and a known-good
success.

For a new coding case:

1. the untouched fixture must fail;
2. a known-good answer must pass;
3. the verifier must check behaviour, not one exact code shape;
4. the task should fit inside 30 minutes, 45 turns, and 150,000 total tokens.

Draft cases cannot run.

## 3. Run hosted controls

For coding:

```bash
pi-bench campaign coding \
  --run-profile hosted-quality \
  --run-profile hosted-cost \
  --profiles configs/model-baselines.local.json \
  --env-file .env.local \
  --campaign case-check-v1 \
  --epochs 3 \
  --resume
```

Read every failure in Inspect. A good case should normally succeed in at least
two of three trials on both capable cloud models.

## 4. Run the local model

Use the same:

- dataset;
- campaign name;
- number of trials;
- Pi version;
- Docker image;
- tools; and
- limits.

```bash
pi-bench campaign coding \
  --run-profile local-candidate \
  --profiles configs/model-baselines.local.json \
  --env-file .env.local \
  --campaign case-check-v1 \
  --epochs 3 \
  --resume
```

Using the same campaign name tells the dashboard these results belong together.

## 5. Run planning

Planning needs a separate grader model:

```bash
pi-bench campaign planning \
  --run-profile hosted-quality \
  --run-profile hosted-cost \
  --run-profile local-candidate \
  --grader-profile independent-grader \
  --profiles configs/model-baselines.local.json \
  --env-file .env.local \
  --campaign planning-check-v1 \
  --epochs 3 \
  --resume
```

The grader must not grade itself.

## 6. See the results

Rebuild the small chart files from Inspect:

```bash
pi-bench export --logs-dir logs --results-dir results
```

```bash
pi-bench view \
  --results-dir results \
  --logs-dir logs \
  --inspect
```

Use the Pi Agent Bench dashboard to compare models.

The Inspect log is the main evidence. The dashboard data is a copy.

Use Inspect to answer questions such as:

- What did Pi ask the model?
- Which tools did it use?
- Where did it get stuck?
- Why did the verifier fail?

## What to compare

Look at several facts together:

- success rate;
- quality score;
- failed verifier parts;
- time for successful tasks;
- tokens used for successful tasks;
- tool failures;
- retries;
- cost, when the provider reports it;
- output tokens each second for local servers; and
- examples of good and bad runs.

Do not choose a winner using one number alone.

## When ranking is allowed

The dashboard only ranks models when:

- at least two profiles are present;
- every profile has the same shared cases;
- at least five cases are shared;
- every profile and case has at least three trials;
- the dataset version matches; and
- the benchmark files match.

If these rules are not met, the dashboard still shows the data. It also says
why the evidence is not ready for ranking.

## Cold and warm local runs

A cold run starts without a useful cache.

A warm run may reuse saved model work.

Keep them in separate campaigns or label them:

```bash
--cache-state cold
```

or:

```bash
--cache-state warm
```

Do not mix cold and warm results in one comparison.

## If a run stops

Use `--resume`. Inspect will keep completed work and continue missing work.

Interrupted or broken attempts are stored under:

```text
results/_invalid/
```

They do not enter model rankings.

## Check old work again

Re-grade planning:

```bash
pi-bench rescore-planning logs/<planning-log>.eval \
  --grader-profile independent-grader \
  --profiles configs/model-baselines.local.json \
  --env-file .env.local
```

Replay coding verification:

```bash
pi-bench replay-coding logs/<coding-log>.eval
```

This avoids paying the candidate model to repeat work it already did.
