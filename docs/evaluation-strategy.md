# Evaluation strategy

## Questions the benchmark should answer

1. Can a local model complete representative planning and coding tasks
   accurately enough?
2. How long does successful completion take?
3. How reliable is the result across repeated runs?
4. Where does performance degrade as context grows?
5. What capability is lost or gained relative to hosted controls?
6. Is the local quality, privacy and marginal-cost trade-off worth the hardware
   and operational investment?

## Evaluation suites

### Planning

Planning cases produce an architecture or implementation plan from a controlled
context pack.

Primary scoring dimensions:

- critical constraints recognised;
- architectural correctness;
- completeness;
- risks and unknowns identified;
- prohibited recommendations avoided; and
- output clarity and actionability.

Exact-string matching is insufficient. Start with deterministic checks for
explicit facts, then use a rubric scored by an independent model and calibrate
it against blinded human review.

### Coding

Coding cases start from a clean repository fixture and execute the real agent
with its tools.

Primary scoring should be objective:

- hidden tests;
- build and type-check;
- lint;
- regression tests;
- required and forbidden file changes; and
- task-specific assertions.

Do not use similarity to a reference patch as the main measure. Different
implementations may be equally correct.

### End to end

End-to-end cases first generate a frozen planning artifact, then start a new
coding session using that artifact. This suite measures the combined workflow
without allowing the planning transcript to consume coding context.

## Metrics

### Quality

- pass@1;
- success across repeated runs;
- perfect-task rate;
- partial verifier score;
- regression rate;
- planning rubric score; and
- blinded human preference on a sample.

### Performance

- complete wall-clock duration;
- time to first model token;
- time to first useful action;
- cold prompt-processing duration;
- warm-turn prompt-processing duration;
- output tokens per second;
- model turns and tool calls;
- failed tool calls and retries;
- input, cached-input and output tokens;
- peak context and compactions; and
- timeout or infrastructure failures.

Always separate model time, tool time and verification time where the available
traces allow it.

## Comparison controls

- Use the same Pi version, instructions, tools and limits for every model.
- Record sampling configuration and seed when supported.
- Run at least three trials per case for exploratory comparisons.
- Use more repetitions before making close investment decisions.
- Run context bands such as 32K, 64K and 128K using meaningful material rather
  than arbitrary padding.
- Include both cold-cache and production-like prefix-cache runs.
- Version the dataset and never rewrite historical expected results in place.

## Leadership reporting

Avoid collapsing the outcome into one opaque score. Report:

1. task success and confidence interval;
2. median and p95 successful-task duration;
3. failure categories;
4. quality versus time;
5. quality versus operating cost; and
6. representative successful and failed trajectories.

A useful decision statement is specific:

> At dataset version X, configuration Y completed Z% of tasks, compared with
> the hosted control at A%, with median successful-task duration B and p95 C.

Raw tokens per second should be supporting evidence, not the headline.
