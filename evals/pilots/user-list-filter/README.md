# User list filter pilot

This is one small, real API change.

The starting project is a public FastAPI user service. The outcome case asks
for this change:

- add an optional `activated` filter to the user list;
- keep the old response when the filter is missing;
- reject silly page and limit numbers;
- add tests; and
- explain the API in the project README.

The case uses a protected verifier. Before using this case in a
comparison, run `pi-bench prove-case` with a private known-good patch.

This optional pilot is not bundled because its repository is owned by someone
else. Fetch its exact starting commit with:

```bash
git clone \
  https://github.com/Pytest-with-Eric/pytest-fastapi-crud-example.git \
  local-repos/pytest-fastapi-crud-example
git -C local-repos/pytest-fastapi-crud-example checkout \
  d47bb85f26c4dc55877563a6c79ecef2c8d50706
```

Use `evals/starter/` when you want cases that need no external code.

The proof must show:

- the untouched project fails the new checks; and
- the known-good patch passes them.
