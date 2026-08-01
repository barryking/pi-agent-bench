    function sampleKey(row) {
      return `${row.run_id}::${row.case_id}::${row.trial_number}`;
    }

    function campaignKey(row) {
      return row.benchmark_id || row.run_name || row.run_id || "legacy-campaign";
    }

    function successfulMetricValues(rows, metric) {
      const successfulSamples = new Set(
        rows
          .filter(row => row.metric === "quality.success" && row.value === 1)
          .map(sampleKey)
      );
      return rows
        .filter(row => row.metric === metric && successfulSamples.has(sampleKey(row)))
        .map(row => row.value);
    }

    function selectComparisonRows(
      rows,
      { datasetVersion, cohortFingerprint, runName, cacheState }
    ) {
      return rows.filter(row =>
        row.dataset_version === datasetVersion &&
        row.cohort_fingerprint === cohortFingerprint &&
        (!runName || runName === "__all_runs__" || row.run_name === runName) &&
        row.cache_state === cacheState
      );
    }

    function comparisonReadiness(cases, profiles, cohort, sameCoverage) {
      const distinct = values => [...new Set(values.filter(
        value => value !== null && value !== undefined && value !== ""
      ))];
      const quality = cohort.filter(row => row.metric === "quality.score");
      const counts = profiles.flatMap(profile => cases.map(caseId =>
        quality.filter(row => row.profile === profile && row.case_id === caseId).length
      ));
      const minimumTrials = counts.length ? Math.min(...counts) : 0;
      const missing = [];
      if (profiles.length < 2) missing.push(`${2 - profiles.length} more setup`);
      if (cases.length < 5) missing.push(`${5 - cases.length} more shared case`);
      if (minimumTrials < 3) {
        missing.push(`${3 - minimumTrials} more trial per setup/case`);
      }
      if (!sameCoverage) missing.push("identical case coverage");
      if (counts.length && !counts.every(count => count === counts[0])) {
        missing.push("identical completed trial counts");
      }
      if (distinct(cohort.map(row => row.cohort_fingerprint)).length !== 1) {
        missing.push("one generated cohort fingerprint");
      }
      if (distinct(cohort.map(row => row.scoring_method)).length !== 1) {
        missing.push("one scoring method");
      }
      [
        ["sandbox_image_id", "one sandbox image"],
        ["inspect_version", "one Inspect version"],
        ["pi_version", "one Pi version"]
      ].forEach(([field, message]) => {
        if (distinct(cohort.map(row => row[field])).length !== 1) missing.push(message);
      });
      return {
        ready: missing.length === 0,
        exploratory: cases.length < 10 || minimumTrials < 5,
        missing,
        minimumTrials
      };
    }

    function wilsonInterval(values, z = 1.96) {
      if (!values.length) return { low: null, high: null, method: "wilson" };
      const successes = values.reduce((sum, value) => sum + (value >= 1 ? 1 : 0), 0);
      const n = values.length;
      const proportion = successes / n;
      const denominator = 1 + (z * z) / n;
      const centre = (proportion + (z * z) / (2 * n)) / denominator;
      const margin = z * Math.sqrt(
        (proportion * (1 - proportion) / n) + ((z * z) / (4 * n * n))
      ) / denominator;
      return {
        low: Math.max(0, centre - margin),
        high: Math.min(1, centre + margin),
        method: "Wilson"
      };
    }

    function caseBootstrapInterval(rows, samples = 2000) {
      const grouped = new Map();
      rows.forEach(row => {
        if (!grouped.has(row.case_id)) grouped.set(row.case_id, []);
        grouped.get(row.case_id).push(row.value);
      });
      const values = [...grouped.values()].map(mean);
      const average = mean(values);
      if (values.length < 2) {
        return { low: average, high: average, method: "case bootstrap" };
      }
      const random = seededRandom(values);
      const estimates = [];
      for (let sample = 0; sample < samples; sample++) {
        let total = 0;
        for (let index = 0; index < values.length; index++) {
          total += values[Math.floor(random() * values.length)];
        }
        estimates.push(total / values.length);
      }
      estimates.sort((a, b) => a - b);
      return {
        low: percentile(estimates, 0.025),
        high: percentile(estimates, 0.975),
        method: "case bootstrap"
      };
    }

    function metricInterval(rows, metric) {
      if (!rows.length) return { low: null, high: null, method: "unavailable" };
      if (metric === "quality.success") {
        return wilsonInterval(rows.map(row => row.value));
      }
      return caseBootstrapInterval(rows);
    }

    function matchedQualityDelta(rows, profile, baseline) {
      if (!baseline || profile === baseline) {
        return { mean: 0, low: 0, high: 0, matches: 0, method: "baseline" };
      }
      const quality = rows.filter(row => row.metric === "quality.score");
      const key = row =>
        `${campaignKey(row)}::${row.case_id}::${row.trial_number}`;
      const baselineValues = new Map(
        quality.filter(row => row.profile === baseline).map(row => [key(row), row.value])
      );
      const differences = quality
        .filter(row => row.profile === profile && baselineValues.has(key(row)))
        .map(row => ({
          case_id: row.case_id,
          benchmark_id: campaignKey(row),
          value: row.value - baselineValues.get(key(row))
        }));
      if (!differences.length) return null;
      const interval = caseBootstrapInterval(differences);
      return {
        mean: mean(caseMeans(differences)),
        low: interval.low,
        high: interval.high,
        matches: differences.length,
        method: "case bootstrap over matched repetitions"
      };
    }

    function repetitionRanks(rows, selectedProfile) {
      const quality = metricRows(rows, "quality.score");
      const repetitions = unique(quality.map(row =>
        `${campaignKey(row)}::${row.trial_number}`
      ));
      return repetitions.map(repetition => {
        const ranked = unique(quality.map(row => row.profile)).map(profile => ({
          profile,
          quality: macroMean(quality.filter(row =>
            row.profile === profile &&
            `${campaignKey(row)}::${row.trial_number}` === repetition
          ))
        })).sort((a, b) => (b.quality ?? -Infinity) - (a.quality ?? -Infinity));
        return ranked.findIndex(item => item.profile === selectedProfile) + 1;
      }).filter(rank => rank > 0);
    }

    function caseMeans(rows) {
      const grouped = new Map();
      rows.forEach(row => {
        if (!grouped.has(row.case_id)) grouped.set(row.case_id, []);
        grouped.get(row.case_id).push(row.value);
      });
      return [...grouped.values()].map(mean);
    }

    function percentile(sortedValues, probability) {
      if (!sortedValues.length) return null;
      const index = Math.min(
        sortedValues.length - 1,
        Math.max(0, Math.floor(probability * sortedValues.length))
      );
      return sortedValues[index];
    }

    function seededRandom(values) {
      let state = values.reduce(
        (seed, value, index) => (seed ^ Math.round(value * 1000003) ^ (index * 2654435761)) >>> 0,
        2166136261
      );
      return () => {
        state = (1664525 * state + 1013904223) >>> 0;
        return state / 4294967296;
      };
    }

    function compactConfiguration(configurationJson) {
      try {
        const configuration = JSON.parse(configurationJson);
        return [
          configuration.quantisation || configuration.quantization,
          configuration.context_tokens || configuration.context_limit,
          configuration.model_revision || configuration.model_snapshot
        ].filter(Boolean).join(" · ") || "recorded";
      } catch {
        return "recorded";
      }
    }

    function formatDelta(delta) {
      if (!delta) return "—";
      const prefix = delta.mean > 0 ? "+" : "";
      return `${prefix}${formatNumber(delta.mean * 100)} pp [${formatNumber(delta.low * 100)}, ${formatNumber(delta.high * 100)}]`;
    }

    function formatCompactTokens(value) {
      if (value >= 1000000) return `${formatNumber(value / 1000000)}m`;
      if (value >= 1000) return `${formatNumber(value / 1000)}k`;
      return formatNumber(value);
    }

    function bindTooltip(canvasId, tipId, formatter) {
      const canvas = $(canvasId), tip = $(tipId);
      canvas.onmousemove = event => {
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left, y = event.clientY - rect.top;
        const point = (state.points[canvasId] || []).find(
          item => Math.hypot(item.x - x, item.y - y) < Math.max(14, (item.r || 0) + 5)
        );
        if (!point) { tip.style.display = "none"; return; }
        tip.innerHTML = formatter(point);
        tip.style.display = "block";
        tip.style.left = `${Math.min(rect.width - 230, Math.max(8, point.x + 12))}px`;
        tip.style.top = `${Math.max(8, point.y - 54)}px`;
      };
      canvas.onmouseleave = () => { tip.style.display = "none"; };
    }

    function drawEmpty(chart, message) {
      chart.ctx.fillStyle = colors().muted;
      chart.ctx.font = "14px system-ui";
      chart.ctx.textAlign = "center";
      chart.ctx.fillText(message, chart.width / 2, chart.height / 2);
    }

    function mean(values) {
      return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
    }
    function sumOrNull(values) {
      return values.length ? values.reduce((sum, value) => sum + value, 0) : null;
    }
    function median(values) {
      if (!values.length) return null;
      const sorted = [...values].sort((a, b) => a - b);
      const middle = Math.floor(sorted.length / 2);
      return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    }
    function formatMetric(value, unit) {
      if (value === null || value === undefined || Number.isNaN(value)) return "—";
      if (unit === "ratio") return `${formatNumber(value * 100)}%`;
      if (unit === "seconds") return `${formatNumber(value)}s`;
      if (unit === "tokens") return Math.round(value).toLocaleString();
      if (unit && unit.startsWith("currency")) return `${formatNumber(value)} ${unit === "currency-unspecified" ? "(currency unspecified)" : unit}`;
      if (/^[A-Z]{3}$/.test(unit || "")) return `${formatNumber(value)} ${unit}`;
      return formatNumber(value);
    }
    function formatNumber(value) {
      return new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(value);
    }
    function formatDateTime(value) {
      return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
    }
    function formatAxisTime(value, span) {
      const options = span < 86400000 ? { hour: "2-digit", minute: "2-digit" } : { month: "short", day: "numeric" };
      return new Intl.DateTimeFormat(undefined, options).format(new Date(value));
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      })[character]);
    }

    if (typeof module !== "undefined") {
      module.exports = {
        caseBootstrapInterval,
        caseMeans,
        comparisonReadiness,
        matchedQualityDelta,
        mean,
        metricInterval,
        percentile,
        sampleKey,
        selectComparisonRows,
        sumOrNull,
        successfulMetricValues,
        wilsonInterval
      };
    }
