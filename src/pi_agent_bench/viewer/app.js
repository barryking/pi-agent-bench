    ["dataset", "run_name"].forEach(id => $(id).addEventListener("change", () => { refreshCohortControls(); render(); }));
    ["cache", "metric", "trend-case", "baseline", "common-only"].forEach(id => $(id).addEventListener("change", render));
    $("file").addEventListener("change", async event => {
      const file = event.target.files[0];
      if (!file) return;
      try {
        setData(parseJsonl(await file.text()));
        $("status").textContent = `${file.name} · ${unique(state.all.map(sampleKey)).length} samples`;
        $("status").classList.remove("error");
      } catch (error) {
        $("status").textContent = error.message;
        $("status").classList.add("error");
      }
    });
    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        renderPareto(); renderComparison(); renderTrend();
      }, 100);
    });
    loadDefault().catch(error => {
      $("status").textContent = error.message;
      $("status").classList.add("error");
    });
