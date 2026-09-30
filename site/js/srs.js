// In-session Anki-style learning queue. Long-term scheduling (ease/interval) lives in
// src/vocab/srs.py and is applied to data/bank.json when test results are processed.
//
//   fail      -> card comes back ~3 cards later
//   practice  -> card comes back ~8 cards later
//   mastered  -> card leaves the session
// The session ends once every card has been rated "mastered" once. In test mode only the
// FIRST rating for each card counts towards the score and the word bank.

export const REINSERT = { fail: 3, practice: 8 };
export const POINTS = { fail: 0, practice: 0.5, mastered: 1 };

export function score(ratings) {
  const values = Object.values(ratings);
  if (!values.length) return 0;
  return Math.round((1000 * values.reduce((s, r) => s + POINTS[r], 0)) / values.length) / 10;
}

function shuffle(items) {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export class Session {
  constructor(cardIds, state = null) {
    this.total = cardIds.length;
    this.queue = state?.queue ?? shuffle(cardIds);
    this.first = state?.first ?? {};
    this.reviews = state?.reviews ?? 0;
  }

  get current() { return this.queue[0] ?? null; }
  get done() { return this.queue.length === 0; }
  get masteredCount() { return this.total - new Set(this.queue).size; }

  rate(rating) {
    const id = this.queue.shift();
    if (id === undefined) return;
    this.reviews += 1;
    if (!(id in this.first)) this.first[id] = rating;
    if (rating !== "mastered") {
      this.queue.splice(Math.min(REINSERT[rating], this.queue.length), 0, id);
    }
  }

  breakdown() {
    const counts = { fail: 0, practice: 0, mastered: 0 };
    for (const r of Object.values(this.first)) counts[r] += 1;
    return counts;
  }

  score() { return score(this.first); }

  toJSON() {
    return { queue: this.queue, first: this.first, reviews: this.reviews };
  }
}
