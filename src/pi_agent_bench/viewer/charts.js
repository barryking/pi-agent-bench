    function setupCanvas(id) {
      const canvas = $(id);
      const rect = canvas.parentElement.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, rect.width, rect.height);
      return { canvas, ctx, width: rect.width, height: rect.height };
    }

    function axes(ctx, width, height, bounds, formatX, formatY) {
      const c = colors();
      const pad = { left: 62, right: 24, top: 18, bottom: 43 };
      const plotW = width - pad.left - pad.right;
      const plotH = height - pad.top - pad.bottom;
      const x = value => pad.left + ((value - bounds.minX) / (bounds.maxX - bounds.minX || 1)) * plotW;
      const y = value => pad.top + (1 - (value - bounds.minY) / (bounds.maxY - bounds.minY || 1)) * plotH;
      ctx.strokeStyle = c.line;
      ctx.fillStyle = c.muted;
      ctx.lineWidth = 1;
      ctx.font = "11px ui-monospace, monospace";
      for (let i = 0; i <= 4; i++) {
        const value = bounds.minY + (bounds.maxY - bounds.minY) * i / 4;
        const py = y(value);
        ctx.beginPath(); ctx.moveTo(pad.left, py); ctx.lineTo(width - pad.right, py); ctx.stroke();
        ctx.textAlign = "right"; ctx.fillText(formatY(value), pad.left - 9, py + 4);
      }
      ctx.textAlign = "center";
      for (let i = 0; i <= 3; i++) {
        const value = bounds.minX + (bounds.maxX - bounds.minX) * i / 3;
        ctx.fillText(formatX(value), x(value), height - 14);
      }
      return { x, y, pad };
    }

    function renderPareto() {
      const chart = setupCanvas("pareto");
      const usable = state.summaries.filter(item => item.quality !== null && item.wallAll !== null);
      if (!usable.length) return drawEmpty(chart, "Quality and duration data are required.");
      const maxWall = Math.max(...usable.map(item => item.wallAll));
      const maxCost = Math.max(...usable
        .filter(item => item.costCoverage !== "unavailable")
        .map(item => item.cost || 0), 0);
      const scale = axes(
        chart.ctx, chart.width, chart.height,
        { minX: 0, maxX: maxWall * 1.12 || 1, minY: 0, maxY: 1 },
        value => `${formatNumber(value)}s`,
        value => `${formatNumber(value * 100)}%`
      );
      state.points.pareto = usable.map((item, index) => {
        const radius = item.costCoverage === "unavailable"
          ? 8
          : Math.max(5, maxCost ? Math.sqrt((item.cost || 0) / maxCost) * 22 : 5);
        const point = {
          x: scale.x(item.wallAll),
          y: scale.y(item.quality),
          r: radius,
          item
        };
        const color = palette[index % palette.length];
        chart.ctx.setLineDash(item.costCoverage === "partial" ? [4, 3] : []);
        chart.ctx.lineWidth = 2;
        chart.ctx.strokeStyle = color;
        chart.ctx.fillStyle = item.costCoverage === "unavailable" ? "transparent" : `${color}99`;
        chart.ctx.beginPath(); chart.ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
        chart.ctx.fill(); chart.ctx.stroke();
        chart.ctx.setLineDash([]);
        chart.ctx.fillStyle = colors().text;
        chart.ctx.textAlign = "left";
        chart.ctx.font = "12px system-ui";
        chart.ctx.fillText(item.profile, point.x + radius + 5, point.y + 4);
        return point;
      });
      $("pareto-legend").innerHTML = `
        <span class="legend-item"><span class="bubble-key bubble-small"></span>lower reported cost</span>
        <span class="legend-item"><span class="bubble-key bubble-large"></span>higher reported cost</span>
        <span class="legend-item"><span class="bubble-key bubble-partial"></span>partial cost</span>
        <span class="legend-item"><span class="bubble-key bubble-unavailable"></span>cost unavailable</span>
        <span class="legend-item">A point directly above another has better quality at roughly the same time. A similarly positioned but smaller bubble achieves the same outcome at lower cost.</span>`;
      bindTooltip("pareto", "pareto-tip", point =>
        `<strong>${escapeHtml(point.item.profile)}</strong>` +
        `${formatMetric(point.item.quality, "ratio")} quality · ${formatMetric(point.item.wallAll, "seconds")} median wall time<br>` +
        `${escapeHtml(formatMetric(point.item.cost, point.item.costUnit))} summed run cost · ${escapeHtml(point.item.costCoverage)} coverage<br>` +
        `Configured: ${escapeHtml(point.item.modelResources)}; default: ${escapeHtml(point.item.defaultResource)}<br>` +
        `Observed: ${escapeHtml(point.item.observedModels)}`
      );
    }

    function renderTokenSuccess() {
      const chart = setupCanvas("token-success");
      const usable = state.summaries.filter(item =>
        item.success !== null && item.tokensPerSuccess !== null
      );
      if (!usable.length) return drawEmpty(chart, "Successful tasks with token telemetry are required.");
      const maxTokens = Math.max(...usable.map(item => item.tokensPerSuccess));
      const scale = axes(
        chart.ctx, chart.width, chart.height,
        { minX: 0, maxX: maxTokens * 1.12 || 1, minY: 0, maxY: 1 },
        value => formatCompactTokens(value),
        value => `${formatNumber(value * 100)}%`
      );
      state.points["token-success"] = usable.map((item, index) => {
        const point = {
          x: scale.x(item.tokensPerSuccess),
          y: scale.y(item.success),
          item
        };
        chart.ctx.fillStyle = palette[index % palette.length];
        chart.ctx.beginPath(); chart.ctx.arc(point.x, point.y, 6, 0, Math.PI * 2); chart.ctx.fill();
        chart.ctx.fillStyle = colors().text;
        chart.ctx.textAlign = "left";
        chart.ctx.font = "12px system-ui";
        chart.ctx.fillText(item.profile, point.x + 9, point.y + 4);
        return point;
      });
      $("token-success-legend").innerHTML =
        `<span class="legend-item">x-axis is median input + output tokens among successful attempts; failed attempts still affect success rate.</span>`;
      bindTooltip("token-success", "token-success-tip", point =>
        `<strong>${escapeHtml(point.item.profile)}</strong>${formatMetric(point.item.success, "ratio")} success · ${formatMetric(point.item.tokensPerSuccess, "tokens")} median tokens per success`
      );
    }

    function renderComparison() {
      const metric = $("metric").value;
      $("comparison-title").textContent = `${label(metric)} across profiles`;
      const chart = setupCanvas("comparison");
      const groups = state.summaries.map(summary => {
        const rows = state.cohort.filter(row => row.profile === summary.profile && row.metric === metric);
        const values = caseMeans(rows);
        const interval = metricInterval(rows, metric);
        return { profile: summary.profile, values, mean: macroMean(rows), interval, unit: rows[0]?.unit };
      }).filter(group => group.mean !== null);
      if (!groups.length) return drawEmpty(chart, "This provider did not report the selected metric.");
      const unit = groups[0].unit;
      let min = Math.min(...groups.map(group => group.interval.low));
      let max = Math.max(...groups.map(group => group.interval.high));
      if (unit === "ratio") { min = 0; max = 1; }
      else if (min === max) { min = Math.min(0, min * .9); max = max * 1.1 || 1; }
      const pad = { left: 125, right: 35, top: 28, bottom: 42 };
      const plotW = chart.width - pad.left - pad.right;
      const x = value => pad.left + ((value - min) / (max - min || 1)) * plotW;
      const c = colors();
      chart.ctx.strokeStyle = c.line;
      chart.ctx.fillStyle = c.muted;
      chart.ctx.font = "11px ui-monospace, monospace";
      chart.ctx.textAlign = "center";
      for (let i = 0; i <= 4; i++) {
        const value = min + (max - min) * i / 4;
        const px = x(value);
        chart.ctx.beginPath(); chart.ctx.moveTo(px, pad.top); chart.ctx.lineTo(px, chart.height - pad.bottom); chart.ctx.stroke();
        chart.ctx.fillText(formatMetric(value, unit), px, chart.height - 15);
      }
      state.points.comparison = groups.map((group, index) => {
        const y = pad.top + (index + .5) * ((chart.height - pad.top - pad.bottom) / groups.length);
        chart.ctx.fillStyle = c.text;
        chart.ctx.textAlign = "right";
        chart.ctx.font = "12px system-ui";
        chart.ctx.fillText(group.profile, pad.left - 12, y + 4);
        chart.ctx.strokeStyle = palette[index % palette.length];
        chart.ctx.lineWidth = 2;
        chart.ctx.beginPath(); chart.ctx.moveTo(x(group.interval.low), y); chart.ctx.lineTo(x(group.interval.high), y); chart.ctx.stroke();
        chart.ctx.beginPath(); chart.ctx.moveTo(x(group.interval.low), y - 5); chart.ctx.lineTo(x(group.interval.low), y + 5); chart.ctx.stroke();
        chart.ctx.beginPath(); chart.ctx.moveTo(x(group.interval.high), y - 5); chart.ctx.lineTo(x(group.interval.high), y + 5); chart.ctx.stroke();
        chart.ctx.fillStyle = palette[index % palette.length];
        chart.ctx.beginPath(); chart.ctx.arc(x(group.mean), y, 6, 0, Math.PI * 2); chart.ctx.fill();
        return { x: x(group.mean), y, group };
      });
      bindTooltip("comparison", "comparison-tip", point =>
        `<strong>${escapeHtml(point.group.profile)}</strong>${formatMetric(point.group.mean, point.group.unit)} case-balanced mean · ${point.group.values.length} cases · ${escapeHtml(point.group.interval.method)} interval`
      );
    }

    function renderCoverage() {
      const profiles = unique(state.rawCohort.map(row => row.profile));
      const cases = unique(metricRows(state.rawCohort, "quality.score").map(row => row.case_id));
      $("coverage-head").innerHTML =
        `<th>Benchmark case</th>${profiles.map(profile => `<th>${escapeHtml(profile)}</th>`).join("")}`;
      const qualityRows = metricRows(state.rawCohort, "quality.score");
      const counts = cases.flatMap(caseId => profiles.map(profile =>
        qualityRows.filter(row => row.case_id === caseId && row.profile === profile).length
      ));
      const maxCount = counts.length ? Math.max(...counts) : 0;
      const uniformCoverage = state.sameCoverage &&
        counts.length > 0 &&
        counts.every(count => count === counts[0] && count > 0);
      $("coverage-body").innerHTML = cases.map(caseId => {
        return `<tr><td class="model">${escapeHtml(caseId)}</td>${profiles.map(profile => {
          const count = qualityRows.filter(
            row => row.case_id === caseId && row.profile === profile
          ).length;
          const coverageClass = count === 0
            ? " coverage-missing"
            : (count < maxCount ? " coverage-uneven" : "");
          return `<td class="number${coverageClass}">${count || "—"}</td>`;
        }).join("")}</tr>`;
      }).join("");
      $("coverage-label").textContent = uniformCoverage
        ? `Complete · ${cases.length} cases · ${counts[0]} trials per profile`
        : state.sameCoverage
          ? `Uneven trials · ${cases.length} cases across ${profiles.length} profiles`
          : `Incomplete · ${state.commonCases.length}/${cases.length} cases shared`;
      if (!uniformCoverage) $("coverage-details").open = true;
    }

    function renderTrend() {
      const metric = $("metric").value;
      const selectedCase = $("trend-case").value;
      const rows = state.cohort.filter(row => row.metric === metric && row.case_id === selectedCase)
        .sort((a, b) => a._time - b._time || a._index - b._index);
      const chart = setupCanvas("trend");
      if (!rows.length) return drawEmpty(chart, "No observations for this case and metric.");
      const unit = rows[0].unit;
      const times = rows.map(row => row._time);
      const values = rows.map(row => row.value);
      let minX = Math.min(...times), maxX = Math.max(...times);
      if (minX === maxX) { minX -= 60000; maxX += 60000; }
      let minY = Math.min(...values), maxY = Math.max(...values);
      if (unit === "ratio") { minY = 0; maxY = 1; }
      else {
        const gap = Math.max((maxY - minY) * .12, Math.abs(maxY || 1) * .06);
        minY = Math.max(0, minY - gap); maxY += gap;
      }
      const scale = axes(
        chart.ctx, chart.width, chart.height,
        { minX, maxX, minY, maxY },
        value => formatAxisTime(value, maxX - minX),
        value => formatMetric(value, unit)
      );
      const profiles = unique(rows.map(row => row.profile));
      state.points.trend = [];
      profiles.forEach((profile, index) => {
        const profileRows = rows.filter(row => row.profile === profile);
        const color = palette[index % palette.length];
        chart.ctx.strokeStyle = color;
        chart.ctx.fillStyle = color;
        chart.ctx.lineWidth = 2;
        chart.ctx.beginPath();
        profileRows.forEach((row, pointIndex) => {
          const px = scale.x(row._time), py = scale.y(row.value);
          pointIndex ? chart.ctx.lineTo(px, py) : chart.ctx.moveTo(px, py);
        });
        chart.ctx.stroke();
        profileRows.forEach(row => {
          const point = { x: scale.x(row._time), y: scale.y(row.value), row };
          chart.ctx.beginPath(); chart.ctx.arc(point.x, point.y, 5, 0, Math.PI * 2); chart.ctx.fill();
          state.points.trend.push(point);
        });
      });
      $("trend-legend").innerHTML = profiles.map((profile, index) =>
        `<span class="legend-item"><span class="swatch" style="background:${palette[index % palette.length]}"></span>${escapeHtml(profile)}</span>`
      ).join("");
      bindTooltip("trend", "trend-tip", point =>
        `<strong>${escapeHtml(point.row.profile)}</strong>${formatMetric(point.row.value, point.row.unit)} · ${escapeHtml(formatDateTime(point.row.started_at))}`
      );
    }

    function renderDetails() {
      const metric = $("metric").value;
      const rows = state.cohort.filter(row => row.metric === metric)
        .sort((a, b) => b._time - a._time || b._index - a._index);
      $("row-count").textContent = `${rows.length} observations`;
      $("details").innerHTML = rows.slice(0, 500).map(row => `
        <tr>
          <td>${escapeHtml(row.started_at ? formatDateTime(row.started_at) : "—")}</td>
          <td>${escapeHtml(row.profile || "—")}</td>
          <td>${escapeHtml(row.case_id || "—")}</td>
          <td class="number">${escapeHtml(String(row.trial_number ?? "—"))}</td>
          <td>${escapeHtml(label(row.metric))}</td>
          <td class="number">${escapeHtml(formatMetric(row.value, row.unit))}</td>
          <td class="number">${escapeHtml((row.benchmark_id || row.run_id || "—").slice(0, 12))}</td>
          <td class="number">${escapeHtml((row.cohort_fingerprint || "—").slice(0, 12))}</td>
        </tr>`).join("");
    }
