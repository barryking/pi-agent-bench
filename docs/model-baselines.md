# Choosing models and context sizes

A profile is one exact model setup.

Two runs are not the same profile when they use different:

- model versions;
- number compression;
- server versions;
- context sizes;
- cache settings; or
- generation settings.

Record these details in the profile JSON.

## Start with roles, not favourite models

Prepare profiles for:

- a local candidate;
- a strong hosted control;
- a cheaper hosted control;
- an independent planning grader; and
- an optional subscription control.

Model names change over time. Check current provider and model documentation
before filling the profile.

## Context

Context is the text a model can hold during one request.

Agent work also needs room for:

- system instructions;
- tool descriptions;
- previous messages;
- file contents;
- tool results; and
- the model's answer.

A model that says it supports 128K does not leave all 128K for source files.

Start with realistic smaller tasks. Test larger context bands later:

- 32K;
- 64K;
- 96K;
- 128K;
- larger stress tests when the server supports them.

Do not fill context with repeated nonsense. Use useful files and realistic
distractions.

## Check the exact setup

Before accepting results, record:

- provider;
- model name;
- model revision;
- compression;
- server name and version;
- attention backend;
- context limit;
- KV-cache settings;
- prefix caching;
- temperature and seed, when supported;
- hardware; and
- cost currency for billed providers.

If one of these changes, treat the result as a new setup.
