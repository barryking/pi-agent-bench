# Important design choices

## Use Inspect

Inspect owns execution, limits, logs, model calls, scores, and detailed
evidence. Pi Agent Bench adds only the Pi adapter, clean sandbox, profiles,
cases, protected verification, generated comparison identity, and reports.

## Measure the finished outcome

A case asks for one observable repository result. Protected executable checks,
not similarity to one reference patch or another model's opinion, determine
quality and success.

## Treat case maturity as a lifecycle

There is no permanent pilot case type. A new case begins as a non-runnable
draft, passes structural validation and a known-good proof, then receives real
candidate trials before acceptance into a maintained dataset.

`prove-case` is a maintainer authoring check, not a per-run user prerequisite.
It demonstrates untouched failure and one known-good success. Candidate trials
remain necessary to assess difficulty, stability, limits, and ambiguous
instructions.

External source under `local-repos/` does not define a different case class.
It is only an ignored location for a pinned third-party or private starting
repository.

## Compare complete agent profiles

The primary benchmark unit is `AgentProfile`: one `PiProfile`, an ordered set of
model resources, and a default resource.

This represents the system teams actually run—guidance, tools, skills,
extensions, settings, MCP access, and every available model. A model-only
baseline is two otherwise-identical agent profiles with different single
resources.

## Keep reusable components separate

- `PiProfile` defines Pi harness behaviour.
- `ModelProfile` defines one concrete inference resource.
- `AgentProfile` composes them into a runnable comparison unit.

There is no `BenchmarkProfile`, semantic model-role schema, or benchmark-owned
router. Selected Pi extensions may switch among configured resources through
Pi's native registry.

## Bridge models through Inspect when possible

Local OpenAI-compatible endpoints, normal cloud APIs, and OpenRouter are
independently instantiated Inspect models and exposed to Pi as
`inspect-bridge/<resource-name>`.

Pi-direct execution is reserved for provider/authentication paths Inspect
cannot instantiate, initially OpenAI Codex subscription OAuth. Bridged secrets
remain on the host; selected direct authentication alone is staged.

## Enforce one profile-wide run boundary

Every Pi invocation—bridge-only, direct-only, or hybrid—is wrapped by the same
turn/token supervisor and sandbox timeout. Inspect remains authoritative for
bridged usage. Pi events supply only direct-attributed usage. Merged totals
never add Pi bridge events a second time.

## Isolate project-owned Pi configuration

Runs always pass `--no-approve`. The selected Pi profile is staged into an
isolated global Pi home. Repository `.pi` and `.agents/skills` resources cannot
silently change the harness.

Repository `AGENTS.md` and `CLAUDE.md` context files remain enabled because
they are part of the case input and starting-repository fingerprint.

## Protect verification

Verifier source stays root-owned under `/opt/verifiers`, unreadable by the Pi
user, and outside `/workspace`. A case must use exactly:

```text
python3 /opt/verifiers/<case-id>/verify.py
```

## Separate profile identity from cohort identity

The composed profile fingerprint changes with its Pi profile, resource
bindings, resource order, or default. The generated cohort fingerprint changes
with use-case inputs, repositories, verifiers, scoring, limits, shared run
conditions, Pi/Inspect versions, execution-protocol source, or sandbox runtime.

Profile definition files are deliberately excluded from cohort identity, so
different profiles can remain valid comparison arms.

Planned trial count is campaign metadata rather than cohort input. This permits
later campaigns to add compatible evidence. Equal completed trial coverage is
still required before profiles receive a shared ranking. One `benchmark_id`
links the profile arms from a single invocation and prevents repeated campaigns
with the same trial numbers from being matched to one another.

## Report missing measurements honestly

Unavailable fields are `null`; zero means measured zero. Inference cost
coverage is:

- `complete`: local-only, or every used cloud call reports cost;
- `partial`: some used cloud cost is reported and some is missing;
- `unavailable`: cloud inference occurred and none of it reported cost.

Provider inference cost is not total cost of ownership.

## Compare only matching evidence

Rankings require one generated cohort identity, equal case coverage, equal
completed trial counts, and at least three trials per profile and case before
small differences are trusted.
