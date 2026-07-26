# Decisions we have made

This page records important choices. Change it when the evidence changes.

## Test the whole agent

We test Pi doing a full task. We do not test only one model answer.

Why: tools, files, retries, and the agent loop can change the outcome.

## Use Inspect AI as the controller

Inspect loads cases, starts Docker, applies limits, stores logs, and runs
scorers.

Why: using one controller is simpler and makes runs easier to compare.

## Keep Pi as the agent

We run the real Pi tool loop.

Why: replacing Pi with our own small loop would test a different product.

## Use a clean container for every trial

Every trial gets new files, a new Pi home, and a new session.

Why: one trial must not change another trial.

## Turn off personal Pi extras

Skills, extensions, prompt templates, themes, context files, and old sessions
are disabled.

Why: a personal extra would make the comparison unfair.

## Let Inspect control normal model settings

For bridge runs, Inspect controls the chosen model and generation settings.

Why: Pi is pointed at a bridge model name, not the real provider model.

## Support subscription models as a separate route

Pi may call a subscription model directly using one selected login.

Why: some useful models are available through subscriptions instead of normal
API billing.

This route has less Inspect model detail, so we record Pi events too.

## Treat cloud models as controls

Use one strong cloud model and one cheaper cloud model.

Why: cloud models show the quality ceiling and price trade-off. A local model
does not need to win every measure to be useful.

## Keep the framework hardware-neutral

The project is called Pi Agent Bench. DGX is one local server choice.

Why: Inspect, Pi, Docker, cases, and reports can work with many model servers.

## Use the name Pi Agent Bench

The final project name is **Pi Agent Bench**.

Use:

- GitHub repository: `pi-agent-bench`;
- Python package: `pi_agent_bench`;
- command: `pi-bench`; and
- Docker image: `pi-agent-bench-sandbox`.

Why: it says which agent we test and that this is a benchmark. It does not tie
the project to DGX or pretend to replace Inspect.

## Keep planning and coding separate

Planning and coding use different sessions and different scores.

Why: a long planning conversation should not fill the coding context.

## Prefer real checks for coding

Hidden tests and required behaviour are the main coding score.

Why: one reference patch is not the only correct solution.

## Use an independent planning grader

The tested model cannot grade itself.

Why: self-grading is not trustworthy.

People must check a hidden sample of the grader's scores.

## Store scores in Inspect first

Inspect stores quality, success, and score parts. The dashboard reads smaller
copies of those results.

Why: the full Inspect log is the best evidence and can be checked later.

## Keep broken attempts out of rankings

Interrupted runs, run errors, and invalid scores go under `results/_invalid/`.

Why: a system problem is not the same thing as a bad model answer.

## Make new cases safe drafts

Generated cases cannot run. Generated coding verifiers fail.

Why: unfinished work, including AI-written work, must not become ranking
evidence by mistake.

## Require balanced evidence before ranking

Ranking needs:

- the same shared cases;
- at least five shared cases;
- at least three trials per profile and case;
- matching versions; and
- matching benchmark files.

Why: a model should not rank higher just because it skipped hard cases.

## Use the same harness for every model

Compared models use the same Pi, tools, cases, limits, and Docker image.

Why: otherwise we cannot tell whether the model caused the difference.

## Start with a 128K model profile

The first broad model profile uses a 128K context where supported.

Why: this leaves room for realistic tasks and agent work without always using
the largest and slowest setting.

Each case may use a smaller limit.

## Keep public and private cases apart

This repository stays public-safe. Protected cases live elsewhere.

Why: the framework can be shared without sharing private company data.

## Choices still being tested

These are ideas, not final answers:

- which local planning model is best;
- which local coding model is best;
- which compression keeps enough quality;
- whether vLLM is the best server;
- whether prefix caching should be on;
- how many trials are enough for close results.

## Open questions

- Which local model gives the best useful result?
- Is one model enough for both planning and coding?
- Which context size gives the best speed and quality?
- How closely does the planning grader match people?
- How many real cases are needed?
- Which failure groups should the dashboard show?
- What quality gap is acceptable for private local inference?
- How should hardware, power, and maintenance cost be counted?
- Should the final advice choose one model or route different jobs differently?
- Which open-source licence should this project use?
