# User idempotency candidate

Status: **draft candidate; not ready for benchmark comparisons**.

This proposed case asks an agent to make user creation safe when a client
repeats the same request. It uses the same pinned external repository as the
smaller `user-list-filter` candidate.

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
