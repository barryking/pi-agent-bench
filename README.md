# Pi Agent Bench

Pi Agent Bench helps you compare coding AI models.

It can compare:

- a model running on your own computer;
- a model running on a server such as a DGX;
- a cloud model paid for by API use; and
- a cloud model used through a subscription.

Every model gets the same task, agent setup, time, and tests. This makes the
result as fair as we can make it. You can also keep the model fixed and compare
different agent setups.

Inspect is the evaluation framework. This repository does not replace it.

- Inspect owns runs, limits, logs, scores, and detailed evidence.
- This repository adds the Pi connection, cases, protected checks, model setup,
  local-hardware facts, and simple comparisons across runs.
- Files under `results/` are copies made for charts. They can be rebuilt from
  Inspect logs.

## The big picture

```text
Your Mac
  └─ Inspect AI starts a clean Docker container
       └─ Pi reads the task and works on the code
            └─ Pi asks one chosen model for help

After the work:
  ├─ protected tests check the answer
  ├─ Inspect saves the full story of the run
  └─ Pi Agent Bench saves small files for charts and comparisons
```

The Mac runs the tests and stores the results. A DGX or other model server only
answers model requests. It does not receive your whole Mac filesystem.

## Important words

- **Case:** one task for the AI.
- **Fixture:** the starting files for a coding case.
- **Verifier:** protected code that checks the result.
- **Model profile:** which model answers Pi, plus its inference settings.
- **Agent profile:** Pi's tools, instructions, skills, extensions, and other
  agent setup.
- **Trial:** one attempt at one case.
- **Campaign:** a group of trials that should be compared.
- **Inspect log:** the full record of what happened.
- **Dashboard:** the simple charts made by Pi Agent Bench.

## What “quality” and “success” mean

Quality is a number from `0` to `1`.

- `0` means the task was not done.
- `0.5` means some important parts worked.
- `1` means everything checked by the case worked.

Success is a yes-or-no result. Each case has a success line called a
`success_threshold`. Coding cases may also name critical checks. Every
critical check must pass, even when the weighted quality score is high enough.

For example:

```text
quality = 0.80
success threshold = 0.75
success = yes
```

Coding quality comes from real checks, such as tests and required behaviour.
Planning quality comes from a written score guide called a rubric. A different
AI model reads the rubric and grades the plan. People must later check a sample
of those grades.

## Install on a clean Mac

Install Git, Python 3.11, and Docker Desktop:

```bash
brew install git python@3.11
brew install --cask docker
open -a Docker
```

Clone this repository:

```bash
mkdir -p ~/Code
cd ~/Code
git clone https://github.com/barryking/pi-agent-bench.git
cd pi-agent-bench
```

Run the setup script:

```bash
./scripts/bootstrap-mac.sh
source .venv/bin/activate
```

The script:

1. creates a private Python environment;
2. installs the pinned tools;
3. creates local config files without replacing old ones;
4. builds the Docker image; and
5. runs the checks.

For more help, read [Clean Mac setup](docs/setup-mac.md).

## Configure models

This command creates the local files if they do not exist:

```bash
pi-bench init
```

Edit:

- `.env.local` for secret keys and private addresses;
- `configs/model-baselines.local.json` for model names and settings; and
- `configs/agent-profiles.local.json` when you want to test a changed Pi setup.

Do not put a secret key directly in the JSON file.

The command names say whether you are choosing one profile or pointing at its
file:

- `--model-profile` chooses one model setup by name.
- `--model-profiles-file` points at the file containing model setups.
- `--agent-profile` chooses one Pi setup by name.
- `--agent-profiles-file` points at the file containing Pi setups.

The example config has places for:

- `local-candidate`;
- `hosted-quality`;
- `hosted-cost`;
- `independent-grader`;
- `openai-codex-gpt-5.6-sol`; and
- `openai-codex-gpt-5.6-luna`.

Check a model before using it:

```bash
pi-bench doctor \
  --model-profile local-candidate \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local
```

If it says `ready`, the model can be used.

For a DGX server, follow [DGX setup](docs/setup-dgx.md).

## Configure Pi

The default agent profile is `vanilla`. It gives Pi fixed tools and no personal
instructions, skills, extensions, prompt templates, or MCP servers.

