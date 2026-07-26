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

If possible, give the DGX a fixed address so it does not keep changing.

## 3. Choose a model and server

The first supported example is vLLM. vLLM is software that serves a model using
an API that looks like OpenAI's API.

Install and run the model server directly on the DGX. Follow the current
installation guide for the DGX architecture, CUDA version, model, and
compression type. The benchmark does not install or manage the model server.

For vLLM, read:

- [vLLM GPU installation](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/)
- [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/)

Before starting the server, write down:

- the exact model-server version;
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

Check them on the DGX:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/models
```

Send one small model request:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<exact-model-name>",
    "messages": [{"role": "user", "content": "Reply with OK"}],
    "max_tokens": 16
  }'
```

Do not start a benchmark until this works.

## 5. Check it from the Mac

```bash
curl http://<dgx-address>:8000/health
curl http://<dgx-address>:8000/v1/models
```

Set `.env.local`:

```text
LOCAL_MODEL_BASE_URL=http://<dgx-address>:8000/v1
LOCAL_MODEL_API_KEY=<your-key-or-private-network-placeholder>
```

Set the exact model details in
`configs/model-baselines.local.json`.

Then run:

```bash
pi-bench doctor \
  --model-profile local-candidate \
  --model-profiles-file configs/model-baselines.local.json \
  --env-file .env.local
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
