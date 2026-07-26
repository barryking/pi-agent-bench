# User idempotency pilot

This is the harder pilot case.

It asks the model to make user creation safe when a client repeats the same
request. The case uses one pinned starting repository.

Use the smaller `user-list-filter` pilot first. Use this case after the simple
path works.

It uses the same optional external repository described in
`evals/pilots/user-list-filter/README.md`. The five owned starter cases need no
external repository.

Before using the case in a comparison, prove it with:

```bash
pi-bench prove-case \
  evals/pilots/user-idempotency/cases.jsonl \
  --known-good-diff <private-known-good.diff> \
  --output results/case-proofs/user-idempotency-1.0.json
```
