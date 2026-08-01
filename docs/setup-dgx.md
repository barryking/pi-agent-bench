# DGX model server setup

A DGX runs the AI model. The Mac still runs Pi, Docker, tests, and reports.

```text
Mac runs the task
  └─ sends model questions over the network
       └─ DGX sends model answers back
```

The DGX does not need the case repository.

## 1. Check the DGX

Finish NVIDIA's normal first-time setup and install the recommended updates
for your exact DGX model.

DGX OS includes NVIDIA's drivers and system settings. Check that the operating
system can see the GPU:

```bash
nvidia-smi
```

Stop if this command cannot identify the NVIDIA GPU or driver.
On DGX Spark, `nvidia-smi` may report `Memory-Usage: Not Supported` because the
GPU uses unified memory. NVIDIA documents this as expected; it is not a failed
GPU check.

Use NVIDIA's current guide for your hardware:

- [DGX Spark first-time setup](https://docs.nvidia.com/dgx/dgx-spark/first-boot.html)
- [DGX OS initial setup](https://docs.nvidia.com/dgx/dgx-os-7-user-guide/initial_setup.html)

## 2. Give the DGX a safe network address

The Mac must be able to reach the DGX.

Use a trusted local network. Do not open the model server to the public
internet.

From the Mac:

```bash
ping <dgx-address>
```

Some networks block `ping`. If it fails, confirm the address with SSH or the
HTTP checks below instead. If possible, give the DGX a fixed address so it does
not keep changing.

## 3. Choose a model and server

NVIDIA publishes the current deployment routes for DGX Spark. This guide uses
NVIDIA's **vLLM for Inference** Spark playbook because it exposes the
OpenAI-compatible model API that Pi Agent Bench needs:

- [NVIDIA DGX Spark playbooks](https://build.nvidia.com/spark)
- [vLLM for Inference on DGX Spark](https://build.nvidia.com/spark/vllm)

Follow that Spark-specific playbook and its current supported-model matrix. Use
the NVIDIA container and command it recommends for the chosen model; do not
substitute a generic x86 vLLM image or an arbitrary upstream build. Pin and
record the container tag and image digest. The benchmark does not install or
manage the model server.

Pi is a tool-using coding agent. Choose a model with working tool calling and
enable the model-specific parser required by the Spark playbook. In vLLM,
automatic tool choice is disabled by default; the usual server options include
`--enable-auto-tool-choice` and the correct `--tool-call-parser` for the model.
Do not guess the parser: use the playbook or
[vLLM's model-specific tool-calling table](https://docs.vllm.ai/en/latest/features/tool_calling/).

Before starting the server, write down:

- the exact model-server version;
- the exact container tag and image digest;
- the exact model name and revision;
- the compression type, such as FP8 or NVFP4;
- the CUDA and model-framework versions;
- the context size;
- whether prefix caching is on; and
- the full performance settings used to start the server.

These details are part of the result. Changing them makes a different profile.

Keep the model server running across normal benchmark trials. Record cold
model starts separately from warm trials. Restarting or changing the server
between trials makes the timing harder to compare.

## 4. Check the server on the DGX

The server should have these routes:

```text
/health
/v1/models
/v1/chat/completions
```

The checks below use an authenticated server. Set the same private key on the
DGX that you pass to the playbook's vLLM `--api-key` option:

```bash
export LOCAL_MODEL_API_KEY='<private-key>'
```

Check the server routes on the DGX:

```bash
curl http://127.0.0.1:8000/health \
  -H "Authorization: Bearer $LOCAL_MODEL_API_KEY"
curl http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer $LOCAL_MODEL_API_KEY"
```

Send one small model request:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $LOCAL_MODEL_API_KEY" \
  -d '{
    "model": "<exact-model-name>",
    "messages": [{"role": "user", "content": "Reply with OK"}],
    "max_tokens": 16
  }'
```

Then prove that automatic tool calling works. A successful response contains a
`choices[0].message.tool_calls` entry for `get_current_directory`:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $LOCAL_MODEL_API_KEY" \
  -d '{
    "model": "<exact-model-name>",
    "messages": [{
      "role": "user",
      "content": "Call get_current_directory now. Do not answer in text."
    }],
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_current_directory",
        "description": "Return the current working directory",
        "parameters": {"type": "object", "properties": {}}
      }
    }],
    "tool_choice": "auto",
    "max_tokens": 128,
    "temperature": 0
  }'
```

Do not start a benchmark until both requests work. A server that can answer
plain text but cannot emit tool calls is not ready for Pi.

If you intentionally run without vLLM API-key authentication, omit the
Authorization headers and keep the endpoint restricted to a trusted private
network. `LOCAL_MODEL_API_KEY` on the Mac must still be a non-empty placeholder
because the OpenAI-compatible client requires one; the unauthenticated server
will ignore it.

## 5. Check it from the Mac

Set the same key in the Mac shell for these checks:

```bash
export LOCAL_MODEL_API_KEY='<the-same-private-key>'
curl http://<dgx-address>:8000/health \
  -H "Authorization: Bearer $LOCAL_MODEL_API_KEY"
curl http://<dgx-address>:8000/v1/models \
  -H "Authorization: Bearer $LOCAL_MODEL_API_KEY"
```

Set `.env.local`:

```text
LOCAL_MODEL_BASE_URL=http://<dgx-address>:8000/v1
LOCAL_MODEL_API_KEY=<the-same-private-key-or-private-network-placeholder>
```

Set the exact model details in
`configs/model-baselines.local.json`.

Then run:

```bash
pi-bench doctor --agent-profile local-candidate-agent
```

## 6. Watch the DGX during a run

Useful server measurements include:

- time until the first token;
- output tokens each second;
- prompt processing speed;
- GPU memory;
- GPU use;
- queue time; and
- power use.

These measurements help explain why a run was fast or slow. They do not replace
the success and quality scores.

## Keep it safe

- Bind the server only to a trusted network.
- Use a firewall.
- Use a key or network rule when possible.
- Do not store provider secrets in Git.
- Keep a note of every model and server change.
