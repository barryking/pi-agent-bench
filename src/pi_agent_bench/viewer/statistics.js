    function confidence(values, unit) {
      const average = mean(values);
      if (values.length < 2) return { low: average, high: average };
      const variance = values.reduce((sum, value) => sum + (value - average) ** 2, 0) / (values.length - 1);
      const margin = 1.96 * Math.sqrt(variance / values.length);
      return {
        low: unit === "ratio" ? Math.max(0, average - margin) : average - margin,
        high: unit === "ratio" ? Math.min(1, average + margin) : average + margin
      };
    }

    function caseMeans(rows) {
      const grouped = new Map();
      rows.forEach(row => {
        if (!grouped.has(row.case_id)) grouped.set(row.case_id, []);
        grouped.get(row.case_id).push(row.value);
      });
      return [...grouped.values()].map(mean);
    }

    function pairedQualityDelta(rows, profile, baseline) {
      if (!baseline || profile === baseline) return { mean: 0, low: 0, high: 0, pairs: 0 };
      const quality = metricRows(rows, "quality.score");
      const key = row => `${row.case_id}::${row.trial_number}`;
      const baselineValues = new Map(
        quality.filter(row => row.profile === baseline).map(row => [key(row), row.value])
      );
      const differences = quality
        .filter(row => row.profile === profile && baselineValues.has(key(row)))
        .map(row => row.value - baselineValues.get(key(row)));
      if (!differences.length) return null;
      const interval = confidence(differences, "delta");
      return { mean: mean(differences), ...interval, pairs: differences.length };
    }

    function trialRanks(rows, selectedProfile) {
      const quality = metricRows(rows, "quality.score");
      const trials = unique(quality.map(row => row.trial_number));
      return trials.map(trial => {
        const ranked = unique(quality.map(row => row.profile)).map(profile => ({
          profile,
          quality: macroMean(quality.filter(row =>
            row.profile === profile && row.trial_number === trial
          ))
        })).sort((a, b) => (b.quality ?? -Infinity) - (a.quality ?? -Infinity));
        return ranked.findIndex(item => item.profile === selectedProfile) + 1;
      }).filter(rank => rank > 0);
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
        const point = (state.points[canvasId] || []).find(item => Math.hypot(item.x - x, item.y - y) < 14);
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
