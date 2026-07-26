# Runnable agent-profile examples

These small examples show how a file on the Mac becomes part of Pi inside a
benchmark trial.

They are owned by this project. They do not download packages or copy another
repository.

## See the profiles

```bash
pi-bench agent-profiles \
  --agent-profiles-file examples/agent-profiles/agent-profiles.example.json
```

The file contains focused profiles and one `example-everything` profile used
by the integration check.

## The common loading path

```text
file in examples/agent-profiles/
  → named by agent-profiles.example.json
  → checked and hashed on the Mac
  → copied into a new temporary Pi home inside Docker
  → discovered by Pi 0.82.1
  → removed with the trial container
```

The source directory is not mounted into Docker. Result records contain safe
hashes, not the file contents.

## AGENTS.md guidance

Source:

```text
guidance/AGENTS.md
```

Profile entry:

```json
{
  "context_files": [
    {
      "name": "example-guidance",
      "path": "guidance/AGENTS.md"
    }
  ]
}
```

Pi Agent Bench copies it to:

```text
/tmp/pi-bench-pi-home/.pi/agent/AGENTS.md
```

Pi adds the guidance to its system prompt. In Inspect, open the model input and
look for `BENCHMARK_GUIDANCE_MARKER`.

## Skill

Source:

```text
skills/test-first/SKILL.md
```

Profile entry:

```json
{
  "skills": [
    {
      "name": "test-first",
      "path": "skills/test-first"
    }
  ]
}
```

Pi sees the skill name and description in its system prompt. It reads the full
`SKILL.md` only when the task needs it or the prompt calls
`/skill:benchmark-test-first`.

In Inspect, look for `benchmark-test-first` in the system prompt. If Pi reads
the complete skill, its file-read event contains `BENCHMARK_SKILL_MARKER`.

## Extension and custom tool

Source:

```text
extensions/repository-info.ts
```

The profile must do two things:

1. name the extension file; and
2. add its registered tool name to the profile tool list.

```json
{
  "tools": [
    "read",
    "bash",
    "edit",
    "write",
    "grep",
    "find",
    "ls",
    "repository_info"
  ],
  "extensions": [
    {
      "name": "repository-info",
      "path": "extensions/repository-info.ts"
    }
  ]
}
```

Pi loads the TypeScript file from its temporary global extensions folder. The
extension registers `repository_info`.

In Inspect:

- the first model request lists `repository_info` as a tool; and
- a tool call result contains `BENCHMARK_EXTENSION_MARKER`.

An extension must be self-contained or use software already present in the
pinned Docker image. Trials do not install packages.

## Prompt template

Source:

```text
prompts/benchmark-review.md
```

Profile entry:

```json
{
  "prompt_templates": [
    {
      "name": "benchmark-review",
      "path": "prompts/benchmark-review.md"
    }
  ]
}
```

Installing a prompt template does not change a normal case by itself. A case
must invoke it. For this example, the case instruction would start with:

```text
/benchmark-review README.md
```

Pi expands that text before calling the model. In Inspect, the user message
contains `BENCHMARK_TEMPLATE_MARKER` and the expanded instructions instead of
the slash command.

This means a prompt template is an active part of the case design, not passive
background guidance. Use `AGENTS.md` or an appended system prompt when every
ordinary task should receive the same instruction.

## MCP server

Pi has no built-in general MCP client. An MCP profile therefore needs:

1. an extension that acts as the MCP client;
2. the server program or endpoint;
3. an `mcp_servers` entry; and
4. every exposed MCP tool in the profile tool list.

The owned example contains:

```text
extensions/mcp-client/index.ts  Pi extension and MCP client
extensions/mcp-client/server.py tiny stdio MCP server
```

The important profile parts are:

```json
{
  "tools": [
    "read",
    "bash",
    "edit",
    "write",
    "grep",
    "find",
    "ls",
    "example_catalog_lookup"
  ],
  "extensions": [
    {
      "name": "mcp-client",
      "path": "extensions/mcp-client"
    }
  ],
  "mcp_servers": [
    {
      "name": "example-catalog",
      "extension": "mcp-client",
      "transport": "stdio",
      "server": "example-catalog",
      "tools": ["example_catalog_lookup"]
    }
  ]
}
```

At run time:

```text
Pi
  → example_catalog_lookup tool
  → mcp-client extension
  → JSON-RPC over stdio
  → owned Python MCP server
```

Pi Agent Bench writes the selected `mcp_servers` list inside Docker and sets:

```text
PI_BENCH_MCP_CONFIG
```

The extension reads that file. The JSON list does not connect to anything on
its own.

The owned client is deliberately small. It supports only its bundled stdio
catalog server. For a real MCP service, use a reviewed and pinned extension
that supports the required transport, authentication, schemas, errors, and
server lifecycle. Pass private addresses and credentials with `runtime_env`;
never put them in the profile JSON.

In Inspect, a successful call to `example_catalog_lookup` contains
`BENCHMARK_MCP_MARKER`.

## Run one example profile

Use any configured model:

```bash
pi-bench run \
  --model-profile hosted-quality \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profile example-extension \
  --agent-profiles-file examples/agent-profiles/agent-profiles.example.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --run-name agent-extension-example
```

The model decides whether the task needs `repository_info`. Use Inspect to
confirm whether it called the tool.

## Prove every example automatically

Build the pinned image, then run:

```bash
pi-bench build-sandbox
python scripts/check-agent-profile-examples.py
```

The check uses a scripted Inspect model so tool use is not left to chance. It
proves all five resource types inside a real Pi Docker trial.
