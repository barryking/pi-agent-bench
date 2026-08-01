# Create, prove, trial, and publish benchmark cases

A case describes one finished repository outcome. A dataset is a versioned
JSONL list of cases intended to be run together.

There is no separate pilot case type. New work starts as a draft case, becomes
a runnable candidate after proof, and enters an ordinary maintained dataset
only after candidate trials show that it produces useful evidence.

## Who needs this process

Normal benchmark users should run a maintained dataset such as
`evals/starter/cases.jsonl`. Its starting repositories, verifiers, and
known-good checks are already maintained by this project. Users do not run
`prove-case` before each benchmark.

This page is for maintainers who create or materially change cases.

## Case lifecycle

```text
draft
  → validate structure and assets
  → prove untouched failure and known-good success
  → enable and trial as a candidate
  → accept into a maintained dataset
  → publish a new dataset version
```

The stages are evidence gates, not different runtime case classes:

- `metadata.draft: true` prevents benchmark execution while authoring is
  incomplete.
- `pi-bench validate` checks syntax, metadata, repository state, and verifier
  references. It does not show that the verifier measures the intended change.
- `pi-bench prove-case` checks the verifier against the untouched repository
  and one private known-good implementation.
- candidate benchmark trials reveal difficulty, variance, time requirements,
  ambiguous instructions, and unintended solution paths.
- publication adds the accepted case to a maintained dataset and changes that
  dataset's version.

## 1. Create a draft

Create a one-case candidate dataset:

```bash
pi-bench new-case \
  --id outcome-example \
  --dataset evals/candidates/outcome-example/cases.jsonl \
  --dataset-version outcome-example-draft-1
```

This creates:

- the JSONL case with `metadata.draft: true`;
- a project-owned starting repository scaffold under
  `starting-repos/outcome-example/`; and
- a protected verifier scaffold under `verifiers/outcome-example/`.

The command refuses to overwrite existing files. Develop a candidate in its
own dataset, then add its final JSON object to a maintained multi-case dataset
only when it is accepted.

## 2. Write the observable contract

The instruction may be a realistic PRD or work ticket. Include:

- required observable behaviour;
- behaviour that must not change;
- important errors and limits;
- public tests the agent should add; and
- documentation that must change.

Do not reveal protected verifier logic or a reference implementation.

The starting repository is the clean code given to every agent. It must be:

- realistic enough to matter;
- small enough for the declared limits;
- public-safe and free of secrets;
- pinned to one reproducible state; and
- unchanged between trials.

Project-owned fixtures belong under `starting-repos/`. External or private
checkouts belong under the ignored `local-repos/`; follow
[`local-repos/README.md`](../local-repos/README.md). The storage location does
not make a case a different type.

## 3. Build deterministic protected verification

The verifier runs after the agent finishes and prints one final JSON object:

```json
{
  "score": 0.8,
  "components": {
    "old_behaviour": 1,
    "new_behaviour": 1,
    "public_tests": 1,
    "documentation": 0
  },
  "explanation": "The behaviour works, but the documentation is missing."
}
```

The case command must be exactly:

```json
["python3", "/opt/verifiers/<case-id>/verify.py"]
```

Verifier source stays root-owned under `/opt/verifiers`, outside `/workspace`,
and unreadable by the unprivileged Pi user. The scorer executes it as root only
after Pi finishes.

Quality is from `0` to `1`. Success requires:

1. quality at or above `success_threshold`; and
2. every `required_components` item to pass.

Prefer deterministic checks of observable outcomes over implementation-shape
checks or another model's judgement.

## 4. Validate and prove the case

First validate the draft and rebuild the sandbox containing its verifier:

```bash
pi-bench validate evals/candidates/outcome-example/cases.jsonl
pi-bench build-sandbox
```

Then a maintainer supplies a known-good diff:

```bash
pi-bench prove-case \
  evals/candidates/outcome-example/cases.jsonl \
  --known-good-diff <private-known-good.diff> \
  --output results/case-proofs/outcome-example.json
```

`prove-case` creates two temporary workspaces from the same starting
repository:

1. the untouched workspace must score below the success threshold; and
2. the workspace with the known-good diff must meet the threshold and pass
   every required component.

The known-good diff comes from the case maintainer. Keep it outside the public
repository so agents cannot discover a reference answer and private code is
not published. The proof record stores its SHA-256 hash, not its contents,
alongside before/after scores, components, source commit, verifier command, and
sandbox version.

Proof demonstrates that the case is not already solved and that at least one
valid solution can pass. It does not show that the reference solution is the
only solution, or establish difficulty, fairness, and stability; candidate
trials supply that evidence.

Rerun proof whenever instructions, starting code, verifier, required
components, success threshold, scoring, or relevant sandbox behavior changes.

## 5. Run candidate trials

After a successful proof, set:

```json
"draft": false
```

This permits benchmark execution but does not make the case part of a
maintained dataset. Run several complete agent profiles and inspect:

- whether capable profiles can complete the case;
- whether scores distinguish meaningful outcomes;
- whether results are repeatable enough;
- whether limits are realistic;
- whether instructions admit unintended interpretations; and
- whether the verifier rewards only observable requirements.

If the case changes, return it to draft, update its candidate dataset version,
and repeat validation and proof.

## 6. Publish into a maintained dataset

When a candidate is accepted:

1. add its JSON object to the maintained dataset;
2. remove temporary status tags such as `candidate`;
3. keep `metadata.draft: false`;
4. give every case in that file the same new `metadata.dataset_version`;
5. add automated proof coverage where the project owns a public-safe reference
   solution; and
6. validate and run the repository checks.

Do not treat earlier candidate results as measurements from the newly
published dataset. The case set and dataset version differ.

## When the dataset version changes

Change the dataset version whenever old and new results should not be directly
compared, including:

- adding, removing, or replacing a case;
- materially changing case instructions or acceptance criteria;
- changing the starting repository contents or pinned source commit;
- changing verifier behavior, scoring weights, success thresholds, or required
  components; or
- changing limits enough to alter the task's effective difficulty.

Do not change the dataset version for:

- another model, Pi profile, or agent profile;
- another benchmark campaign or run name;
- a different planned trial count;
- cold versus warm cache state;
- a Pi, Inspect, or framework upgrade by itself; or
- dashboard, reporting, documentation, or JSON formatting changes.

The generated cohort fingerprint separates relevant execution-environment and
run-condition differences inside one dataset version.

## Recommended limits

A normal case should usually fit inside:

- 30 minutes;
- 45 turns; and
- 150,000 total tokens.

Use smaller limits for smaller jobs. Confirm feasibility with a capable profile
before using a case to compare weaker or local profiles.
