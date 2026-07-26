# Repositories used by coding cases

Put a clean copy of each real coding project in this folder:

```text
local-repos/
  source-project-name/
```

Git ignores everything here except this README. This helps stop a private or
third-party project from being committed by mistake.

You do not need this folder for the owned starter suite. It uses the committed
code under `starting-repos/`.

## Add a repository

Run:

```bash
git clone <repository-url> local-repos/source-project-name
git -C local-repos/source-project-name checkout <full-commit-sha>
git -C local-repos/source-project-name status --short
git -C local-repos/source-project-name rev-parse HEAD
```

The `status` command must print nothing. This means the copy is clean.

The last command prints the exact starting commit. Put it in the case:

```json
{
  "metadata": {
    "starting_repository": "local-repos/source-project-name",
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
