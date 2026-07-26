# Benchmark cases

Each JSONL file contains complete outcome cases.

```text
sample/cases.jsonl                 two small smoke cases
starter/cases.jsonl                five owned starter cases
pilots/<name>/cases.jsonl          larger real-repository cases
schemas/outcome-case.schema.json   case format
```

Every profile is judged by the same final outcome verifier.

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

Read [Scoring and making cases](../docs/scoring-and-extending.md) before adding
a case.
