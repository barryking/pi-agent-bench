# Runnable profile examples

This directory contains public, owned examples for every profile layer.

## Files

```text
pi-profiles.example.json
model-profiles.example.json
agent-profiles.example.json
guidance/AGENTS.md
skills/test-first/SKILL.md
prompts/benchmark-review.md
extensions/repository-info.ts
extensions/model-switch.ts
extensions/mcp-client/index.ts
extensions/mcp-client/server.py
```

`pi-profiles.example.json` demonstrates:

- global `AGENTS.md` guidance;
- one owned skill;
- one owned extension tool;
- one prompt template;
- an MCP client extension and owned stdio server; and
- a model-switch extension using `ctx.modelRegistry` and `pi.setModel`.

`model-profiles.example.json` defines two bridge resources.
`agent-profiles.example.json` composes the full Pi profile with both resources
and starts with `example-model`. After the first tool result, the owned
extension selects `review-model` through Pi's native registry.

This is intentionally profile behaviour, not a benchmark routing policy.

## Verify loading

```bash
pi-bench pi-profiles \
  --pi-profiles-file examples/agent-profiles/pi-profiles.example.json

pi-bench agent-profiles \
  --agent-profiles-file examples/agent-profiles/agent-profiles.example.json \
  --pi-profiles-file examples/agent-profiles/pi-profiles.example.json \
  --model-profiles-file examples/agent-profiles/model-profiles.example.json
```

The automated Docker check:

```bash
scripts/check-agent-profile-examples.py
```

proves that:

1. global guidance reaches Pi;
2. the skill appears in Pi's system prompt;
3. the prompt template expands;
4. the extension tool runs;
5. the MCP extension calls its owned server;
6. the extension switches between two bridged Inspect aliases; and
7. Inspect logs export into agent-profile-first dashboard records.

The example model endpoint names are illustrative. Do not put private URLs or
credentials into public JSON. Bridge constructor secrets belong in
`model_args_env`; Pi-tool secrets belong in the Pi profile's `runtime_env`.

## Use the structure privately

Copy the Pi profile into `configs/pi-profiles.local.json`, point its resources
at private files, define real model resources, then compose them in
`configs/agent-profiles.local.json`.

```bash
pi-bench benchmark \
  --agent-profile my-complete-agent \
  --agent-profiles-file configs/agent-profiles.local.json \
  --pi-profiles-file configs/pi-profiles.local.json \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name my-profile-check-v1 \
  --epochs 3 \
  --resume
```

Only commit examples safe to make public.
