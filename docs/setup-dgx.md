# DGX model server setup

A DGX runs the AI model. The Mac still runs Pi, Docker, tests, and reports.

```text
Mac runs the task
  └─ sends model questions over the network
       └─ DGX sends model answers back
```

The DGX does not need the case repository.

## 1. Check the DGX

Finish NVIDIA's normal first-time setup.

Check that Docker can see the GPU:

```bash
nvidia-smi
docker run --rm --gpus all nvcr.io/nvidia/cuda:13.0.0-base-ubuntu24.04 nvidia-smi
```

Stop if these commands fail.

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

Before starting it, write down:

- the exact vLLM image;
- the exact model name and revision;
- the compression type, such as FP8 or NVFP4;
- the context size;
- whether prefix caching is on; and
- any special attention setting.

These details are part of the result. Changing them makes a different profile.

Follow the current vLLM and NVIDIA instructions for your exact DGX and model.
Do not copy an old command without checking it.

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
  --profile local-candidate \
  --profiles configs/model-baselines.local.json \
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
