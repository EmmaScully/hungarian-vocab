// Password-protected weekly reading & writing exercise.
// Everything for this tab is stored encrypted (see crypto.js); the password never leaves the
// browser and is kept only in sessionStorage for the current tab.
import { fetchJSON, storage } from "./data.js";
import { decryptJSON, encryptJSON } from "./crypto.js";
import { putFile } from "./github.js";

const $ = (sel) => document.querySelector(sel);
const PW_KEY = "writing-pw";

const state = { index: { lists: [] }, week: null, exercise: null, feedback: null, submission: null };

const session = {
  get() { try { return sessionStorage.getItem(PW_KEY); } catch { return null; } },
  set(v) { try { sessionStorage.setItem(PW_KEY, v); } catch { /* ignore */ } },
  clear() { try { sessionStorage.removeItem(PW_KEY); } catch { /* ignore */ } },
};

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    node.setAttribute(k, v === true ? "" : v);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

const paragraphs = (text) => text.split(/\n\s*\n|\n/).filter((p) => p.trim()).map((p) => el("p", {}, p.trim()));
const countWords = (text) => (text.trim() ? text.trim().split(/\s+/).length : 0);
const weeks = () => state.index.lists.filter((e) => e.has_writing).map((e) => e.id);
const entryFor = (week) => state.index.lists.find((e) => e.id === week);

async function loadEncrypted(path, password) {
  const envelope = await fetchJSON(path);
  return envelope ? decryptJSON(envelope, password) : null;
}

// ---------- lock / unlock ----------
function showLocked(message = "") {
  $("#writing-locked").hidden = false;
  $("#writing-unlocked").hidden = true;
  const status = $("#unlock-status");
  status.className = message ? "small err" : "small";
  status.textContent = message;
}

async function unlock(password) {
  const list = weeks();
  if (!list.length) {
    showLocked("No reading & writing exercises have been published yet.");
    return false;
  }
  $("#unlock-status").className = "small";
  $("#unlock-status").textContent = "Unlocking…";
  try {
    // Decrypting the latest exercise doubles as the password check.
    await loadWeek(list.at(-1), password);
  } catch (err) {
    showLocked(err.name === "OperationError" ? "Wrong password." : `Could not open: ${err.message}`);
    return false;
  }
  session.set(password);
  $("#writing-locked").hidden = true;
  $("#writing-unlocked").hidden = false;
  const select = $("#writing-week");
  select.replaceChildren(...[...list].reverse().map((w) => el("option", { value: w }, w)));
  select.value = state.week;
  return true;
}

async function loadWeek(week, password = session.get()) {
  const exercise = await loadEncrypted(`writing/${week}.enc.json`, password);
  if (!exercise) throw new Error(`exercise for ${week} not found`);
  const [feedback, submission] = await Promise.all([
    loadEncrypted(`writing/feedback/${week}.enc.json`, password).catch(() => null),
    loadEncrypted(`writing/submissions/${week}.enc.json`, password).catch(() => null),
  ]);
  Object.assign(state, { week, exercise, feedback, submission });
  render();
}

// ---------- rendering ----------
const draftKey = () => `writing-draft:${state.week}`;

function isSubmitted() {
  return Boolean(
    state.submission || state.feedback || entryFor(state.week)?.writing_submitted ||
      storage.get(`writing-submitted:${state.week}`),
  );
}

function answerFor(key) {
  const sub = state.submission;
  if (sub) return (key.startsWith("q") ? sub.answers : sub.writing)[key] || "";
  return storage.get(draftKey(), {})[key] || "";
}

function render() {
  const ex = state.exercise;
  const locked = isSubmitted();
  const status = $("#writing-status");
  if (state.feedback) {
    status.textContent = "✅ Marked — your feedback is below and was emailed to you.";
  } else if (locked) {
    status.textContent = "⏳ Submitted — feedback usually arrives (here and by email) within a few minutes.";
  } else {
    status.textContent = "Answer in Hungarian. Drafts save automatically in this browser; submit once when you're done.";
  }
  status.hidden = false;

  const en = (text) => el("span", { class: "en" }, text);
  const art = $("#exercise");
  const children = [
    el("h1", {}, ex.title_hu, " ", en(`(${ex.title_en})`)),
    el("p", { class: "muted small" }, `Level ${ex.level} · Theme: ${ex.theme}`),
    el("div", { class: "panel passage" }, ...paragraphs(ex.passage_hu)),
    ex.glossary?.length
      ? el(
          "details",
          { class: "panel" },
          el("summary", {}, "Glossary"),
          el("ul", { class: "glossary" }, ...ex.glossary.map((g) => el("li", {}, el("b", {}, g.hu), ` — ${g.en}`))),
        )
      : null,
    el("h2", {}, "Reading questions"),
    ...ex.questions.map((q, i) => field(`q${i + 1}`, `${i + 1}. ${q.question_hu}`, q.question_en, q.kind, locked)),
    el("h2", {}, "Writing"),
    ...ex.writing_prompts.map((w, i) =>
      field(`w${i + 1}`, w.prompt_hu, `${w.prompt_en} (${w.min_words}–${w.max_words} words)`, w.kind === "long" ? "essay" : "long", locked),
    ),
    locked
      ? null
      : el(
          "div",
          { class: "row" },
          el("button", { type: "button", class: "btn primary", id: "btn-writing-submit" }, "Submit for marking"),
          el("span", { id: "writing-submit-status", class: "small" }),
        ),
  ];
  art.replaceChildren(...children.filter(Boolean));
  $("#btn-writing-submit")?.addEventListener("click", submit);
  renderFeedback();
}

