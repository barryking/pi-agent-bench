const test = require("node:test");
const assert = require("node:assert/strict");

const {
  caseBootstrapInterval,
  comparisonReadiness,
  matchedQualityDelta,
  metricInterval,
  selectComparisonRows,
  successfulMetricValues,
  wilsonInterval
} = require("../../src/pi_agent_bench/viewer/statistics.js");

test("Wilson interval stays within zero and one for small success samples", () => {
  const interval = wilsonInterval([1, 1, 0]);
  assert.equal(interval.method, "Wilson");
  assert.ok(interval.low >= 0);
  assert.ok(interval.high <= 1);
  assert.ok(interval.low < 2 / 3);
  assert.ok(interval.high > 2 / 3);
});

test("continuous metrics use a deterministic case-level bootstrap", () => {
  const rows = [
    { case_id: "a", value: 0.2 },
    { case_id: "a", value: 0.4 },
    { case_id: "b", value: 0.8 },
    { case_id: "b", value: 1.0 }
  ];
  assert.deepEqual(caseBootstrapInterval(rows), caseBootstrapInterval(rows));
  assert.equal(metricInterval(rows, "quality.score").method, "case bootstrap");
});

test("quality delta is described as matched rather than paired", () => {
  const rows = [
    { metric: "quality.score", profile: "base", case_id: "a", trial_number: 1, value: 0.4 },
    { metric: "quality.score", profile: "model", case_id: "a", trial_number: 1, value: 0.8 },
    { metric: "quality.score", profile: "base", case_id: "b", trial_number: 1, value: 0.5 },
    { metric: "quality.score", profile: "model", case_id: "b", trial_number: 1, value: 0.7 }
  ];
  const delta = matchedQualityDelta(rows, "model", "base");
  assert.equal(delta.matches, 2);
  assert.match(delta.method, /matched repetitions/);
  assert.ok(Math.abs(delta.mean - 0.3) < 1e-12);
});

test("quality delta matches profiles within the same benchmark campaign", () => {
  const rows = [
    { metric: "quality.score", benchmark_id: "first", profile: "base", case_id: "a", trial_number: 1, value: 0.1 },
    { metric: "quality.score", benchmark_id: "first", profile: "model", case_id: "a", trial_number: 1, value: 0.2 },
    { metric: "quality.score", benchmark_id: "second", profile: "base", case_id: "a", trial_number: 1, value: 0.8 },
    { metric: "quality.score", benchmark_id: "second", profile: "model", case_id: "a", trial_number: 1, value: 1.0 }
  ];
  const delta = matchedQualityDelta(rows, "model", "base");
  assert.equal(delta.matches, 2);
  assert.ok(Math.abs(delta.mean - 0.15) < 1e-12);
});

test("successful metrics are matched to the exact case and repetition", () => {
  const rows = [
    { metric: "quality.success", run_id: "same-run", case_id: "pass", trial_number: 1, value: 1 },
    { metric: "quality.success", run_id: "same-run", case_id: "fail", trial_number: 1, value: 0 },
    { metric: "time.wall", run_id: "same-run", case_id: "pass", trial_number: 1, value: 10 },
    { metric: "time.wall", run_id: "same-run", case_id: "fail", trial_number: 1, value: 99 }
  ];

  assert.deepEqual(successfulMetricValues(rows, "time.wall"), [10]);
});

test("dashboard selection never mixes cohort fingerprints and can pool run labels", () => {
  const rows = [
    { dataset_version: "v1", cohort_fingerprint: "one", run_name: "first", cache_state: "warm" },
    { dataset_version: "v1", cohort_fingerprint: "one", run_name: "second", cache_state: "warm" },
    { dataset_version: "v1", cohort_fingerprint: "two", run_name: "first", cache_state: "warm" }
  ];
  const selected = selectComparisonRows(rows, {
    datasetVersion: "v1",
    cohortFingerprint: "one",
    runName: "__all_runs__",
    cacheState: "warm"
  });
  assert.deepEqual(selected.map(row => row.run_name), ["first", "second"]);
});

test("ranking requires identical coverage and complete version evidence", () => {
  const cases = ["a", "b", "c", "d", "e"];
  const profiles = ["one", "two"];
  const dimensions = {
    cohort_fingerprint: "cohort",
    scoring_method: "verifier",
    framework_version: "1",
    inspect_version: "1",
    pi_version: "1",
    sandbox_image_id: "sha256:image"
  };
  const cohort = profiles.flatMap(profile => cases.flatMap(caseId =>
    [1, 2, 3].map(trial_number => ({
      ...dimensions,
      metric: "quality.score",
      profile,
      case_id: caseId,
      trial_number,
      value: 1
    }))
  ));

  assert.equal(comparisonReadiness(cases, profiles, cohort, true).ready, true);
  assert.equal(comparisonReadiness(cases, profiles, cohort, false).ready, false);
  const unevenTrials = cohort.filter(row =>
    !(row.profile === "two" && row.case_id === "e" && row.trial_number === 3)
  );
  assert.ok(
    comparisonReadiness(cases, profiles, unevenTrials, true).missing.includes(
      "identical completed trial counts"
    )
  );
  const missingPi = cohort.map(row => ({ ...row, pi_version: null }));
  assert.ok(
    comparisonReadiness(cases, profiles, missingPi, true).missing.includes("one Pi version")
  );
});
