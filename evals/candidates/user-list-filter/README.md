# User list filter candidate

Status: **draft candidate; not ready for benchmark comparisons**.

This proposed case exercises a small API change in a public FastAPI service:

- add an optional `activated` filter to the user list;
- preserve the existing response when the filter is absent;
- reject invalid page and limit values;
- add tests; and
- document the API.

The case definition and protected verifier are tracked here. The third-party
starting repository is not tracked; prepare it by following
[`local-repos/README.md`](../../../local-repos/README.md).

This file is for case maintainers. Before enabling candidate trial runs, a
maintainer must:

1. complete and review the instruction and verifier;
2. create a private known-good implementation diff;
3. run the proof process in
   [`docs/scoring-and-extending.md`](../../../docs/scoring-and-extending.md);
4. set `metadata.draft` to `false`; and
5. run several candidate trials before proposing it for a maintained dataset.

Normal benchmark users should run the maintained starter suite and do not need
to prove this candidate.
