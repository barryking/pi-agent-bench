# Roadmap

## Phase 1 — Contracts and scaffold

- [x] Public-safe repository guidance
- [x] Golden-case schema and validation
- [x] Synthetic planning and coding examples
- [x] Pi JSON-event process wrapper
- [x] Basic deterministic planning checks
- [ ] Select an open-source licence

## Phase 2 — Inspect integration

- [ ] Create an Inspect custom agent for Pi
- [ ] Run Pi inside a disposable Docker sandbox
- [ ] Route Pi model calls through Inspect's sandbox agent bridge
- [ ] Capture model usage and trajectory
- [ ] Enforce time, turn and token limits

## Phase 3 — Verifiers

- [ ] Execute coding verifier commands after the agent stops
- [ ] Support weighted verifier results
- [ ] Add planning rubric scoring
- [ ] Add an independent judge-model adapter
- [ ] Add a human-review export

## Phase 4 — Provider matrix

- [ ] Add DGX Spark vLLM configuration
- [ ] Add hosted quality control
- [ ] Add hosted cost control
- [ ] Record cold and warm inference measures
- [ ] Run 32K, 64K and 128K context profiles

## Phase 5 — Reporting

- [ ] Produce per-run JSON artifacts
- [ ] Aggregate pass rate, median and p95 duration
- [ ] Categorise failures
- [ ] Generate quality-versus-time and quality-versus-cost charts
- [ ] Generate a concise leadership report

## Later

- Public benchmark packaging
- Harbor/Terminal-Bench compatibility
- CI regression runs
- Private golden-dataset integration
- Hardware utilisation and energy measurements
