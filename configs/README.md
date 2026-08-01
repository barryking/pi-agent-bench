# Configuration templates

The tracked JSON files in this directory are starter templates used by
`pi-bench init`:

- `model-baselines.example.json` defines reusable model resources;
- `pi-profiles.json` defines reusable Pi harness configurations; and
- `agent-profiles.json` composes those resources into comparison arms.

`pi-bench init` copies them to ignored `*.local.json` files. Normal commands use
those local files by default, along with `.env.local`.

`schemas/` contains the editor-facing JSON Schemas for all three document
types. The tracked templates reference them with `$schema`.

The files under `examples/agent-profiles/` are different: they are executable
integration fixtures covering guidance, skills, extensions, prompts, MCP, and
multi-model switching. They are validated by `scripts/check-all.sh` and are not
copied into a user's local configuration.
