# Configure model resources

A model profile is a reusable definition of one concrete inference resource.
Its profile name becomes the agent-visible resource alias, so it must match:

```text
[a-z0-9][a-z0-9._-]*
```

The name cannot contain `/`, whitespace, or provider syntax.

## Inspect bridge

Use `inspect-bridge` for local OpenAI-compatible servers, ordinary cloud APIs,
and OpenRouter:

```json
{
  "kind": "local",
  "model": "openai/nvidia/example-model",
  "execution": {
    "mode": "inspect-bridge",
    "model_args": {},
    "model_args_env": {
      "base_url": "LOCAL_MODEL_BASE_URL",
      "api_key": "LOCAL_MODEL_API_KEY"
    },
    "generate_config": {
      "temperature": 0
    }
  },
  "capabilities": {
    "context_tokens": 131072,
    "max_output_tokens": 32768,
    "reasoning": true,
    "input": ["text"]
  },
  "configuration": {
    "weights": "example@exact-revision",
    "runtime": "vllm",
    "runtime_version": "exact-version",
    "quantisation": "NVFP4"
  }
}
```

`model_args` contains public-safe Inspect constructor arguments.
`model_args_env` maps constructor arguments to host environment names. Each
resource is constructed independently; Pi Agent Bench never mutates
process-wide provider variables around an evaluation.

`generate_config` contains Inspect generation defaults. Secret-like fields are
invalid in public arguments, generation config, capabilities, and
configuration.

### Common bridged providers

The `model` prefix selects Inspect's provider adapter. Common shapes are:

| Server or provider | Model value | Environment-backed arguments |
|---|---|---|
| vLLM, SGLang, llama.cpp, or another OpenAI-compatible server | `openai/<exact-served-id>` | `base_url`, usually `api_key` |
| Ollama | `ollama/<exact-model-tag>` | `base_url` when not using `http://localhost:11434/v1` |
| OpenRouter | `openrouter/<provider>/<exact-model-slug>` | `api_key` |
| OpenAI | `openai/<exact-model-id>` | `api_key` |
| Anthropic | `anthropic/<exact-model-id>` | `api_key` |
| Google | `google/<exact-model-id>` | `api_key` |

For a local endpoint, `pi-bench doctor` queries `/v1/models` and checks that
the part after the Inspect provider prefix exactly matches an advertised ID.
This catches a wrong Ollama tag or vLLM `--served-model-name` before a run.
Non-Ollama local bridge resources must configure `base_url`; Ollama uses its
native localhost default when one is omitted.

Use exact model IDs and revisions for repeatable comparisons. Provider aliases
that move over time are useful for applications but make benchmark identity
less precise.

## Pi direct

Use `pi-direct` only where Inspect cannot construct the provider/authentication
path. The first supported use is OpenAI Codex subscription OAuth:

```json
{
  "kind": "hosted",
  "model": "openai-codex/example-model",
  "execution": {
    "mode": "pi-direct",
    "provider": "openai-codex",
    "model": "example-model",
    "auth_file_env": "PI_AUTH_FILE",
    "thinking_level": "high"
  },
  "capabilities": {
    "context_tokens": 131072,
    "max_output_tokens": 32768,
    "reasoning": true,
    "input": ["text", "image"]
  },
  "configuration": {
    "billing": "ChatGPT subscription",
    "authentication": "Pi OAuth",
    "model_revision": "exact-version-or-snapshot"
  }
}
```

The auth file path is resolved from the named host environment variable. The
file content is never fingerprinted or copied to results.

`thinking_level` is execution behaviour, so it belongs in `execution` and
changes the model-resource fingerprint. Schema-1 local files that still place
it in `configuration` remain readable for compatibility.

## Capabilities and case limits

Capabilities are required and generate Pi model metadata. Each case
`context_tokens` limit caps the advertised resource window. `max_output_tokens`
cannot exceed the real context window and is also capped to the effective case
window.

## Reproducibility

Record measured facts such as:

- exact model revision or weights;
- runtime and version;
- quantisation;
- attention backend;
- configured context;
- caching;
- generation defaults;
- provider snapshot; and
- direct thinking level.

Clearly distinguish measured facts from estimates. A change to weights,
runtime, context, generation settings, or execution path changes the model
fingerprint and therefore the composed agent-profile fingerprint.

Local resources have complete zero inference cost. Hosted cost comes only from
runtime/provider telemetry; missing cloud cost is partial or unavailable, never
zero.
