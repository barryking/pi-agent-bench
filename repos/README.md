# Repositories used by coding cases

Put a clean copy of each real coding project in this folder:

```text
repos/
  code-idempotency-001/
```

Git ignores everything here except this README. This helps stop a private or
third-party project from being committed by mistake.

## Add a repository

Run:

```bash
git clone <repository-url> repos/code-idempotency-001
git -C repos/code-idempotency-001 checkout <full-commit-sha>
git -C repos/code-idempotency-001 status --short
git -C repos/code-idempotency-001 rev-parse HEAD
```

The `status` command must print nothing. This means the copy is clean.

The last command prints the exact starting commit. Put it in the case:

```json
{
  "metadata": {
    "fixture": "repos/code-idempotency-001",
    "source_commit": "<full-commit-sha>",
    "dataset_version": "1.0",
    "synthetic": false
  }
}
```

The validator stops if the repository is dirty or is on a different commit.

## What happens during a run

The copy in this folder is never the agent's working folder.

For each try, Inspect copies it to `/workspace` inside a new Docker container.
Pi changes the copy. The framework saves the final diff and throws the
container away.

You do not need to reset the repository after a run. The next try starts from
the same clean commit.

If you want a new starting point, check out a different commit. Then update
`source_commit` and increase `dataset_version`.
