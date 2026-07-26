# Test cases

Keep case files in these places:

```text
evals/
  planning/                 small fake planning checks
  coding/                   small fake coding checks
  pilots/
    user-list-filter/       first real pilot
    user-idempotency/       harder real pilot
  schemas/                  case file rules
```

Each real pilot folder contains:

- `planning.jsonl`;
- `coding.jsonl`; and
- a short README.

Starting repositories live under `repos/`. Real repositories are ignored by
Git.

Protected coding checks live under `verifiers/<coding-case-id>/`. Docker puts
them in `/opt/verifiers/`, where Pi cannot read them.

Do not keep several old copies of a case. When a case changes:

1. change its dataset version;
2. keep old Inspect logs;
3. replace the case file; and
4. explain the important change in the pilot README.

Inspect logs keep the old run evidence. We do not need old case files with
names such as `v1-final-new-2`.
