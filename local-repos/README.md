# Local external starting repositories

Put clean checkouts of external or private coding projects in this folder:

```text
local-repos/
  source-project-name/
```

Git ignores everything here except this README. `local-repos/` is a storage
location, not a case type or dataset. It prevents private or third-party source
from being committed accidentally.

The maintained starter suite does not use this folder. Its project-owned
starting code is committed under `starting-repos/`.

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
    "score_components": ["requirements"],
    "draft": true,
    "synthetic": false
  }
}
```

The validator stops if the repository is dirty or is on a different commit.
Keep `draft` set to `true` until the verifier and case proof are complete.
Merely checking out the declared commit does not change the dataset version.

## What happens during a run

The copy in this folder is never the agent's working folder.

For each try, Inspect copies it to `/workspace` inside a new Docker container.
Pi changes the copy. The framework saves the final diff and throws the
container away.

You do not need to reset the repository after a run. The next try starts from
the same clean commit.

If you want a new starting point, check out a different commit. Then update
`source_commit`, rerun the case proof, and increase `dataset_version` because
old and new results are not comparable.
