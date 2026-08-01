# Benchmark case files

Each JSONL file is a dataset containing one or more outcome cases.

```text
sample/cases.jsonl                    two small framework smoke cases
starter/cases.jsonl                   five maintained, ready-to-run cases
candidates/<name>/cases.jsonl         draft or trial-stage maintainer cases
schemas/outcome-case.schema.json      case format
```

There is no separate pilot case type. A candidate becomes an ordinary
maintained case only after it has been validated, proved with a known-good
implementation, trialled with real agent profiles, and accepted into a
versioned dataset.

The starter suite is fully bundled: definitions, starting repositories,
verifiers, and automated reference checks are all tracked. Normal users should
start there.

Candidate definitions and verifiers may be tracked while their external
starting repositories and private reference implementations are not. Read the
candidate's status before attempting to run it. Draft candidates are
intentionally rejected by benchmark commands.

Each case points to:

- a starting repository;
- one protected verifier under `verifiers/<case-id>/`;
- limits;
- a success threshold; and
- required score components.

Run:

```bash
pi-bench validate evals/starter/cases.jsonl
```

Read [Creating, proving, and publishing cases](../docs/scoring-and-extending.md)
before adding a case.
