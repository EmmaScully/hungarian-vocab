// Browser half of src/vocab/crypto.py — keep the envelope format in sync:
// PBKDF2-SHA256 -> AES-256-GCM, fields {v, kdf, iter, salt, iv, ct} base64-encoded.
const ITERATIONS = 600000;
const enc = new TextEncoder();
const dec = new TextDecoder();

const toB64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const fromB64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

async function deriveKey(password, salt, iterations) {
  const material = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, [
    "deriveKey",
  ]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

// Throws if the password is wrong (AES-GCM authentication fails).
export async function decryptJSON(envelope, password) {
  const key = await deriveKey(password, fromB64(envelope.salt), envelope.iter);
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: fromB64(envelope.iv) },
    key,
    fromB64(envelope.ct),
  );
  return JSON.parse(dec.decode(plain));
}

export async function encryptJSON(data, password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(password, salt, ITERATIONS);
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(JSON.stringify(data)));
  return { v: 1, kdf: "PBKDF2-SHA256", iter: ITERATIONS, salt: toB64(salt), iv: toB64(iv), ct: toB64(ct) };
}
