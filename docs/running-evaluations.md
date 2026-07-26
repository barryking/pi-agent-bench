# Running and comparing models

This page shows the safe order for a real comparison.

## Why cloud models go first

Test a new case with strong cloud models before testing a local model.

This answers an important question:

> Is the case clear and possible?

If strong cloud models keep failing, the case may be too large, unclear, or
broken. Fix the case before blaming a local model.

## 1. Check every model and agent profile

List the model profiles:

```bash
pi-bench model-profiles \
  --model-profiles-file configs/model-baselines.local.json
```

Check each one:

```bash
pi-bench doctor \
  --model-profile hosted-quality \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local
```

Do not run a profile until `doctor` says it is ready.

List agent profiles:

```bash
pi-bench agent-profiles \
  --agent-profiles-file configs/agent-profiles.local.json
```

Use `vanilla` for model comparisons. If you are testing agent changes, check
the chosen pair:

```bash
pi-bench doctor \
  --model-profile hosted-quality \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profile team-agent \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local
```

## 2. Check the cases

```bash
pi-bench validate evals/planning/sample.jsonl
pi-bench validate evals/coding/sample.jsonl
```

For the five owned starter cases:

```bash
pi-bench validate evals/starter/planning.jsonl
pi-bench validate evals/starter/coding.jsonl
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
  --model-profile hosted-quality \
  --model-profile hosted-cost \
  --dataset evals/starter/coding.jsonl \
  --model-profiles-file configs/model-baselines.local.json \
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
  --model-profile local-candidate \
  --dataset evals/starter/coding.jsonl \
  --model-profiles-file configs/model-baselines.local.json \
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
  --model-profile hosted-quality \
  --model-profile hosted-cost \
  --model-profile local-candidate \
  --dataset evals/starter/planning.jsonl \
  --grader-model-profile independent-grader \
  --model-profiles-file configs/model-baselines.local.json \
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

## Compare agent setup

Agent changes can be tested with the same cases and model:

```bash
pi-bench campaign coding \
  --model-profile hosted-quality \
  --agent-profile vanilla \
  --agent-profile team-agent \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local \
  --dataset evals/starter/coding.jsonl \
  --campaign agent-check-v1 \
  --epochs 3 \
  --resume
```

The two model-and-agent pairs are separate comparison arms. Keep every other
setting unchanged. Read [Agent profiles](agent-profiles.md).

## When ranking is allowed

The dashboard only ranks models when:

- at least two profiles are present;
- every model-and-agent pair has the same shared cases;
- at least five cases are shared;
- every model-and-agent pair and case has at least three trials;
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
  --grader-model-profile independent-grader \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local
```

Replay coding verification:

```bash
pi-bench replay-coding logs/<coding-log>.eval
```

This avoids paying the candidate model to repeat work it already did.
