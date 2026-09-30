// Loads the JSON produced by the Python pipeline. On GitHub Pages the deploy copies data/ into
// the site; when serving the repo root locally (…/site/), fall back to ../data/.
const DATA_BASE = location.pathname.includes("/site/") ? "../data/" : "data/";

export async function fetchJSON(path, fallback = null) {
  try {
    const res = await fetch(DATA_BASE + path, { cache: "no-cache" });
    if (!res.ok) return fallback;
    return await res.json();
  } catch {
    return fallback;
  }
}

export const loadIndex = () => fetchJSON("lists/index.json", { lists: [] });
export const loadList = (id) => fetchJSON(`lists/${id}.json`);
export const loadBank = () => fetchJSON("bank.json", { words: {}, applied_results: [] });

// Tiny try/catch wrappers: storage can be unavailable (private mode, blocked site data).
export const storage = {
  get(key, fallback = null) {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ }
  },
  remove(key) {
    try { localStorage.removeItem(key); } catch { /* ignore */ }
  },
};
