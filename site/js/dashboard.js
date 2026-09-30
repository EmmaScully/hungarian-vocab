import { loadBank } from "./data.js";

const charts = {};
let cachedBank = null;
let lastLists = [];

const $ = (sel) => document.querySelector(sel);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function td(text) {
  const cell = document.createElement("td");
  cell.textContent = text;
  return cell;
}

function row(...cells) {
  const tr = document.createElement("tr");
  tr.append(...cells.map(td));
  return tr;
}

// Consecutive tested weeks counting back from the most recent list (the current, untested
// week doesn't break the streak).
function streak(lists) {
  let n = 0;
  const ordered = [...lists].reverse();
  if (ordered[0] && !ordered[0].tested) ordered.shift();
  for (const e of ordered) {
    if (!e.tested) break;
    n += 1;
  }
  return n;
}

function renderTiles(words, lists) {
  const all = Object.values(words);
  const count = (s) => all.filter((w) => w.status === s).length;
  const tested = lists.filter((e) => e.tested);
  const avg = tested.length
    ? Math.round(tested.reduce((s, e) => s + e.score, 0) / tested.length)
    : null;
  const tiles = [
    ["Words seen", all.length],
    ["Mastered", count("mastered")],
    ["Practising", count("learning")],
    ["Not yet tested", count("new")],
    ["Avg test score", avg === null ? "–" : `${avg}%`],
    ["Week streak", streak(lists)],
  ];
  $("#tiles").replaceChildren(
    ...tiles.map(([k, v]) => {
      const div = document.createElement("div");
      div.className = "tile";
      div.innerHTML = `<div class="v"></div><div class="k"></div>`;
      div.querySelector(".v").textContent = v;
      div.querySelector(".k").textContent = k;
      return div;
    }),
  );
}

function lineChart(id, labels, data, { max, suffix = "" } = {}) {
  charts[id]?.destroy();
  const color = css("--series-1");
  const muted = css("--muted");
  const grid = css("--grid");
  charts[id] = new Chart(document.getElementById(id), {
    type: "line",
    data: {
      labels,
      datasets: [{
        data,
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBorderColor: css("--surface"),
        pointBorderWidth: 2,
        tension: 0,
      }],
    },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.parsed.y}${suffix}` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: muted }, border: { color: grid } },
        y: {
          beginAtZero: true,
          max,
          grid: { color: grid },
          border: { display: false },
          ticks: { color: muted, precision: 0 },
        },
      },
    },
  });
}

function renderCharts(words, lists) {
  if (typeof Chart === "undefined") return;
  const tested = lists.filter((e) => e.tested);
  lineChart("chart-score", tested.map((e) => e.id), tested.map((e) => e.score), {
    max: 100,
    suffix: "%",
  });

  // Mastered words as of the end of each list's week.
  const masteredDates = Object.values(words)
    .filter((w) => w.mastered_on)
    .map((w) => new Date(w.mastered_on));
  const weekEnd = (e) => new Date(new Date(e.created).getTime() + 7 * 864e5);
  lineChart(
    "chart-mastered",
    lists.map((e) => e.id),
    lists.map((e) => masteredDates.filter((d) => d < weekEnd(e)).length),
  );
}

function renderTables(words, lists) {
  const hardest = Object.values(words)
    .filter((w) => w.lapses > 0 || w.last_rating === "practice")
    .sort((a, b) => b.lapses - a.lapses || a.ease - b.ease)
    .slice(0, 12);
  const statusLabel = { new: "untested", learning: "practising", mastered: "mastered ✓" };
  $("#hard-table tbody").replaceChildren(
    ...(hardest.length
      ? hardest.map((w) => row(w.en, w.hu, w.lapses, statusLabel[w.status]))
      : [row("Nothing yet — take a test first.", "", "", "")]),
  );
  $("#weeks-table tbody").replaceChildren(
    ...[...lists].reverse().map((e) =>
      row(e.id, e.n_cards, (e.topics || []).join(", ") || "—", e.tested ? `${e.score}%` : "not yet"),
    ),
  );
}

export async function renderDashboard(index) {
  cachedBank ??= await loadBank();
  const words = cachedBank.words || {};
  const lists = index.lists || [];
  lastLists = lists;
  renderTiles(words, lists);
  renderTables(words, lists);
  renderCharts(words, lists);
}

// Re-render charts with the right colours when the OS theme changes.
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (cachedBank && !$("#view-dashboard").hidden) {
    renderCharts(cachedBank.words || {}, lastLists);
  }
});
