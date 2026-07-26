    const palette = ["#7ee095", "#7db9ff", "#ffca70", "#d59cff", "#ff817b", "#68e2da"];
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
        try { return JSON.parse(line); }
        catch (error) { throw new Error(`Invalid JSON on line ${index + 1}: ${error.message}`); }
      }).filter(row => typeof row.value === "number");
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
      $("metric").innerHTML = metrics.map(metric => optionHtml(metric, label(metric))).join("");
      $("metric").value = metrics.includes("quality.score") ? "quality.score" : metrics[0];
      $("status").textContent = `${unique(state.all.map(sampleKey)).length} samples loaded`;
      render();
    }

    function refreshCohortControls() {
      setOptions("dataset", unique(state.all.map(row => row.dataset_version)));
      const versionRows = state.all.filter(row => row.dataset_version === $("dataset").value);
      setOptions("run_name", unique(versionRows.map(row => row.run_name)), "default");
      const runRows = versionRows.filter(row => row.run_name === $("run_name").value);
      setOptions("cache", unique(runRows.map(row => row.cache_state)), "unspecified");
    }

    function render() {
      state.rawCohort = state.all.filter(row =>
        row.dataset_version === $("dataset").value &&
        row.run_name === $("run_name").value &&
        row.cache_state === $("cache").value
      );
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
        `outcomes · dataset ${$("dataset").value} · ${$("run_name").value} · ${$("cache").value} cache`;
    }

    function buildSummaries(rows) {
      const profiles = unique(rows.map(row => row.profile));
      const baseline = $("baseline").value;
      const summaries = profiles.map(profile => {
        const profileRows = rows.filter(row => row.profile === profile);
        const success = metricRows(profileRows, "quality.success");
        const quality = metricRows(profileRows, "quality.score");
        const successfulWall = successfulMetricValues(profileRows, "time.wall");
        const cost = successfulMetricValues(profileRows, "cost.provider_reported");
        const successfulTokens = successfulMetricValues(profileRows, "tokens.total");
        const delta = matchedQualityDelta(rows, profile, baseline);
        const ranks = repetitionRanks(rows, profile);
        const configuration = profileRows.find(row => row.configuration_json)?.configuration_json;
        const agentConfiguration =
          profileRows.find(row => row.agent_configuration_json)?.agent_configuration_json;
        const agentProfile =
          profileRows.find(row => row.agent_profile)?.agent_profile || "vanilla";
        return {
          profile,
          kind: profileRows.find(row => row.profile_kind)?.profile_kind || "unspecified",
          model: profileRows.find(row => row.model)?.model || "model identity unavailable",
          provider: profileRows.find(row => row.provider)?.provider || "unreported",
          configuration:
            `model: ${configuration ? compactConfiguration(configuration) : "unreported"}; ` +
            `agent (${agentProfile}): ${agentConfiguration ? compactConfiguration(agentConfiguration) : "unreported"}`,
          configurationFingerprint:
            profileRows.find(row => row.configuration_fingerprint)?.configuration_fingerprint,
          agentConfigurationFingerprint:
            profileRows.find(row => row.agent_configuration_fingerprint)
              ?.agent_configuration_fingerprint,
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
          costPerSuccess: mean(cost),
          costUnit: metricRows(profileRows, "cost.provider_reported")[0]?.unit || null,
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

    function renderNotice(cases, profileNames) {
      const profiles = profileNames.length;
      const attempts = unique(
        metricRows(state.cohort, "quality.score").map(sampleKey)
      ).length;
      const fingerprints = unique(state.cohort.map(row => row.benchmark_fingerprint));
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
        $("data-notice").textContent += ` ${fingerprints.length} benchmark fingerprints are present; interpret the time trend as a build comparison.`;
      }
    }

    function renderLeaderboard() {
      $("leaderboard").innerHTML = state.summaries.length ? state.summaries.map((summary, index) => `
        <tr>
          <td class="number">${state.rankingReady ? index + 1 : "—"}</td>
          <td class="model">${escapeHtml(summary.profile)}</td>
          <td>${escapeHtml(summary.model)}</td>
          <td>${escapeHtml(summary.kind)}</td>
          <td>${escapeHtml(summary.provider)}</td>
          <td class="number">${summary.rawCases} / ${state.unionCases.length || summary.rawCases}</td>
          <td class="number">${formatNumber(summary.trialsPerCase)}</td>
          <td class="number">${escapeHtml(summary.rankRange)}</td>
          <td class="number">${formatMetric(summary.success, "ratio")}</td>
          <td class="number">${formatMetric(summary.quality, "ratio")}</td>
          <td class="number">${formatDelta(summary.delta)}</td>
          <td class="number">${formatMetric(summary.wall, "seconds")}</td>
          <td class="number">${formatMetric(summary.tokensPerSuccess, "tokens")}</td>
          <td class="number">${formatMetric(summary.observedTokensPerSecond, "tokens/second")}</td>
          <td class="number">${formatMetric(summary.costPerSuccess, summary.costUnit)}</td>
          <td class="model">${escapeHtml(summary.configuration)}<small>model ${escapeHtml((summary.configurationFingerprint || "unreported").slice(0, 12))} · agent ${escapeHtml((summary.agentConfigurationFingerprint || "unreported").slice(0, 12))}</small></td>
        </tr>`).join("") : `<tr><td colspan="16"><div class="empty">No comparable results in this cohort.</div></td></tr>`;
    }