An agent profile can deliberately add:

- `AGENTS.md` instructions;
- a replacement or extra system prompt;
- skills;
- extensions and their tools;
- prompt templates;
- Pi settings; and
- MCP servers used through a chosen Pi extension.

List the profiles:

```bash
pi-bench agent-profiles
```

Use `configs/agent-profiles.local.json` for private profiles. Each selected
file is copied into the clean container and hashed. Your normal Pi home is
never copied.

Read [Agent profiles](docs/agent-profiles.md) for a small example.
The [runnable examples](examples/agent-profiles/README.md) include an owned
skill, extension tool, prompt template, and MCP client plus server.

## Run your first campaign

The owned starter suite has five useful jobs. It is included in the clone, so
you do not need to download another repository.

Start with the two subscription cloud controls. This gives you a baseline
before you test a local model:

```bash
pi-bench campaign coding \
  --model-profile openai-codex-gpt-5.6-sol \
  --model-profile openai-codex-gpt-5.6-luna \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --dataset evals/starter/coding.jsonl \
  --campaign starter-coding-baseline-v1 \
  --epochs 3 \
  --resume
```

This runs three attempts for every profile and case. It runs profiles one at
a time. `--resume` lets Inspect continue after an interruption.

Next, run the same cases against the local model:

```bash
pi-bench campaign coding \
  --model-profile local-candidate \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --dataset evals/starter/coding.jsonl \
  --campaign starter-coding-baseline-v1 \
  --epochs 3 \
  --resume
```

Keep the case files, Pi version, Docker image, and limits unchanged. This lets
you compare local results with the cloud baseline.

For planning and coding together:

```bash
pi-bench campaign all \
  --model-profile openai-codex-gpt-5.6-sol \
  --model-profile openai-codex-gpt-5.6-luna \
  --model-profile local-candidate \
  --grader-model-profile independent-grader \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --planning-dataset evals/starter/planning.jsonl \
  --coding-dataset evals/starter/coding.jsonl \
  --campaign first-full-baseline \
  --epochs 3 \
  --resume
```

The grader must be a different model from every model it grades.

### Compare two Pi setups

Keep the model fixed and repeat `--agent-profile`:

```bash
pi-bench campaign coding \
  --model-profile hosted-quality \
  --agent-profile vanilla \
  --agent-profile team-agent \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profiles-file configs/agent-profiles.local.json \
  --env-file .env.local \
  --dataset evals/starter/coding.jsonl \
  --campaign agent-profile-check-v1 \
  --epochs 3 \
  --resume
```

The dashboard shows `hosted-quality` and
`hosted-quality + team-agent` as separate choices. This makes changes in tools,
context, skills, and extensions visible without pretending they are different
models.

## See the results

Open both local viewers:

```bash
pi-bench view \
  --results-dir results \
  --logs-dir logs \
  --inspect
```

This starts:

- the Pi Agent Bench dashboard at `http://127.0.0.1:8765/`;
- the Inspect viewer at `http://127.0.0.1:7575/`.

Use the dashboard to compare models. Use Inspect to read one run step by step.
Press `Ctrl+C` to stop both.

### Open Inspect by itself

Inspect logs are files ending in `.eval` under `logs/`.

To open only Inspect:

```bash
source .venv/bin/activate
inspect view --log-dir logs --port 7575
```

Then open:

```text
http://127.0.0.1:7575/
```

Inspect shows:

- the task and model;
- every model message;
- Pi tool calls;
- token use and timing;
- the final answer or code diff;
- verifier and rubric scores; and
- errors and limits.

For a subscription run, Inspect may show `mockllm/model` in its model column.
This is the small Inspect-to-Pi bridge, not the model being tested. Open the
run metadata to see the profile, or use the Pi Agent Bench dashboard to see the
real provider and model name recorded by Pi.

For one saved campaign, point `--log-dir` at its folder. For example:

```bash
inspect view --log-dir logs/pilot-user-list-filter --port 7575
```

You can also build result files without opening a browser:

```bash
pi-bench export \
  --logs-dir logs \
  --results-dir results

pi-bench report \
  --results-dir results \
  --output results/summary.md
```

`export` reads Inspect logs. It does not run a model.

## Make a new case

Create a planning case:

