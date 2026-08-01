    const palette = ["#7ee095", "#7db9ff", "#ffca70", "#d59cff", "#ff817b", "#68e2da"];
    const ALL_RUNS = "__all_runs__";
    const friendly = {
      "quality.success": "Success rate",
      "quality.score": "Quality score",
      "time.wall": "Total wall time",
      "time.inspect_working": "Inspect working time",
      "time.model_working": "Model working time",
      "time.tool_working": "Tool working time",
      "time.pi": "Pi execution time",
      "speed.observed_output_tokens_per_model_second": "Observed output tokens per model second",
      "tokens.input": "Input tokens",
      "tokens.cache_write": "Cache-write tokens",
      "tokens.cached_input": "Cached input tokens",
      "tokens.reasoning": "Reasoning tokens",
      "tokens.output": "Output tokens",
      "tokens.total": "Total tokens",
      "cost.provider_reported": "Provider-reported cost",
      "agent.turns": "Agent turns",
      "agent.tool_calls": "Tool calls",
      "agent.failed_tool_calls": "Failed tool calls",
      "agent.retries": "Retries",
      "agent.compactions": "Compactions"
    };
    const state = {
      all: [],
      rawCohort: [],
      cohort: [],
      commonCases: [],
      unionCases: [],
      sameCoverage: false,
      rankingReady: false,
      summaries: [],
      points: {}
    };
    const $ = id => document.getElementById(id);
    const unique = values => [...new Set(values.filter(value => value !== null && value !== undefined && value !== ""))].sort();
    const label = metric => friendly[metric] || metric.replaceAll(".", " · ").replaceAll("_", " ");
    const colors = () => ({
      line: getComputedStyle(document.documentElement).getPropertyValue("--line").trim(),
      muted: getComputedStyle(document.documentElement).getPropertyValue("--muted").trim(),
      text: getComputedStyle(document.documentElement).getPropertyValue("--text").trim()
    });

    function parseJsonl(text) {
      return text.split(/\r?\n/).filter(Boolean).map((line, index) => {
        try { return normaliseMetricRow(JSON.parse(line)); }
        catch (error) { throw new Error(`Invalid JSON on line ${index + 1}: ${error.message}`); }
      }).filter(row => typeof row.value === "number");
    }

    function normaliseMetricRow(row) {
      if (row.schema_version !== 1) return row;
      const observed = row.model
        ? [{ provider: row.provider, model: row.model, execution: "legacy" }]
        : [];
      return {
        ...row,
        run_name: row.run_name || row.campaign || "default",
        benchmark_id:
          row.benchmark_id || row.campaign_id || row.campaign || row.run_name ||
          "legacy-campaign",
        cohort_fingerprint:
          row.cohort_fingerprint || row.benchmark_fingerprint || "legacy-cohort",
        sandbox_image_id: row.sandbox_image_id || row.sandbox_image,
        harness_source_fingerprint:
          row.harness_source_fingerprint || row.benchmark_fingerprint,
        pi_profile: row.pi_profile || row.agent_profile || "legacy-profile",
        model_resources: row.model_resources || row.model || "unreported",
        default_model_resource:
          row.default_model_resource || row.model || "unreported",
        agent_profile_fingerprint:
          row.agent_profile_fingerprint || row.configuration_fingerprint,
        agent_profile_json:
          row.agent_profile_json || row.configuration_json || "",
        observed_models_json:
          row.observed_models_json || JSON.stringify(observed),
        cost_coverage: row.cost_coverage || "complete"
      };
    }

    async function loadDefault() {
      const response = await fetch("/metrics.jsonl", { cache: "no-store" });
      if (!response.ok) throw new Error(`Could not load metrics.jsonl (${response.status})`);
      setData(parseJsonl(await response.text()));
    }

    function optionHtml(value, text = value) {
      return `<option value="${escapeHtml(value)}">${escapeHtml(text)}</option>`;
    }

    function setOptions(id, values, preferred) {
      const control = $(id);
      const previous = control.value;
      control.innerHTML = values.map(value => optionHtml(value)).join("");
      control.value = values.includes(preferred) ? preferred :
        values.includes(previous) ? previous : (values[0] || "");
    }

    function setData(rows) {
      state.all = rows.map((row, index) => ({
        ...row,
        _index: index,
        _time: row.started_at ? new Date(row.started_at).getTime() : index
      }));
      refreshCohortControls();
      const metrics = unique(state.all.map(row => row.metric));
      const metricOptions = metrics.map(metric => optionHtml(metric, label(metric))).join("");
      const initialMetric = metrics.includes("quality.score") ? "quality.score" : metrics[0];
      $("metric").innerHTML = metricOptions;
      $("metric").value = initialMetric;
      $("status").textContent = `${unique(state.all.map(sampleKey)).length} samples loaded`;
      render();
    }

    function refreshCohortControls() {
      setOptions("dataset", unique(state.all.map(row => row.dataset_version)));
      const versionRows = state.all.filter(row => row.dataset_version === $("dataset").value);
      setOptions("cohort", unique(versionRows.map(row => row.cohort_fingerprint)));
      const cohortRows = versionRows.filter(
        row => row.cohort_fingerprint === $("cohort").value
      );
      const runNames = unique(cohortRows.map(row => row.run_name));
      const previousRun = $("run_name").value;
      $("run_name").innerHTML = [
        optionHtml(ALL_RUNS, "All runs"),
        ...runNames.map(value => optionHtml(value))
      ].join("");
      $("run_name").value = runNames.includes(previousRun) ? previousRun : ALL_RUNS;
      const runRows = $("run_name").value === ALL_RUNS
        ? cohortRows
        : cohortRows.filter(row => row.run_name === $("run_name").value);
      setOptions("cache", unique(runRows.map(row => row.cache_state)), "unspecified");
    }

    function render() {
      state.rawCohort = selectComparisonRows(state.all, {
        datasetVersion: $("dataset").value,
        cohortFingerprint: $("cohort").value,
        runName: $("run_name").value,
        cacheState: $("cache").value
      });
      const profiles = unique(state.rawCohort.map(row => row.profile));
      setOptions("baseline", profiles, $("baseline").value || profiles[0]);
      const profileCases = profiles.map(profile =>
        unique(metricRows(
          state.rawCohort.filter(row => row.profile === profile),
          "quality.score"
        ).map(row => row.case_id))
      );
      state.commonCases = profileCases.length
        ? profileCases.reduce((common, cases) => common.filter(item => cases.includes(item)))
        : [];
      state.unionCases = unique(profileCases.flat());
      state.sameCoverage = profileCases.length > 0 &&
        profileCases.every(cases =>
          cases.length === profileCases[0].length &&
          cases.every(item => profileCases[0].includes(item))
        );
      const useCommon = $("common-only").checked;
      state.cohort = useCommon
        ? state.rawCohort.filter(row => state.commonCases.includes(row.case_id))
        : state.rawCohort;
      const cases = unique(state.cohort.map(row => row.case_id));
      setOptions("trend-case", cases, $("trend-case").value);
      state.rankingReady = comparisonReadiness(
        cases,
        profiles,
        state.cohort,
        state.sameCoverage
      ).ready;
      state.summaries = buildSummaries(state.cohort);
      renderNotice(cases, profiles);
      renderLeaderboard();
      renderPareto();
      renderTokenSuccess();
      renderComparison();
      renderTrend();
      renderCoverage();
      renderDetails();
      $("cohort-label").textContent =
        `outcomes · dataset ${$("dataset").value} · cohort ${$("cohort").value.slice(0, 12)} · ${$("run_name").selectedOptions[0]?.textContent || "all runs"} · ${$("cache").value} cache`;
    }

    function buildSummaries(rows) {
      const profiles = unique(rows.map(row => row.profile));
      const baseline = $("baseline").value;
      const summaries = profiles.map(profile => {
        const profileRows = rows.filter(row => row.profile === profile);
        const success = metricRows(profileRows, "quality.success");
        const quality = metricRows(profileRows, "quality.score");
        const successfulWall = successfulMetricValues(profileRows, "time.wall");
        const costRows = metricRows(profileRows, "cost.provider_reported");
        const successfulTokens = successfulMetricValues(profileRows, "tokens.total");
        const delta = matchedQualityDelta(rows, profile, baseline);
        const ranks = repetitionRanks(rows, profile);
        const profileJson = profileRows.find(row => row.agent_profile_json)?.agent_profile_json;
        const modelResources =
          profileRows.find(row => row.model_resources)?.model_resources || "unreported";
        const piProfile =
          profileRows.find(row => row.pi_profile)?.pi_profile || "unreported";
        const defaultResource =
          profileRows.find(row => row.default_model_resource)?.default_model_resource || "unreported";
        const observedModelsJson =
          profileRows.find(row => row.observed_models_json)?.observed_models_json || "[]";
        const coverageStates = unique(profileRows.map(row => row.cost_coverage));
        const costCoverage = coverageStates.length === 1
          ? coverageStates[0]
          : (coverageStates.every(value => value === "unavailable") ? "unavailable" : "partial");
        return {
          profile,
          piProfile,
          modelResources,
          defaultResource,
          observedModels: compactObservedModels(observedModelsJson),
          configuration: profileJson ? "composed profile recorded" : "unreported",
          agentConfigurationFingerprint:
            profileRows.find(row => row.agent_profile_fingerprint)
              ?.agent_profile_fingerprint,
          cases: unique(quality.map(row => row.case_id)).length,
          rawCases: unique(metricRows(
            state.rawCohort.filter(row => row.profile === profile),
            "quality.score"
          ).map(row => row.case_id)).length,
          samples: unique(quality.map(sampleKey)).length,
          trialsPerCase: quality.length
            ? quality.length / unique(quality.map(row => row.case_id)).length
            : null,
          success: macroMean(success),
          quality: macroMean(quality),
          wall: median(successfulWall),
          wallAll: median(metricRows(profileRows, "time.wall").map(row => row.value)),
          input: mean(metricRows(profileRows, "tokens.input").map(row => row.value)),
          output: mean(metricRows(profileRows, "tokens.output").map(row => row.value)),
          tokensPerSuccess: median(successfulTokens),
          observedTokensPerSecond: median(metricRows(
            profileRows,
            "speed.observed_output_tokens_per_model_second"
          ).map(row => row.value)),
          cost: costRows.reduce((total, row) => total + row.value, 0),
          costCoverage,
          costUnit: costRows[0]?.unit || "cost",
          delta,
          rankRange: ranks.length ? `${Math.min(...ranks)}–${Math.max(...ranks)}` : "—"
        };
      });
      return state.rankingReady
        ? summaries.sort((a, b) =>
            ((b.quality ?? -Infinity) - (a.quality ?? -Infinity))
            || ((a.wallAll ?? Infinity) - (b.wallAll ?? Infinity))
          )
        : summaries.sort((a, b) => a.profile.localeCompare(b.profile));
    }

    function metricRows(rows, metric) {
      return rows.filter(row => row.metric === metric);
    }

    function macroMean(rows) {
      if (!rows.length) return null;
      const cases = new Map();
      rows.forEach(row => {
        if (!cases.has(row.case_id)) cases.set(row.case_id, []);
        cases.get(row.case_id).push(row.value);
      });
      return mean([...cases.values()].map(mean));
    }

    function compactObservedModels(value) {
      try {
        const models = JSON.parse(value);
        if (!Array.isArray(models) || !models.length) return "unavailable";
        return models.map(item =>
          `${item.provider ? `${item.provider}/` : ""}${item.model || "unknown"} (${item.execution || "unknown"})`
        ).join(", ");
      } catch {
        return "unavailable";
      }
    }

    function renderNotice(cases, profileNames) {
      const profiles = profileNames.length;
      const attempts = unique(
        metricRows(state.cohort, "quality.score").map(sampleKey)
      ).length;
      const fingerprints = unique(state.cohort.map(row => row.cohort_fingerprint));
      const synthetic = state.cohort.some(row => row.synthetic === true);
      const readiness = comparisonReadiness(
        cases,
        profileNames,
        state.cohort,
        state.sameCoverage
      );
      $("data-badge").textContent = synthetic
        ? "SYNTHETIC CASES"
        : (readiness.ready
            ? (readiness.exploratory ? "COMPARABLE · EXPLORATORY" : "COMPARABLE")
            : "INSUFFICIENT EVIDENCE");
      $("data-notice").textContent = synthetic
        ? `${profiles} setups across ${cases.length} shared example cases and ${attempts} real attempts. These results compare the setups, but example code may not represent your work.`
        : readiness.ready
          ? `${profiles} setups, ${cases.length} identical cases and at least ${readiness.minimumTrials} trials per setup/case. Ranking is enabled.${readiness.exploratory ? " Uncertainty is exploratory until there are at least 10 cases and 5 trials per setup/case." : ""}`
          : `Ranking is disabled: needs ${readiness.missing.join(", ")}.`;
      if (synthetic && !readiness.ready) {
        $("data-notice").textContent += ` Ranking disabled: needs ${readiness.missing.join(", ")}.`;
      } else if (synthetic && readiness.ready) {
        $("data-notice").textContent += ` Ranking is enabled.${readiness.exploratory ? " Uncertainty is still exploratory." : ""}`;
      }
      if (!synthetic && fingerprints.length > 1) {
        $("data-badge").textContent = "MIXED BUILD";
        $("data-notice").textContent += ` ${fingerprints.length} cohort fingerprints are present; these profiles are not comparable.`;
      }
    }

    function renderLeaderboard() {
      $("leaderboard").innerHTML = state.summaries.length ? state.summaries.map((summary, index) => `
        <tr>
          <td class="number">${state.rankingReady ? index + 1 : "—"}</td>
          <td class="model">${escapeHtml(summary.profile)}</td>
          <td>${escapeHtml(summary.piProfile)}</td>
          <td>${escapeHtml(summary.modelResources)}</td>
          <td>${escapeHtml(summary.defaultResource)}</td>
          <td class="number">${summary.rawCases} / ${state.unionCases.length || summary.rawCases}</td>
          <td class="number">${formatNumber(summary.trialsPerCase)}</td>
          <td class="number">${escapeHtml(summary.rankRange)}</td>
          <td class="number">${formatMetric(summary.success, "ratio")}</td>
          <td class="number">${formatMetric(summary.quality, "ratio")}</td>
          <td class="number">${formatDelta(summary.delta)}</td>
          <td class="number">${formatMetric(summary.wall, "seconds")}</td>
          <td class="number">${formatMetric(summary.tokensPerSuccess, "tokens")}</td>
          <td class="number">${formatMetric(summary.observedTokensPerSecond, "tokens/second")}</td>
          <td class="number">${formatMetric(summary.cost, summary.costUnit)} · ${escapeHtml(summary.costCoverage)}</td>
          <td class="model">${escapeHtml(summary.observedModels)}</td>
          <td class="model">${escapeHtml(summary.configuration)}<small>agent ${escapeHtml((summary.agentConfigurationFingerprint || "unreported").slice(0, 12))}</small></td>
        </tr>`).join("") : `<tr><td colspan="17"><div class="empty">No comparable results in this cohort.</div></td></tr>`;
    }
