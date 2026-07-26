# User list filter pilot

This is one small, real API change.

The starting project is a public FastAPI user service. Both the planning case
and the coding case ask for the same change:

- add an optional `activated` filter to the user list;
- keep the old response when the filter is missing;
- reject silly page and limit numbers;
- add tests; and
- explain the API in the project README.

The coding case uses a protected verifier. Before using this case in a
comparison, run `pi-bench prove-case` with a private known-good patch.

The proof must show:

- the untouched project fails the new checks; and
- the known-good patch passes them.
