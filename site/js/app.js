import { loadIndex, loadList, storage } from "./data.js";
import { getSettings, putFile, saveSettings, testConnection } from "./github.js";
import { Session } from "./srs.js";
import { renderDashboard } from "./dashboard.js";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const state = {
  index: { lists: [] },
  list: null,
  cards: {},
  mode: "revise",
  direction: storage.get("direction", "en-hu"),
  session: null,
  flipped: false,
};

// ---------- routing ----------
function route() {
  const name = (location.hash || "#study").slice(1);
  const view = ["study", "dashboard", "settings"].includes(name) ? name : "study";
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
  $$("[data-route]").forEach((a) => a.classList.toggle("active", a.dataset.route === view));
  if (view === "dashboard") renderDashboard(state.index);
}

// ---------- study ----------
const sessionKey = () => `session:${state.list.id}:${state.mode}`;
const indexEntry = () => state.index.lists.find((e) => e.id === state.list?.id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  node.append(...children);
  return node;
}

async function selectList(id) {
  state.list = await loadList(id);
  if (!state.list) {
    $("#list-banner").textContent = `Could not load list ${id}.`;
    $("#list-banner").hidden = false;
    return;
  }
  state.cards = Object.fromEntries(state.list.cards.map((c) => [c.id, c]));
  renderWordTable();
  startSession(false);
}

function renderBanner() {
  const entry = indexEntry();
  const banner = $("#list-banner");
  const latest = state.index.lists.at(-1)?.id === state.list.id;
  let text = "";
  if (entry?.tested) {
    text = `✅ Tested — score ${entry.score}%. Results are in the word bank; test mode here is practice only.`;
  } else if (storage.get(`submitted:${state.list.id}`)) {
    text = "⏳ Test submitted — the word bank updates in a minute or two.";
  } else if (state.mode === "test") {
    text = "📝 Test mode: your FIRST answer for each card is recorded and decides which words come back next week.";
  } else if (latest) {
    text = "Revise during the week, then switch to Test before next Monday.";
  }
  banner.textContent = text;
  banner.hidden = !text;
}

function renderWordTable() {
  const tbody = $("#word-table tbody");
  tbody.replaceChildren(
    ...state.list.cards.map((c) =>
      el(
        "tr",
        {},
        el("td", {}, c.front_en),
        el("td", {}, el("b", {}, c.back_hu), " ", c.source === "review" ? el("span", { class: "tag" }, "review") : ""),
        el("td", { class: "ex" }, c.example_hu || "", c.example_en ? el("br") : "", el("i", {}, c.example_en || "")),
      ),
    ),
  );
  const link = $("#audio-link");
  link.replaceChildren();
  if (state.list.audio_url) {
    link.append(" · ", el("a", { href: state.list.audio_url }, "🎧 mp3"));
  }
}

function startSession(fresh) {
  const ids = state.list.cards.map((c) => c.id);
  const saved = fresh ? null : storage.get(sessionKey());
  // Discard saved state that no longer matches the list (e.g. regenerated).
  const valid = saved && saved.queue.every((id) => id in state.cards);
  state.session = new Session(ids, valid ? saved : null);
  renderBanner();
  renderCard();
}

function saveSession() {
  storage.set(sessionKey(), state.session.toJSON());
}

function setFlipped(flipped) {
  state.flipped = flipped;
  $("#card").classList.toggle("flipped", flipped);
  $$(".btn.rate").forEach((b) => (b.disabled = !flipped));
  $("#btn-flip").textContent = flipped ? "Flip back" : "Flip";
}

function renderCard() {
  const s = state.session;
  $("#progress-bar").style.width = `${(100 * s.masteredCount) / s.total}%`;
  $("#progress-text").textContent =
    `${s.masteredCount} / ${s.total} mastered · ${s.reviews} reviews` +
    (state.mode === "test" ? ` · ${Object.keys(s.first).length} / ${s.total} answered` : "");

  if (s.done) return renderFinished();
  $("#session").hidden = false;
  $("#finished").hidden = true;

  const card = state.cards[s.current];
  const huFirst = state.direction === "hu-en";
  $("#front-lang").textContent = huFirst ? "Magyar" : "English";
  $("#back-lang").textContent = huFirst ? "English" : "Magyar";
  $("#front-text").textContent = huFirst ? card.back_hu : card.front_en;
  $("#back-text").textContent = huFirst ? card.front_en : card.back_hu;
  $("#back-pos").textContent = card.pos || "";
  $("#back-example").replaceChildren(
    card.example_hu || "",
    card.example_en ? el("br") : "",
    el("i", {}, card.example_en || ""),
  );
  // Swap text without animating the flip-back for the new card.
  const inner = $(".card-inner");
  inner.style.transition = "none";
  setFlipped(false);
  void inner.offsetWidth;
  inner.style.transition = "";
}

