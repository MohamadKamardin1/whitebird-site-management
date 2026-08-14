/* White Bird Zanzibar — dashboard chart rendering + nav toggle.
   Reads chart datasets injected via json_script and renders with Chart.js. */
(function () {
  "use strict";

  var palette = {
    primary: "#A47C00",
    accent: "#C9A227",
    success: "#2E7D32",
    warning: "#B26A00",
    danger: "#B3261E",
    text: "#6B5B33",
    grid: "rgba(107, 91, 51, 0.12)",
  };

  function dataset(label, data, color) {
    return {
      label: label,
      data: data,
      borderColor: color,
      backgroundColor: color,
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 2,
    };
  }

  function renderChart(canvas) {
    if (typeof Chart === "undefined") {
      canvas.textContent = "Charts unavailable (Chart.js not loaded).";
      return;
    }
    var key = canvas.dataset.chartKey;
    var type = canvas.dataset.chartType || "bar";
    var dataEl = document.getElementById("charts-data");
    if (!dataEl) return;
    var all;
    try {
      all = JSON.parse(dataEl.textContent);
    } catch (e) {
      return;
    }
    var series = all[key];
    if (!series || !series.labels || !series.values) return;

    if (type === "line") {
      var sets = [];
      if (Array.isArray(series.present)) sets.push(dataset("Present", series.present, palette.success));
      if (Array.isArray(series.late)) sets.push(dataset("Late", series.late, palette.warning));
      if (Array.isArray(series.absent)) sets.push(dataset("Absent", series.absent, palette.danger));
      if (sets.length === 0 && Array.isArray(series.passed)) {
        sets.push(dataset("Passed", series.passed, palette.success));
        sets.push(dataset("Failed", series.failed, palette.danger));
        sets.push(dataset("Needs attention", series.needs_attention, palette.warning));
      }
      new Chart(canvas, { type: "line", data: { labels: series.labels, datasets: sets }, options: chartOptions() });
    } else {
      new Chart(canvas, {
        type: type,
        data: { labels: series.labels, datasets: [dataset("", series.values, palette.primary)] },
        options: type === "doughnut" ? doughnutOptions() : chartOptions(),
      });
    }
  }

  function chartOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: palette.text } } },
      scales: {
        x: { grid: { color: palette.grid }, ticks: { color: palette.text, maxRotation: 45 } },
        y: { beginAtZero: true, grid: { color: palette.grid }, ticks: { color: palette.text } },
      },
    };
  }

  function doughnutOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: palette.text } } },
    };
  }

  function toggleSidebar() {
    var shell = document.querySelector(".wb-shell");
    if (shell) shell.classList.toggle("wb-nav-open");
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".wb-chart-canvas").forEach(renderChart);
    var toggle = document.querySelector("[data-wb-toggle='sidebar']");
    if (toggle) toggle.addEventListener("click", toggleSidebar);
  });
})();
