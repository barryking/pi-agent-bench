# Roadmap

Checked boxes are done. Empty boxes are still needed.

## Foundation

- [x] Public-safe repository rules
- [x] Put unfinished case work under `evals/candidates/<case>/`
- [x] Remove the old pilot case category and terminology
- [x] Case file format and checks
- [x] Small sample outcome cases
- [x] Clean Docker workspace
- [x] Real Pi agent inside Docker
- [x] Choose the MIT open-source licence

## Inspect and scoring

- [x] Connect Pi to Inspect
- [x] Keep full Inspect logs
- [x] Apply time, turn, and token limits
- [x] Keep each case's exact limits
- [x] Add quality, success, and score parts
- [x] Add repeated-trial statistics
- [x] Replay outcome verification from saved diffs
- [x] Prove an outcome case fails before and passes after a known-good patch

## Models

- [x] Add local, strong cloud, and cheaper cloud profile slots
- [x] Add subscription login support
- [ ] Run a complete strong cloud baseline
- [ ] Run a complete local baseline
- [ ] Test 32K, 64K, and 128K context sizes
- [ ] Record cold and warm local runs
- [ ] Fully check direct subscription limits on a real outcome run

## Agent profiles

- [x] Make the composed runnable agent profile the primary comparison unit
- [x] Rename harness-only profiles to Pi profiles
- [x] Keep reusable Pi and model definitions separate
- [x] Keep vanilla Pi as the clean default
- [x] Select and hash context, prompts, skills, extensions, and templates
- [x] Select tools and Pi settings by profile
- [x] Pass secret environment values without recording them
- [x] Support MCP through a selected Pi extension
- [x] Bind ordered bridge/direct model resources and one default
- [x] Expose several bridged models through Inspect aliases
- [x] Allow Pi-native model switching without a benchmark router
- [x] Guard bridge-only, direct-only, and hybrid Pi runs
- [x] Force project Pi resources untrusted while loading repository context
- [x] Compare several complete agent profiles in one benchmark run
- [x] Add owned examples for guidance, skills, extensions, prompts, and MCP
- [x] Add an owned native model-switching extension example
- [x] Re-prove the expanded owned examples in a real Pi Docker trial
- [ ] Run a real three-trial agent-profile comparison

## Cases

- [x] Add safe case scaffolding
- [x] Document draft, proof, candidate-trial, and publication stages
- [x] Keep unfinished draft cases out of model runs
- [x] Add two external-repository outcome candidates
- [x] Prove all five owned starter outcome cases
- [ ] Prove and trial the external user-filter candidate with the current image
- [x] Build five owned shared starter cases
- [ ] Build a larger private case set

## Reports

- [x] Save one small record per trial
- [x] Save outcome diffs
- [x] Export CSV and JSONL
- [x] Rebuild dashboard records from Inspect logs
- [x] Prune stale rebuilt records that no longer exist in canonical Inspect logs
- [x] Add a local comparison dashboard
- [x] Add coverage and ranking checks
- [x] Show time, tokens, cost, and quality
- [x] Separate composed agent-profile identity from generated cohort identity
- [x] Version the cohort contract independently from evidence/report schemas
- [x] Record one benchmark campaign ID across all profile arms
- [x] Prevent the dashboard from mixing incompatible cohort fingerprints
- [x] Keep compatible campaigns poolable while matching repetitions by campaign
- [x] Persist bridged, direct, and merged usage without double counting
- [x] Record complete, partial, and unavailable cost coverage
- [x] Make agent profile the report and dashboard comparison key
- [x] Size quality/time chart bubbles by summed reported cost
- [x] Validate model, Pi, and agent profile files with published JSON Schemas
- [x] Test dashboard cohort and campaign selection semantics
- [x] Start Inspect and the dashboard together
- [ ] Add clear failure groups
- [x] Show observed output tokens per model second from Inspect
- [ ] Add first-token and local server-reported speed
- [ ] Add GPU, power, and energy facts
- [ ] Make a short leadership report

## Later

- public benchmark packages;
- private case transport;
- Harbor or Terminal-Bench checks;
- many-user load tests;
- automatic DGX setup;
- hardware cost estimates.

## Keep the repository lean

For every new feature, ask:

1. Does Inspect already do it?
2. Is it needed to run Pi, define our cases, check answers, or compare local
   and cloud models?
3. Can the output be rebuilt from an Inspect log?
4. Can an old file or command be removed when the new one is added?

Do not build a second runner, scorer store, or detailed log viewer.
