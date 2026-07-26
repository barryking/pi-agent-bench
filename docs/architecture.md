# How Pi Agent Bench works

Pi Agent Bench measures a finished repository outcome.

It does not give planning and coding separate rankings. Planning, test-first
work, review loops, tools, skills, and prompts are parts of an agent profile.
Every profile starts with the same repository and is checked by the same final
verifier.

## The parts

The Mac runs:

- the `pi-bench` command;
- Inspect;
- Docker;
- reports; and
- the dashboard.

The clean Docker container runs:

- Pi;
- a temporary copy of the starting repository;
- the selected agent-profile resources; and
- the protected verifier.

The model can run in the cloud or on local hardware such as a DGX. It answers
Pi's model requests. The benchmark controller and reports stay on the Mac.

## One trial

One trial works like this:

1. Inspect starts a clean container.
2. The starting repository is copied to `/workspace`.
3. The selected agent profile is copied to Pi's private temporary home.
4. Pi asks the selected model to complete the task.
5. Pi may plan, inspect, edit, test, or use extra tools.
6. The protected verifier checks the final repository.
7. Inspect saves the full trajectory and score.
8. Pi Agent Bench exports small result files for comparisons.
9. The container is removed.

The host starting repository is never changed.

## What an agent profile means

An agent profile is a reproducible Pi setup. It may contain:

- `AGENTS.md` guidance;
- system-prompt additions;
- tools;
- skills;
- extensions;
- prompt templates;
- settings;
- MCP client extensions and server descriptions.

There is no special “planning profile” switch. To test plan-first behaviour,
make a normal profile whose instructions ask Pi to plan before editing. The
profile name and content hashes show exactly what changed.

## What is scored

The main score is the finished outcome:

- protected behaviour checks;
- regression checks;
- required public tests;
- documentation or other required files;
- critical components; and
- the case success threshold.

The main chart shows quality against total time. Planning text can be reviewed
inside the Inspect log, but it does not replace the final outcome score.

If the requested outcome really is a plan or design document, create a case
whose starting repository, instruction, and verifier check that document. It is still one
complete outcome.

## Source of truth

Inspect `.eval` files are the source evidence. JSON, CSV, and JSONL files under
`results/` are rebuildable chart copies.
