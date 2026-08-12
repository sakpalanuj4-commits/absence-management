// Each canvas declares its own endpoint, e.g.
// <canvas data-chart="line" data-src="/reports/chart/attendance-trend/"></canvas>
(function () {
  if (typeof Chart === "undefined") return;

  const PALETTE = ["#4f46e5", "#059669", "#f59e0b", "#e11d48", "#0ea5e9", "#7c3aed"];
  const STATUS_COLOURS = {
    Present: "#059669",
    Absent: "#e11d48",
    Late: "#f59e0b",
    Excused: "#0ea5e9",
  };

  Chart.defaults.font.family =
    "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif";
  Chart.defaults.color = "#64748b";

  function build(canvas, rows) {
    const kind = canvas.dataset.chart;
    const labels = rows.map((row) => row.label);
    const values = rows.map((row) => row.value);

    if (kind === "doughnut") {
      return new Chart(canvas, {
        type: "doughnut",
        data: {
          labels,
          datasets: [
            {
              data: values,
              backgroundColor: labels.map(
                (label, i) => STATUS_COLOURS[label] || PALETTE[i % PALETTE.length]
              ),
              borderWidth: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "62%",
          plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
        },
      });
    }

    const isBar = kind === "bar";
    return new Chart(canvas, {
      type: isBar ? "bar" : "line",
      data: {
        labels,
        datasets: [
          {
            label: canvas.dataset.label || "Attendance %",
            data: values,
            borderColor: PALETTE[0],
            backgroundColor: isBar ? PALETTE[0] : "rgba(79, 70, 229, 0.12)",
            borderWidth: 2,
            fill: !isBar,
            tension: 0.3,
            pointRadius: 3,
            borderRadius: isBar ? 6 : 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            ticks: { callback: (value) => value + "%" },
            grid: { color: "#e2e8f0" },
          },
          x: { grid: { display: false } },
        },
      },
    });
  }

  document.querySelectorAll("canvas[data-src]").forEach(async (canvas) => {
    try {
      const response = await fetch(canvas.dataset.src, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const payload = await response.json();
      const rows = payload.data || [];
      if (rows.length === 0) {
        const message = document.createElement("p");
        message.className = "py-10 text-center text-sm text-slate-400";
        message.textContent = "No data to chart yet.";
        canvas.replaceWith(message);
        return;
      }
      build(canvas, rows);
    } catch (error) {
      canvas.replaceWith(
        Object.assign(document.createElement("p"), {
          className: "py-10 text-center text-sm text-rose-500",
          textContent: "Chart could not be loaded.",
        })
      );
    }
  });
})();
