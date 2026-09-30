// Commits test results to the repo via the GitHub Contents API, using a fine-grained token
// kept only in this browser's localStorage.
import { storage } from "./data.js";

const API = "https://api.github.com";

function guessRepo() {
  // https://owner.github.io/repo/ -> owner/repo
  const m = location.hostname.match(/^([^.]+)\.github\.io$/);
  const repo = location.pathname.split("/").filter(Boolean)[0];
  return m && repo ? `${m[1]}/${repo}` : "";
}

export function getSettings() {
  return { repo: guessRepo(), branch: "main", token: "", ...storage.get("gh-settings", {}) };
}

export function saveSettings(settings) {
  storage.set("gh-settings", settings);
}

function headers(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function toBase64(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

export async function testConnection({ repo, token }) {
  const res = await fetch(`${API}/repos/${repo}`, { headers: headers(token) });
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${(await res.json()).message}`);
  const data = await res.json();
  if (!data.permissions?.push) throw new Error("Token can read the repo but cannot write to it.");
  return data.full_name;
}

export async function putFile(path, content, message) {
  const { repo, branch, token } = getSettings();
  if (!repo || !token) throw new Error("Set your repository and token in Settings first.");
  const url = `${API}/repos/${repo}/contents/${path}`;

  // Include the existing file's sha so a retaken test overwrites the previous submission.
  let sha;
  const existing = await fetch(`${url}?ref=${encodeURIComponent(branch)}`, { headers: headers(token) });
  if (existing.ok) sha = (await existing.json()).sha;

  const res = await fetch(url, {
    method: "PUT",
    headers: headers(token),
    body: JSON.stringify({ message, content: toBase64(content), branch, sha }),
  });
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${(await res.json()).message}`);
  return res.json();
}