```bash
pi-bench new-case planning \
  --id plan-example-001 \
  --dataset evals/custom/planning-example-v1.jsonl
```

Create a coding case:

```bash
pi-bench new-case coding \
  --id code-example-001 \
  --dataset evals/custom/coding-example-v1.jsonl
```

The new case is a safe draft. Pi Agent Bench will not run it yet.

For planning, you or an AI must:

1. write a clear task;
2. list important ideas the plan must include;
3. write a simple rubric;
4. choose the success line; and
5. set `metadata.draft` to `false`.

For coding, you or an AI must:

1. prepare the starting files;
2. write a clear task;
3. replace the failing verifier with real checks;
4. prove the untouched fixture fails;
5. prove a known-good answer passes; and
6. set `metadata.draft` to `false`.

Then check the case:

```bash
pi-bench validate evals/custom/coding-example-v1.jsonl
docker compose -f docker/compose.yaml build

pi-bench prove-case \
  evals/custom/coding-example-v1.jsonl \
  --known-good-diff <private-known-good.diff> \
  --output results/case-proofs/code-example-001.json
```

Read [Scoring and making cases](docs/scoring-and-extending.md) for examples.

Two real pilot pairs are included:

- `evals/pilots/user-list-filter/` — start here;
- `evals/pilots/user-idempotency/` — a harder database and concurrency job.

The recommended examples are under `evals/starter/`. They use code owned by
this project and run without cloning anything else:

- user filtering and pagination validation;
- configuration precedence;
- webhook signature checking;
- cursor pagination in Node; and
- durable SQLite idempotency.

## Use a real repository

Put a clean copy under `repos/<case-id>/`.

Pin it to one full Git commit:

```bash
git clone <repository-url> repos/<case-id>
git -C repos/<case-id> checkout <full-commit>
git -C repos/<case-id> status --short
```

The last command must print nothing.

Pi Agent Bench copies this repository into Docker. The AI never edits the host
copy. Read [Local case repositories](repos/README.md).

## Check old results again

Re-grade a planning log with another grader:

```bash
pi-bench rescore-planning logs/<planning-log>.eval \
  --grader-model-profile independent-grader \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local
```

Re-run the protected coding verifier without rerunning the model:

```bash
pi-bench replay-coding logs/<coding-log>.eval
```

The coding replay uses a temporary copy. It does not change the original
fixture.

## Where files go

- `logs/*.eval` — full Inspect records.
- `results/*.json` — rebuildable chart records for each trial.
- `results/*.diff` — code changes made by the AI.
- `results/summary.md` — a readable summary.
- `results/runs.csv` — a table for spreadsheet tools.
- `results/metrics.jsonl` — facts used by charts.
- `results/_invalid/` — interrupted or broken attempts.
- `results/replay/` — coding replay checks.
- `results/case-proofs/` — proof that a coding case fails before and passes
  after a known-good patch.

Broken attempts do not enter rankings.
Inspect logs are the source of truth.

Each result also records the model profile, agent profile, and safe hashes of
the selected agent resources. Secret values and file contents are not copied
into result records.

## Fair comparison rules

Do not rank models until:

- every model ran the same cases;
- every model used the same Pi and Docker versions;
- every case has at least three trials;
- there are at least five shared cases;
- planning grades have been checked by people; and
- cloud models show that the cases are possible.

Tokens per second are useful for model servers. They do not prove that a model
can finish a coding task.

The main benchmark view is **quality versus total task time**:

- higher means better work;
- further left means less time; and
- upper-left is best.

Cost is not part of this main view. It may still be shown when a provider
reports it.

## Keep private things private

Do not commit:

- API keys or login files;
- private repositories;
- company documents;
- protected prompts;
- hidden test answers; or
- private run transcripts.

## More guides

- [Clean Mac setup](docs/setup-mac.md)
- [DGX setup](docs/setup-dgx.md)
- [Running evaluations](docs/running-evaluations.md)
- [Agent profiles](docs/agent-profiles.md)
- [Scoring and making cases](docs/scoring-and-extending.md)
- [Metrics](docs/metrics.md)
- [Architecture](docs/architecture.md)
- [Decisions](docs/decisions.md)
- [Roadmap](docs/roadmap.md)

## License

Pi Agent Bench is available under the [MIT License](LICENSE).
