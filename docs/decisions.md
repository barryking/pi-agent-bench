# Important design choices

## Use Inspect

Inspect owns runs, limits, logs, scores, and detailed evidence.

Pi Agent Bench adds the Pi connection, clean Docker sandbox, ready-to-run
cases, protected verifiers, model and agent profiles, and comparison dashboard.

## Measure the finished outcome

A case asks for one finished repository result.

Why: users care whether the job was completed well and quickly.

## Keep agent profiles general

Agent profiles can change instructions, tools, skills, extensions, prompts,
settings, MCP, and other Pi behaviour.

Why: many agent changes can affect time and quality. The profile name and
content fingerprint record the whole setup without inventing special switches.

## Prefer executable evidence

Protected verifiers and required behaviour decide final quality and success.

Why: there may be many correct patches. A hidden test contract is fairer than
comparing against one reference patch.

## Keep the model and agent separate

A model profile says which inference model and settings to use.

An agent profile says how Pi is configured.

This lets us compare:

- several models with vanilla Pi;
- several agent setups on one model; or
- every selected model-and-agent combination.

## Use clean containers

Every trial gets a new Docker workspace and a private temporary Pi home.
Personal Pi resources are not loaded by accident.

## Put scores in Inspect first

Inspect logs are the source evidence. Dashboard files are disposable exports.

## Compare only matching cohorts

Rankings require the same case version, verifier fingerprint, limits, Pi
version, container, and case coverage. Use at least three trials per setup and
case before trusting small differences.

The benchmark records the Docker image ID and the source fingerprint used to
build it. A run stops when the image is stale. This prevents a result from
claiming verifier code that was not inside its container.

## Main comparison

The default view is quality against total outcome time. Upper-left is better:
more quality in less time.
