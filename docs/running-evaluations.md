# Run a benchmark

## 1. Set up the Mac

Follow [Clean Mac setup](setup-mac.md), then activate the local environment:

```bash
source .venv/bin/activate
```

## 2. Check a setup

```bash
pi-bench doctor \
  --model-profile hosted-quality \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profile vanilla \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local
```

`ready` means the Mac, Docker, model profile, and agent profile can be used.
If Docker or verifier files changed, run `pi-bench build-sandbox` and check
again.

## 3. Check the cases

```bash
pi-bench validate evals/starter/cases.jsonl
```

Each case contains:

- a clean starting repository;
- one requested outcome;
- time, turn, context, and token limits;
- a protected verifier;
- a quality threshold; and
- any critical checks that must pass.

## 4. Run cloud controls

```bash
pi-bench benchmark \
  --model-profile openai-codex-gpt-5.6-sol \
  --model-profile openai-codex-gpt-5.6-luna \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profile vanilla \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name starter-outcome-v1 \
  --epochs 3 \
  --resume
```

## 5. Run the local model

Use the same dataset, benchmark run name, agent profile, limits, Pi version, and
container:

```bash
pi-bench benchmark \
  --model-profile local-candidate \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profile vanilla \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name starter-outcome-v1 \
  --epochs 3 \
  --resume
```

## 6. Compare agent profiles

Keep the model fixed and repeat `--agent-profile`:

```bash
pi-bench benchmark \
  --model-profile hosted-quality \
  --agent-profile vanilla \
  --agent-profile team-agent \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name agent-profile-v1 \
  --epochs 3 \
  --resume
```

## 7. View results

```bash
pi-bench view \
  --results-dir results \
  --logs-dir logs \
  --inspect
```

The Pi Agent Bench dashboard compares setups. Inspect shows the full messages,
tool calls, edits, verifier output, tokens, time, and errors.

## 8. Recheck a saved result

```bash
pi-bench replay-outcome logs/<run>.eval
```

This applies the saved diff to a temporary starting repository and runs the
protected verifier again. It does not call the model.
