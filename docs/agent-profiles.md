# Configure complete agent profiles

An `AgentProfile` is the complete runnable benchmark unit. It composes:

- one reusable `PiProfile`;
- one or more reusable model resources; and
- one default model resource.

The dashboard compares this complete identity, not a separate model-plus-agent
Cartesian pair.

## Local files

```bash
pi-bench init
```

creates ignored files:

```text
configs/pi-profiles.local.json
configs/model-baselines.local.json
configs/agent-profiles.local.json
```

Paths in a Pi-profile file resolve from that file's directory. Resolved secrets
belong in `.env.local`, never JSON.

## Pi profiles

A Pi profile owns harness behaviour:

```json
{
  "version": 1,
  "profiles": {
    "team-agent": {
      "description": "Test-first guidance and an owned review extension.",
      "tools": ["read", "bash", "edit", "write", "grep", "find", "ls"],
      "runtime_env": {},
      "settings": {},
      "context_files": [
        {
          "name": "team-guidance",
          "path": "../.agent-resources/team/AGENTS.md"
        }
      ],
      "system_prompt": null,
      "append_system_prompts": [],
      "skills": [
        {
          "name": "test-first",
          "path": "../.agent-resources/team/skills/test-first"
        }
      ],
      "extensions": [],
      "prompt_templates": [],
      "mcp_servers": []
    }
  }
}
```

`trust_mode` is not configurable. Every benchmark run forces `--no-approve` so
repository-owned `.pi` settings, extensions, skills, prompts, and packages
cannot add unprofiled harness behaviour.

Repository `AGENTS.md` and `CLAUDE.md` files remain enabled. They are case
context, fingerprinted through the starting repository, and shared by all
profiles in the cohort.

### Tools and resources

`tools` is the exact allowlist, including extension-provided tools.

`context_files` become one staged global `AGENTS.md`. `system_prompt` replaces
Pi's normal prompt. `append_system_prompts` add text to it. `skills`,
`extensions`, and `prompt_templates` stage only named files or directories.
Symlinks are rejected so fingerprints refer to real selected content.

`settings` becomes the private global `settings.json`. Model choices, resource
paths, package resources, and secrets are rejected there.

### Runtime environment

`runtime_env` maps a container variable name to a host variable name:

```json
{
  "runtime_env": {
    "ISSUE_TOOL_TOKEN": "PRIVATE_ISSUE_TOOL_TOKEN"
  }
}
```

Only the names and profile content are fingerprinted. Resolved values are
passed at runtime and never written to results.

### MCP

Pi uses MCP through a selected extension. Name that extension and expose only
the intended tool names:

```json
{
  "mcp_servers": [
    {
      "name": "company-issues",
      "extension": "mcp-client",
      "transport": "http",
      "server": "company-issues-production",
      "tools": ["issue_search", "issue_read"]
    }
  ]
}
```

The description is staged at `PI_BENCH_MCP_CONFIG`. Private URLs and tokens
must come from `runtime_env`.

## Composed profiles

```json
{
  "version": 1,
  "profiles": {
    "frontier-agent": {
      "description": "Vanilla Pi with one frontier cloud model.",
      "pi_profile": "vanilla",
      "model_resources": ["frontier-cloud"],
      "default_model_resource": "frontier-cloud"
    },
    "local-cloud-review": {
      "description": "Local primary work with cloud review available.",
      "pi_profile": "team-agent",
      "model_resources": ["local-32b", "frontier-cloud"],
      "default_model_resource": "local-32b"
    }
  }
}
```

Validation requires known references, a non-empty unique resource list, and a
default included in that list. Resource names match
`[a-z0-9][a-z0-9._-]*`; Pi and selected extensions can observe these aliases,
so aliases and order are fingerprint input.

Direct provider/model pairs must be unique. Direct resources sharing one Pi
provider must use identical provider configuration and authentication source.

There is no routing policy field. Pi starts with the default and a selected
extension can call `ctx.modelRegistry.find(...)` and `pi.setModel(...)`. A
resource need not be used in every run.

## Commands

```bash
pi-bench agent-profiles \
  --agent-profiles-file configs/agent-profiles.local.json \
  --pi-profiles-file configs/pi-profiles.local.json \
  --model-profiles-file configs/model-baselines.local.json

pi-bench doctor \
  --agent-profile local-cloud-review \
  --agent-profiles-file configs/agent-profiles.local.json \
  --pi-profiles-file configs/pi-profiles.local.json \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local

pi-bench benchmark \
  --agent-profile frontier-agent \
  --agent-profile local-cloud-review \
  --agent-profiles-file configs/agent-profiles.local.json \
  --pi-profiles-file configs/pi-profiles.local.json \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name agent-systems-v1 \
  --epochs 3 \
  --resume
```

For a controlled model baseline, keep the same Pi profile and define one
single-resource agent profile per model.

## Saved identity

Each result records:

- composed agent-profile fingerprint;
- Pi profile name, safe configuration, and fingerprint;
- ordered model resource names, execution paths, safe identities, and
  fingerprints;
- default resource;
- observed models where Inspect or Pi can attribute them; and
- a separate generated cohort fingerprint.

The cohort is the shared use-case and environment contract, not another
profile. Different agent profiles intentionally share it. Each benchmark
campaign also records one `benchmark_id`, allowing several compatible
campaigns to be pooled without matching repetitions across campaigns.

Descriptions and top-level display names do not alter component fingerprints.
Resource binding names do, because extensions use them.

The complete owned example includes guidance, a skill, extension tools, a
prompt template, MCP, and an extension that switches between two bridged models:
[Runnable profile examples](../examples/agent-profiles/README.md).
