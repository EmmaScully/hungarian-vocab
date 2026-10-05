// Browser half of src/vocab/crypto.py — keep the envelope format in sync:
// PBKDF2-SHA256 -> AES-256-GCM, fields {v, kdf, iter, salt, iv, ct} base64-encoded.
// Derived keys are cached, so files sharing the data/crypto.json salt cost one derivation.
const ITERATIONS = 600000;
const enc = new TextEncoder();
const dec = new TextDecoder();
const keys = new Map();

const toB64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const fromB64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

function deriveKey(password, saltB64, iterations) {
  const id = `${iterations}:${saltB64}:${password}`;
  if (!keys.has(id)) {
    const promise = crypto.subtle
      .importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"])
      .then((material) =>
        crypto.subtle.deriveKey(
          { name: "PBKDF2", hash: "SHA-256", salt: fromB64(saltB64), iterations },
          material,
          { name: "AES-GCM", length: 256 },
          false,
          ["encrypt", "decrypt"],
        ),
      );
    keys.set(id, promise);
  }
  return keys.get(id);
}

export function forgetKeys() {
  keys.clear();
}

// Throws (OperationError) if the password is wrong: AES-GCM authentication fails.
export async function decryptJSON(envelope, password) {
  const key = await deriveKey(password, envelope.salt, envelope.iter);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromB64(envelope.iv) }, key, fromB64(envelope.ct));
  return JSON.parse(dec.decode(plain));
}

// Pass the shared salt (data/crypto.json) to reuse the cached key.
export async function encryptJSON(data, password, saltB64 = null) {
  const salt = saltB64 || toB64(crypto.getRandomValues(new Uint8Array(16)));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(password, salt, ITERATIONS);
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(JSON.stringify(data)));
  return { v: 1, kdf: "PBKDF2-SHA256", iter: ITERATIONS, salt, iv: toB64(iv), ct: toB64(ct) };
}