function field(key, label, labelEn, kind, locked) {
  const rows = { short: 2, long: 5, essay: 10 }[kind] || 3;
  const textarea = el("textarea", { rows, "data-key": key, readonly: locked, lang: "hu", spellcheck: "false" });
  textarea.value = answerFor(key);
  const counter = el("span", { class: "muted small counter" }, `${countWords(textarea.value)} words`);
  textarea.addEventListener("input", () => {
    counter.textContent = `${countWords(textarea.value)} words`;
    const draft = storage.get(draftKey(), {});
    draft[key] = textarea.value;
    storage.set(draftKey(), draft);
  });
  return el("label", { class: "answer" }, el("span", { class: "q" }, label), el("span", { class: "en small" }, labelEn), textarea, counter);
}

function renderFeedback() {
  const fb = state.feedback;
  const box = $("#feedback");
  box.hidden = !fb;
  if (!fb) return box.replaceChildren();
  const ex = state.exercise;
  const parts = [
    el(
      "div",
      { class: "row feedback-head" },
      el("h2", {}, `Feedback — ${fb.week_id}`),
      el("button", { type: "button", class: "btn", id: "btn-print" }, "Save as PDF"),
    ),
    el(
      "div",
      { class: "tiles" },
      ...[["Reading", `${fb.reading_score_pct}%`], ["Writing", `${fb.writing_score_pct}%`], ["Level", fb.level_estimate]].map(([k, v]) =>
        el("div", { class: "tile" }, el("div", { class: "v" }, v), el("div", { class: "k" }, k)),
      ),
    ),
    el("p", {}, fb.summary),
    ...fb.answers.map((a) =>
      el(
        "div",
        { class: `panel fb verdict-${a.verdict.replace(/\s+/g, "-")}` },
        el("h3", {}, `Q${a.question}. ${ex.questions[a.question - 1]?.question_hu ?? ""}`),
        el("p", { class: "small" }, el("b", {}, `${a.verdict} · ${a.score}/10`)),
        el("p", {}, el("b", {}, "Your answer: "), answerFor(`q${a.question}`) || "(no answer)"),
        el("p", {}, a.feedback),
        el("p", { class: "muted" }, el("b", {}, "Model answer: "), a.model_answer_hu),
      ),
    ),
    ...fb.writing.map((w) =>
      el(
        "div",
        { class: "panel fb" },
        el("h3", {}, `Writing task ${w.prompt} · ${w.score}/10 · ${w.level_estimate}`),
        el("p", {}, w.comments),
        w.strengths.length ? el("ul", {}, ...w.strengths.map((s) => el("li", {}, s))) : null,
        w.corrections.length
          ? el(
              "div",
              { class: "table-wrap" },
              el(
                "table",
                { class: "data" },
                el("thead", {}, el("tr", {}, el("th", {}, "You wrote"), el("th", {}, "Better"), el("th", {}, "Why"))),
                el(
                  "tbody",
                  {},
                  ...w.corrections.map((c) =>
                    el("tr", {}, el("td", { class: "wrong" }, c.original), el("td", { class: "right" }, c.corrected), el("td", {}, c.explanation)),
                  ),
                ),
              ),
            )
          : null,
        el("h4", {}, "Improved version"),
        ...paragraphs(w.improved_version_hu),
      ),
    ),
    fb.next_steps.length ? el("div", { class: "panel" }, el("h3", {}, "Next steps"), el("ul", {}, ...fb.next_steps.map((s) => el("li", {}, s)))) : null,
  ];
  box.replaceChildren(...parts.filter(Boolean));
  $("#btn-print").addEventListener("click", () => window.print());
}

// ---------- submit ----------
async function submit() {
  const status = $("#writing-submit-status");
  const values = Object.fromEntries([...document.querySelectorAll("#exercise textarea")].map((t) => [t.dataset.key, t.value.trim()]));
  const blank = Object.values(values).filter((v) => !v).length;
  const question = blank
    ? `${blank} answer(s) are empty. Submit anyway? You can only submit once per week.`
    : "Submit for marking? You can only submit once per week.";
  if (!confirm(question)) return;

  const submission = {
    week_id: state.week,
    submitted_at: new Date().toISOString(),
    answers: Object.fromEntries(Object.entries(values).filter(([k]) => k.startsWith("q"))),
    writing: Object.fromEntries(Object.entries(values).filter(([k]) => k.startsWith("w"))),
  };
  $("#btn-writing-submit").disabled = true;
  status.className = "small";
  status.textContent = "Encrypting and submitting…";
  try {
    const envelope = await encryptJSON(submission, session.get());
    await putFile(
      `data/writing/submissions/${state.week}.enc.json`,
      JSON.stringify(envelope) + "\n",
      `Writing submission for ${state.week}`,
    );
    storage.set(`writing-submitted:${state.week}`, true);
    state.submission = submission;
    render();
  } catch (err) {
    $("#btn-writing-submit").disabled = false;
    status.className = "small err";
    status.textContent = err.message;
  }
}

// ---------- public ----------
export function initWriting() {
  $("#unlock-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const pw = e.target.pw.value;
    if (await unlock(pw)) e.target.pw.value = "";
  });
  $("#btn-lock").addEventListener("click", () => {
    session.clear();
    Object.assign(state, { exercise: null, feedback: null, submission: null });
    $("#exercise").replaceChildren();
    $("#feedback").replaceChildren();
    showLocked();
  });
  $("#writing-week").addEventListener("change", (e) => loadWeek(e.target.value).catch((err) => showLocked(err.message)));
  $("#show-en").addEventListener("change", (e) => document.body.classList.toggle("show-en", e.target.checked));
}

export async function showWriting(index) {
  state.index = index;
  if (state.exercise) return; // already unlocked in this page view
  const pw = session.get();
  if (!pw || !(await unlock(pw))) showLocked($("#unlock-status").textContent);
}
