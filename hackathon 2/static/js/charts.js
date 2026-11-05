const chartInstances = new Map();

function parseChartData(canvas, key) {
  try { return JSON.parse(canvas.dataset[key] || "[]"); }
  catch (_) { return []; }
}

function createChart(id, type = "bar") {
  const canvas = document.getElementById(id);
  if (!canvas || !window.Chart) return;
  const labels = parseChartData(canvas, "labels");
  const values = parseChartData(canvas, "values").map((value) => Number(value) || 0);
  if (!labels.length || labels.length !== values.length) return;
  chartInstances.get(id)?.destroy();
  const simple = canvas.dataset.simplePerformance === "true";
  chartInstances.set(id, new Chart(canvas, {
    type,
    data: { labels, datasets: [{ data: values, label: canvas.dataset.label || "Score", backgroundColor: "#2563eb", borderColor: "#2563eb", borderWidth: type === "line" ? 2 : 0, borderRadius: 5, barThickness: simple ? 28 : undefined, fill: false, tension: 0.35 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: simple ? "y" : "x",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => `${context.raw || 0}%` } } },
      scales: {
        x: { beginAtZero: true, max: 100, ticks: { color: "#64748b", callback: (value) => `${value}%` }, grid: { display: false } },
        y: { ticks: { color: "#334155" }, grid: { display: false } },
      },
    },
  }));
}

document.addEventListener("DOMContentLoaded", () => {
  createChart("dashboardPerformanceChart");
  createChart("moduleChart");
  createChart("trendChart", "line");
  createChart("adminChart", "doughnut");
  createChart("adminScoreTrendChart", "line");
  createChart("adminModuleChart");
  createChart("adminStudentChart");
  const trendCanvas = document.getElementById("trendChart");
  if (trendCanvas) {
    fetch("/api/performance")
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => {
        trendCanvas.dataset.labels = JSON.stringify((data.trend || []).map((item) => item.label || ""));
        trendCanvas.dataset.values = JSON.stringify((data.trend || []).map((item) => Number(item.score) || 0));
        createChart("trendChart", "line");
      })
      .catch(() => {});
  }
});
