# Change Pi without changing the model

An **agent profile** says how Pi is set up for a test.

A **model profile** says which model answers Pi.

Keep these as two separate choices. This lets you ask fair questions such as:

> Does our skill help the same model finish faster?

or:

> Does an MCP tool improve quality for this case?

The clean starting profile is called `vanilla`. It has fixed built-in tools and
no extra instructions, skills, extensions, prompt templates, or MCP servers.

## Make a local profile file

Run:

```bash
pi-bench init
```

This creates an ignored file:

```text
configs/agent-profiles.local.json
```

The file is ignored by Git because it may point at private company files.
Keep the `vanilla` profile. Add your own profiles beside it.

`--agent-profile` chooses one setup. `--agent-profiles-file` tells the command
which file contains that setup. Model options use the same clear pattern:
`--model-profile` and `--model-profiles-file`.

List them:

```bash
pi-bench agent-profiles \
  --agent-profiles-file configs/agent-profiles.local.json
```

Check one before a run:

```bash
pi-bench doctor \
  --model-profile hosted-quality \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profile team-agent \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local
```

## A small example

Create these files:

```text
.agent-resources/
  team-guidance/
    AGENTS.md
    skills/
      test-first/
        SKILL.md
```

Add this profile to `configs/agent-profiles.local.json`:

```json
{
  "team-agent": {
    "description": "Vanilla Pi plus our test-first guidance.",
    "trust_mode": "no-approve",
    "tools": ["read", "bash", "edit", "write", "grep", "find", "ls"],
    "runtime_env": {},
    "settings": {},
    "context_files": [
      {
        "name": "team-guidance",
        "path": "../.agent-resources/team-guidance/AGENTS.md"
      }
    ],
    "system_prompt": null,
    "append_system_prompts": [],
    "skills": [
      {
        "name": "test-first",
        "path": "../.agent-resources/team-guidance/skills/test-first"
      }
    ],
    "extensions": [],
    "prompt_templates": [],
    "mcp_servers": []
  }
}
```

Paths are read from the folder containing the profile JSON file.

## What each part means

### Behaviour

There is no special workflow switch. The profile's instructions and resources
may ask Pi to plan first, write tests first, review its work, use extra tools,
or follow any other repeatable process. The profile name and content hashes
record the whole setup.

### Tools

`tools` lists everything Pi may use while completing the outcome.

If an extension adds a tool, put its tool name in this list too.

### Context files

`context_files` holds standing instructions such as `AGENTS.md`.

Pi Agent Bench joins the selected files into one temporary `AGENTS.md`. It does
not load the `AGENTS.md` from your Mac or from the case starting repository by
accident.

### System prompt

`system_prompt` replaces Pi's normal system prompt. This is a large change, so
use it only when replacing the whole prompt is the thing you want to test.

`append_system_prompts` adds text after Pi's normal system prompt. This is
usually safer.

Each entry must point at one UTF-8 text file.

### Skills

`skills` points at Pi skill files or folders. A skill folder normally contains
a `SKILL.md`.

Pi can see only the skills named in the profile. Your personal Pi skills stay
outside the container.

### Extensions

`extensions` points at Pi extension files or folders. Extensions can add tools,
commands, events, and other agent behaviour.

An extension must be self-contained or use software already installed in the
pinned Docker image. Pi Agent Bench does not download packages during a trial.
This keeps repeated trials clean.

### Prompt templates

`prompt_templates` points at Pi prompt-template files.

A prompt template is normally used with a slash command. The benchmark sends
the case task directly, so adding a template does not change a run unless an
extension or instruction actually uses it.

### Settings

`settings` becomes Pi's temporary `settings.json`.

Use it for agent-loop choices such as compaction or retry behaviour. Do not put
the model, provider, reasoning level, resource paths, or secrets here. Those
belong in the model profile, named resource lists, or environment file.

### Secret environment values

`runtime_env` maps a name inside Docker to a name on the Mac.

For example:

```json
{
  "runtime_env": {
    "ISSUE_TOOL_TOKEN": "PRIVATE_ISSUE_TOOL_TOKEN"
  }
}
```

Then `.env.local` may contain:

```text
PRIVATE_ISSUE_TOOL_TOKEN=secret-value
```

The result records the environment variable name. It never records the secret
value.

### MCP servers

Pi does not have a built-in, general MCP client. MCP support comes from a Pi
extension.

Put that extension in `extensions`. Then describe each server in
`mcp_servers`:

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

The named extension must exist in the same profile. Pi Agent Bench copies this
list to a temporary JSON file and gives the extension its path in:

```text
PI_BENCH_MCP_CONFIG
```

The extension is responsible for understanding the file and connecting to the
server. Put private URLs and tokens in `runtime_env`, not in the profile.

## Compare agent profiles

Use one model and repeat `--agent-profile`:

```bash
pi-bench campaign \
  --model-profile hosted-quality \
  --agent-profile vanilla \
  --agent-profile team-agent \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local \
  --dataset evals/starter/cases.jsonl \
  --campaign agent-profile-check-v1 \
  --epochs 3 \
  --resume
```

To compare two models and two agent profiles, repeat both choices. Pi Agent
Bench runs all four pairs:

```text
model A + vanilla
model A + team-agent
model B + vanilla
model B + team-agent
```

The dashboard shows each pair separately.

## What gets saved

Each result saves:

- the model profile;
- the agent profile name;
- tools, settings, and safe MCP details;
- a hash of every selected resource;
- a hash of the whole agent profile; and
- the exact Pi and benchmark versions.

It does not save resource contents, full paths, or secret values.

If a file changes, its hash changes. Do not mix those runs under the same
campaign name.

## Keep the comparison fair

Change one thing at a time when you want to learn what caused a difference.

For example:

1. run `same model + vanilla`;
2. run `same model + one skill`;
3. keep cases, limits, model settings, Pi version, and trial count unchanged;
4. compare quality and total task time; and
5. read failed runs in Inspect.

Do not call an agent profile better after one lucky trial. Use at least three
trials for every profile and case.

For complete owned examples of `AGENTS.md`, a skill, an extension tool, a
prompt template, and an MCP client plus server, read
[Runnable agent-profile examples](../examples/agent-profiles/README.md).

The examples include a Docker integration check. It proves that Pi loads each
resource and executes both example tools.

Pi's own guides explain the resource formats:

- [context files](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/usage.md)
- [skills](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)
- [extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)
- [prompt templates](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/prompt-templates.md)
- [settings](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md)
