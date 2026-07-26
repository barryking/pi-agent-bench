# Clean Mac setup

Your Mac runs Pi Agent Bench. It starts Docker, sends work to models, checks the
answers, and stores the results.

Pi runs inside Docker. You do not need Pi on the Mac unless you use a Pi
subscription login.

## 1. Install the basic tools

Install Apple command-line tools:

```bash
xcode-select --install
```

Install Homebrew if you do not have it. Then run:

```bash
brew install git python@3.11
brew install --cask docker
open -a Docker
```

Wait for Docker Desktop to finish starting.

Check the tools:

```bash
git --version
python3.11 --version
docker info
```

If `docker info` fails, Docker Desktop is not ready.

## 2. Download Pi Agent Bench

```bash
mkdir -p ~/Code
cd ~/Code
git clone https://github.com/barryking/pi-agent-bench.git
cd pi-agent-bench
```

## 3. Run the setup script

```bash
./scripts/bootstrap-mac.sh
source .venv/bin/activate
```

The script:

1. makes a private Python environment called `.venv`;
2. installs Inspect AI, Ruff, and pytest;
3. creates local config files if they are missing;
4. builds the Docker image; and
5. runs the tests.

It does not replace config files you already have.

Ruff checks Python code for common mistakes. Pytest runs the project tests.
Neither tool is built into macOS.

Show the pinned versions:

```bash
pi-bench versions
```

## 4. Add model settings

The setup script creates:

- `.env.local`;
- `configs/model-baselines.local.json`; and
- `configs/agent-profiles.local.json`.

Put secret keys and private addresses in `.env.local`.

Example:

```text
LOCAL_MODEL_BASE_URL=http://192.168.1.20:8000/v1
LOCAL_MODEL_API_KEY=local-only-key
HOSTED_QUALITY_API_KEY=secret
HOSTED_COST_API_KEY=secret
INDEPENDENT_GRADER_API_KEY=secret
```

Put public model details in `configs/model-baselines.local.json`.

Record:

- the exact model name;
- the model version;
- the provider or server;
- the context size;
- the runtime version;
- the type of number compression, if used; and
- whether caching is on.

Never put a secret key in the JSON file.

The agent profile file starts with only `vanilla`. You can add exact Pi
instructions, tools, skills, extensions, or MCP support later. Read
[Agent profiles](agent-profiles.md).

## 5. Check one model

```bash
pi-bench doctor \
  --model-profile local-candidate \
  --model-profiles-file configs/model-baselines.local.json \
  --agent-profile vanilla \
  --env-file .env.local
```

The command checks Docker, Git, config values, secrets, and local model
connections.

Fix every message before running a benchmark.

## 6. Run a small test

```bash
pi-bench run coding \
  --dataset evals/starter/coding.jsonl \
  --model-profile hosted-quality \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local \
  --campaign first-check
```

Then open both viewers:

```bash
pi-bench view --results-dir results --logs-dir logs --inspect
```

## Using a ChatGPT subscription

This is optional.

Install the same Pi version used by Docker:

```bash
npm install -g @earendil-works/pi-coding-agent@0.82.1
pi
```

Inside Pi:

1. run `/login`;
2. choose `ChatGPT Plus/Pro (Codex)`;
3. finish the browser login; and
4. exit Pi.

Add only the file path to `.env.local`:

```text
PI_AUTH_FILE=/Users/your-name/.pi/agent/auth.json
```

Do not copy the login contents into this repository.

## How Pi is kept clean

Each trial gets a new temporary home folder.

The default `vanilla` profile runs with personal extras turned off:

```text
--no-session
--no-approve
--no-skills
--no-extensions
--no-prompt-templates
--no-themes
--no-context-files
```

This stops a personal skill or old session from changing the test.

If you select another agent profile, only its named files are copied into this
temporary home. Your normal Pi files still stay outside the container.

## Clean up

Logs and results stay on the Mac. Git ignores them.

To remove only the reusable Docker image:

```bash
docker image rm pi-agent-bench-sandbox:0.5.0
```

Do this only when you mean to rebuild it.
