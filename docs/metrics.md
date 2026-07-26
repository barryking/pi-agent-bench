# What Pi Agent Bench measures

A metric is one measured fact.

Do not use one metric to choose a model. A fast model is not useful if it
cannot finish the task.

The main benchmark view joins two facts:

```text
quality versus total task time
```

The dashboard shows this first. Upper-left is best: better work in less time.
It does not mix the two facts into a mystery score.

## Result quality

Pi Agent Bench records:

- quality from `0` to `1`;
- success as yes or no;
- each verifier or rubric part;
- success across repeated trials; and
- how steady the result is.

The dashboard treats one model-and-agent pair as one comparison arm. For
example, `model-a + team-agent` stays separate from `model-a` using vanilla Pi.

Inspect also calculates:

- the average;
- the amount of uncertainty;
- `pass@k`, which asks whether at least one of several tries works;
- `pass^k`, which asks whether all of several tries work.

Read `pass@k` and `pass^k` from the success field.

## Time

Pi Agent Bench records:

- total trial time;
- Pi process time;
- Inspect working time;
- model working time from Inspect events;
- tool working time from Inspect events;
- time for successful tasks; and
- middle and slow-end times across many trials.

Planned time measurements include:

- time until the first token;
- verifier time; and
- queue time.

## Tokens

A token is a small piece of text used by a model.

Pi Agent Bench records these when the provider reports them:

- input tokens;
- cached input tokens;
- cache-write tokens;
- reasoning tokens;
- output tokens; and
- total tokens.

The dashboard includes success compared with tokens. This helps answer:

> How much model work was needed to get a correct result?

## Local model speed

For vLLM, DGX, and other local servers, useful speed facts include:

- output tokens each second;
- prompt tokens each second;
- time until the first token; and
- queue time.

These are server facts. They help explain total task time.

They are not proof of task quality.

The dashboard now shows **observed output tokens per model second**. It divides
Inspect's output-token count by Inspect's model working time.

This is useful for a first comparison. It is not the same as vLLM engine
throughput. It does not yet show first-token delay, queue time, or prompt
speed. Those need facts from the local model server.

## Agent behaviour

Pi Agent Bench records:

- model turns;
- tool calls;
- failed tool calls;
- retries;
- context shortening, called compaction; and
- process return codes.

These facts help explain why a model was slow or failed.

## Cost

Cloud providers may report a cost for each request.

Pi Agent Bench can show:

- total reported cost;
- cost for each successful task; and
- how many trials include cost data.

Missing cost stays empty. It is never changed to zero.

Local cost needs extra facts, such as:

- hardware price;
- power use;
- expected life;
- maintenance time; and
- how busy the hardware is.

## Evidence files

```text
logs/*.eval
```

These are the full Inspect records. They show the model messages, tool use, and
scores.

```text
results/*.json
```

These are small records used for comparisons.

They are copies, not the main evidence. Rebuild them with:

```bash
pi-bench export --logs-dir logs --results-dir results
```

```text
results/*.diff
```

These show code changes.

```text
results/runs.csv
```

This is one wide table row for each trial.

```text
results/metrics.jsonl
```

This is one metric fact on each line. It is easy for chart and database tools
to read.

Every line includes both `model_profile` and `agent_profile`. It also includes
safe configuration hashes. This lets another chart tool compare the same model
with different tools or instructions.

## Dashboard charts

The dashboard shows:

- success by profile;
- quality by profile;
- time for successful tasks;
- tokens for successful tasks;
- success compared with tokens;
- quality compared with time;
- quality compared with cost;
- case coverage;
- changes from a chosen baseline;
- uncertainty;
- rank changes across trials; and
- history for one case.

Planning and coding are never mixed in one score.

Different dataset versions are never mixed.

Cold and warm cache runs should not be mixed.

## Invalid attempts

A trial enters a comparison only when:

- Inspect says the log finished;
- the sample has no run error; and
- the quality score is a real number.

Other attempts go under:

```text
results/_invalid/
```

They are useful for finding system problems. They do not count as model
failures or ranking evidence.

## Measurements still to add

The most useful missing measurements are:

- first-token time;
- first useful action time;
- prompt and output speed reported by local servers;
- verifier time;
- peak context use;
- GPU memory and use;
- power and energy;
- local cost estimates; and
- clear failure groups.
