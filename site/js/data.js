// Loads the (encrypted) JSON produced by the Python pipeline. On GitHub Pages the deploy copies
// data/ into the site; when serving the repo root locally (…/site/), fall back to ../data/.
import { decryptJSON, encryptJSON, forgetKeys } from "./crypto.js";

const DATA_BASE = location.pathname.includes("/site/") ? "../data/" : "data/";
const PW_KEY = "site-pw";

export async function fetchJSON(path, fallback = null) {
  try {
    const res = await fetch(DATA_BASE + path, { cache: "no-cache" });
    if (!res.ok) return fallback;
    return await res.json();
  } catch {
    return fallback;
  }
}

// Tiny try/catch wrappers: storage can be unavailable (private mode, blocked site data).
function wrap(area) {
  return {
    get(key, fallback = null) {
      try {
        const v = area().getItem(key);
        return v === null ? fallback : JSON.parse(v);
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try { area().setItem(key, JSON.stringify(value)); } catch { /* ignore */ }
    },
    remove(key) {
      try { area().removeItem(key); } catch { /* ignore */ }
    },
  };
}
export const storage = wrap(() => localStorage);
const session = wrap(() => sessionStorage);

// ---------- password ----------
let password = null;
let salt = null;

export const getPassword = () => password;
export const savedPassword = () => session.get(PW_KEY) || storage.get(PW_KEY);

async function sharedSalt() {
  salt ??= (await fetchJSON("crypto.json"))?.salt ?? null;
  return salt;
}

// Checks the password against the encrypted data. Throws on a wrong password.
export async function unlock(pw, remember = false) {
  const probe = (await fetchJSON("lists/index.enc.json")) || (await fetchJSON("bank.enc.json"));
  if (probe) await decryptJSON(probe, pw);
  password = pw;
  session.set(PW_KEY, pw);
  if (remember) storage.set(PW_KEY, pw);
}

export function lock() {
  password = null;
  forgetKeys();
  session.remove(PW_KEY);
  storage.remove(PW_KEY);
}

export async function fetchEncrypted(path) {
  const envelope = await fetchJSON(path);
  return envelope ? decryptJSON(envelope, password) : null;
}

export async function encryptForCommit(data) {
  return JSON.stringify(await encryptJSON(data, password, await sharedSalt())) + "\n";
}

// ---------- data ----------
export const loadIndex = async () => (await fetchEncrypted("lists/index.enc.json")) ?? { lists: [] };
export const loadList = (id) => fetchEncrypted(`lists/${id}.enc.json`);
export const loadBank = async () =>
  (await fetchEncrypted("bank.enc.json")) ?? { words: {}, applied_results: [] };