function renderFinished() {
  const s = state.session;
  $("#session").hidden = true;
  $("#finished").hidden = false;
  const b = s.breakdown();
  $("#finished-title").textContent = state.mode === "test" ? "Test complete" : "Revision complete";
  $("#final-score").textContent = `${s.score()}%`;
  $("#finished-breakdown").textContent =
    `First answers: ${b.mastered} mastered · ${b.practice} needs practice · ${b.fail} failed`;

  const entry = indexEntry();
  const canSubmit = state.mode === "test" && !entry?.tested;
  $("#submit-area").hidden = !canSubmit;
  $("#submit-status").textContent = "";
  $("#btn-submit").disabled = false;
}

function rate(rating) {
  if (!state.flipped || state.session.done) return;
  state.session.rate(rating);
  saveSession();
  renderCard();
}

async function submitTest() {
  const s = state.session;
  const result = {
    list_id: state.list.id,
    completed_at: new Date().toISOString(),
    ratings: s.first,
    score: s.score(),
  };
  const status = $("#submit-status");
  $("#btn-submit").disabled = true;
  status.className = "small";
  status.textContent = "Submitting…";
  try {
    await putFile(
      `data/results/${state.list.id}-test.json`,
      JSON.stringify(result, null, 2) + "\n",
      `Test results for ${state.list.id} (${result.score}%)`,
    );
    storage.set(`submitted:${state.list.id}`, true);
    status.className = "small ok";
    status.textContent = "Saved ✔ The word bank will update shortly.";
  } catch (err) {
    $("#btn-submit").disabled = false;
    status.className = "small err";
    status.textContent = `${err.message} `;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    status.append(
      el("a", { href: URL.createObjectURL(blob), download: `${state.list.id}-test.json` }, "Download results instead"),
    );
  }
}

function bindStudy() {
  $("#list-select").addEventListener("change", (e) => selectList(e.target.value));
  $$("[data-mode]").forEach((btn) =>
    btn.addEventListener("click", () => {
      state.mode = btn.dataset.mode;
      $$("[data-mode]").forEach((b) => b.classList.toggle("active", b === btn));
      startSession(false);
    }),
  );
  $("#direction").value = state.direction;
  $("#direction").addEventListener("change", (e) => {
    state.direction = e.target.value;
    storage.set("direction", state.direction);
    renderCard();
  });
  $("#card").addEventListener("click", () => setFlipped(!state.flipped));
  $("#btn-flip").addEventListener("click", () => setFlipped(!state.flipped));
  $$("[data-rate]").forEach((b) => b.addEventListener("click", () => rate(b.dataset.rate)));
  $("#btn-restart").addEventListener("click", () => startSession(true));
  $("#btn-again").addEventListener("click", () => startSession(true));
  $("#btn-submit").addEventListener("click", submitTest);

  document.addEventListener("keydown", (e) => {
    if ($("#view-study").hidden || e.target.matches("input, select, textarea")) return;
    if (e.key === " " || e.key === "Enter") {
      if (e.target.matches("button")) return;
      e.preventDefault();
      setFlipped(!state.flipped);
    } else if (e.key === "1") rate("fail");
    else if (e.key === "2") rate("practice");
    else if (e.key === "3") rate("mastered");
  });
}

// ---------- settings ----------
function bindSettings() {
  const form = $("#settings-form");
  const status = $("#settings-status");
  const s = getSettings();
  form.repo.value = s.repo;
  form.branch.value = s.branch;
  form.token.value = s.token;
  const read = () => ({
    repo: form.repo.value.trim(),
    branch: form.branch.value.trim() || "main",
    token: form.token.value.trim(),
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    saveSettings(read());
    status.className = "small ok";
    status.textContent = "Saved in this browser.";
  });
  $("#btn-test-conn").addEventListener("click", async () => {
    status.className = "small";
    status.textContent = "Checking…";
    try {
      const name = await testConnection(read());
      status.className = "small ok";
      status.textContent = `Connected to ${name} with write access.`;
    } catch (err) {
      status.className = "small err";
      status.textContent = err.message;
    }
  });
}

// ---------- boot ----------
async function init() {
  bindStudy();
  bindSettings();
  window.addEventListener("hashchange", route);

  state.index = await loadIndex();
  const lists = state.index.lists;
  const select = $("#list-select");
  select.replaceChildren(
    ...[...lists].reverse().map((e) =>
      el("option", { value: e.id }, e.tested ? `${e.id} · ${e.score}%` : e.id),
    ),
  );
  route();

  if (!lists.length) {
    $("#session").hidden = true;
    $("#list-banner").textContent = "No word lists yet — run `vocab generate` (or the weekly workflow).";
    $("#list-banner").hidden = false;
    return;
  }
  // Always open on the newest list; older ones are in the picker for revision.
  const initial = lists.at(-1).id;
  select.value = initial;
  await selectList(initial);
}

init();
