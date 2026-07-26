# Roadmap

Checked boxes are done. Empty boxes are still needed.

## Foundation

- [x] Public-safe repository rules
- [x] Put pilot files under one clear `evals/pilots/<case>/` layout
- [x] Remove old duplicate pilot case versions
- [x] Case file format and checks
- [x] Fake planning and coding examples
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
- [x] Add an independent planning grader
- [x] Re-grade saved planning logs
- [x] Replay coding verification from saved diffs
- [x] Prove a coding case fails before and passes after a known-good patch
- [ ] Check the planning grader against people

## Models

- [x] Add local, strong cloud, and cheaper cloud profile slots
- [x] Add an independent grader slot
- [x] Add subscription login support
- [ ] Run a complete strong cloud baseline
- [ ] Run a complete local baseline
- [ ] Test 32K, 64K, and 128K context sizes
- [ ] Record cold and warm local runs
- [ ] Fully check direct subscription limits on a real coding run

## Cases

- [x] Add safe case scaffolding
- [x] Refuse unfinished draft cases
- [x] Add two real public planning/coding pilot pairs
- [x] Prove all five owned starter coding cases
- [ ] Re-prove the external user-filter pilot with the current image
- [x] Build five owned shared starter cases
- [ ] Build a larger private case set
- [ ] Add a plan-then-code case type

## Reports

- [x] Save one small record per trial
- [x] Save coding diffs
- [x] Export CSV and JSONL
- [x] Rebuild dashboard records from Inspect logs
- [x] Add a local comparison dashboard
- [x] Add coverage and ranking checks
- [x] Show time, tokens, cost, and quality
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
