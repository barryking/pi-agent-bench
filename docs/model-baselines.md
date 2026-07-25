# Model and context baselines

This document records starting hypotheses for experiments. Values are not
benchmark results from this repository.

## Planning candidates

| Candidate | Native context | Initial operating profile |
|---|---:|---:|
| Qwen3.6-35B-A3B | 256K | 128K |
| Qwen3.5-122B-A10B quantised | 256K | 128K |

Suggested planning context bands:

- 32K;
- 64K;
- 128K;
- 192K stress; and
- 224K boundary.

Reserve enough space for model reasoning and output. The complete context
includes system instructions, tools, source material, reasoning and response.

## Coding candidate

| Candidate | Native context | Initial operating profile |
|---|---:|---:|
| Qwen3-Coder-Next FP8 | 256K | 128K |

Single-DGX-Spark reports indicate that runtime and attention-backend choices
can make the practical context limit lower than the model's native limit. Start
with 128K, measure actual memory headroom, and treat larger profiles as separate
configurations.

Suggested coding context bands:

- 32K;
- 64K;
- 96K;
- 128K; and
- 160K stress if the runtime supports it reliably.

## Configuration identity

A benchmark model identifier should include:

```text
model weights
quantisation
serving runtime and version
attention backend
maximum model length
KV-cache type
prefix-caching setting
sampling configuration
```

For example:

```text
qwen3-coder-next-fp8__vllm-x.y__flashinfer__ctx-131072__prefix-cache
```

Do not compare results labelled only with a marketing model name.

## Sources to verify during implementation

- Qwen model cards: <https://huggingface.co/Qwen>
- NVIDIA DGX Spark developer forum:
  <https://forums.developer.nvidia.com/c/accelerated-computing/dgx-spark-gb10/719>
- Pi documentation: <https://pi.dev/docs/latest>
- Inspect AI documentation: <https://inspect.aisi.org.uk/>

Record exact source URLs and access dates beside measured runtime
configurations when the first benchmark is published.
