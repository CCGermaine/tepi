// Zero-dependency port of Tepi's scheduling engine and Level 2 prompt rules.
// Matches tepi/engine.py and tepi/sentence.py.

export const EXPORT_FORMAT = "tepi-progress-v1";

export const DEFAULT_CONFIG = Object.freeze({
  newPerDay: 2,
  reviewCap: 4,
  catchUpReviewCap: 12,
  catchUp: true,
  knownIntervals: [1, 3, 7, 16, 30],
  fuzzyDays: 2,
  missedDays: 1,
});

const ACTIVE_FORMS = {
  ajar: ["mengajar"],
  jalan: ["berjalan"],
  beli: ["membeli"],
  main: ["bermain"],
  cuci: ["mencuci"],
  kerja: ["bekerja"],
  cakap: ["bercakap"],
  bayar: ["membayar"],
  masak: ["memasak"],
  tidur: ["tertidur"],
};

const FUNCTION_WORDS = new Set([
  "yang", "untuk", "dengan", "pada", "kepada", "daripada", "oleh", "itu",
  "atau", "kalau", "jika", "kerana", "sebab", "pun", "lah", "kah", "tah",
  "nya", "akan", "telah", "sedang", "supaya", "agar", "dalam", "atas",
  "bawah", "tentang",
]);

export function localIsoDate(now = new Date()) {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function addDays(isoDate, days) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  return dt.toISOString().slice(0, 10);
}

export function tokenize(sentence) {
  return sentence
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]+/gu, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function makeCloze(sentence, lemma, override = null) {
  if (override && override.trim()) return override.trim();
  if (tokenize(sentence).length < 2) return null;
  const candidates = [lemma, ...(ACTIVE_FORMS[lemma.toLowerCase()] || [])];
  for (const target of candidates) {
    const re = new RegExp(`(?<!\\p{L})${escapeRegExp(target)}(?!\\p{L})`, "iu");
    if (re.test(sentence)) {
      return sentence.replace(re, "___");
    }
  }
  return null;
}

export function cardPrompt(entry, mode, intervalIndex) {
  if (mode !== "review" || !entry) return { promptMode: "word", cloze: null };
  if (intervalIndex <= 2) return { promptMode: "word", cloze: null };
  if (intervalIndex <= 4) {
    const cloze = makeCloze(entry.sentence, entry.lemma, entry.cloze || null);
    if (cloze) return { promptMode: "cloze", cloze };
    return { promptMode: "reverse", cloze: null };
  }
  return { promptMode: "reverse", cloze: null };
}

export function cousinFamilies(entries) {
  const groups = new Map();
  for (const entry of entries) {
    if (!groups.has(entry.root)) groups.set(entry.root, []);
    groups.get(entry.root).push(entry);
  }
  return [...groups.entries()]
    .filter(([, members]) => members.length >= 2)
    .map(([root, members]) => ({ root, members }))
    .sort((a, b) => a.members[0].index - b.members[0].index);
}

export function cousinsOf(entries, entry) {
  if (!entry) return [];
  const family = cousinFamilies(entries).find((f) => f.members.some((m) => m.id === entry.id));
  if (!family) return [];
  return family.members.filter((m) => m.id !== entry.id).map((m) => m.lemma);
}

export function settledPromptSentence(entries, progressMap) {
  const settled = entries.filter((e) => progressMap.get(e.id)?.state === "settled");
  if (!settled.length) return null;
  const allowed = new Set(settled.map((e) => e.lemma.toLowerCase()));
  for (const entry of settled) {
    const toks = tokenize(entry.sentence);
    if (!toks.length || toks.length > 12) continue;
    const allKnown = toks.every((t) => allowed.has(t) || FUNCTION_WORDS.has(t));
    if (allKnown) return { entry, sentence: entry.sentence };
  }
  return null;
}

export function ensurePlan(state, entries, config, today) {
  const existing = state.plans.find((p) => p.day === today);
  if (existing) return existing;

  const progressMap = new Map(state.progress.map((r) => [r.wordId, r]));
  const dueRows = state.progress
    .filter((r) => r.state === "in_play" && r.due && r.due <= today)
    .sort((a, b) => (a.due < b.due ? -1 : a.due > b.due ? 1 : a.deckIndex - b.deckIndex));

  const overdue = dueRows.some((r) => r.due < today);
  const useHigher = Boolean(config.catchUp && overdue);
  const cap = useHigher ? config.catchUpReviewCap : config.reviewCap;
  const reviews = dueRows.slice(0, cap).map((r) => r.wordId);
  const catchUp = useHigher && reviews.length > config.reviewCap;

  const fresh = [];
  const batch = new Set();
  if (config.newPerDay > 0) {
    for (const entry of entries) {
      if (progressMap.has(entry.id)) continue;
      const ready = entry.requires.every((req) => progressMap.has(req) || batch.has(req));
      if (!ready) break;
      fresh.push(entry);
      batch.add(entry.id);
      if (fresh.length === config.newPerDay) break;
    }
  }

  const tomorrow = addDays(today, 1);
  const nowIso = new Date().toISOString();
  for (const entry of fresh) {
    state.progress.push({
      wordId: entry.id,
      introducedOn: today,
      due: tomorrow,
      intervalIndex: 0,
      state: "in_play",
      deckIndex: entry.index,
    });
    state.events.push({ ts: nowIso, day: today, wordId: entry.id, kind: "introduced" });
  }

  const plan = { day: today, reviews, introduced: fresh.map((e) => e.id), catchUp };
  state.plans.push(plan);
  return plan;
}

export function getPresentation(state, entries, config, today) {
  const plan = ensurePlan(state, entries, config, today);
  const byId = new Map(entries.map((e) => [e.id, e]));
  const progressMap = new Map(state.progress.map((r) => [r.wordId, r]));
  const ratings = new Set(["known", "fuzzy", "missed"]);

  const rated = new Set();
  const revealed = new Set();
  for (const ev of state.events) {
    if (ev.day !== today) continue;
    if (ratings.has(ev.kind)) rated.add(ev.wordId);
    else if (ev.kind === "revealed") revealed.add(ev.wordId);
  }

  const reviewsLeft = plan.reviews.filter((id) => !rated.has(id));
  const newLeft = plan.introduced.filter((id) => !revealed.has(id));

  let wordId = null;
  let mode = "rest";
  let isRevealed = true;

  if (reviewsLeft.length) {
    wordId = reviewsLeft[0];
    mode = "review";
    isRevealed = revealed.has(wordId);
  } else if (newLeft.length) {
    wordId = newLeft[0];
    mode = "new";
    isRevealed = false;
  } else if (plan.introduced.length) {
    wordId = plan.introduced[plan.introduced.length - 1];
  } else if (plan.reviews.length) {
    wordId = plan.reviews[plan.reviews.length - 1];
  } else if (state.progress.length) {
    const sorted = [...state.progress].sort((a, b) =>
      a.introducedOn !== b.introducedOn
        ? (a.introducedOn < b.introducedOn ? 1 : -1)
        : b.deckIndex - a.deckIndex
    );
    wordId = sorted[0].wordId;
  }

  const entry = wordId ? byId.get(wordId) || null : null;
  if (!entry) mode = "empty";
  const prog = entry ? progressMap.get(entry.id) : null;
  const intervalIndex = prog ? prog.intervalIndex : 0;
  const { promptMode, cloze } = cardPrompt(entry, mode, intervalIndex);

  return {
    date: today,
    mode,
    entry,
    revealed: entry ? isRevealed : false,
    promptMode,
    cloze,
    intervalIndex,
    ladderLength: config.knownIntervals.length,
    plan,
    reviewsRemaining: reviewsLeft.length,
    newRemaining: newLeft.length,
  };
}

export function revealCurrent(state, entries, config, today) {
  const card = getPresentation(state, entries, config, today);
  if (!card.entry) return card;
  state.events.push({ ts: new Date().toISOString(), day: today, wordId: card.entry.id, kind: "revealed" });
  return { ...card, revealed: true };
}

export function rateCurrent(state, entries, config, today, rating) {
  const card = getPresentation(state, entries, config, today);
  if (card.mode !== "review" || !card.entry) return null;
  const row = state.progress.find((r) => r.wordId === card.entry.id);
  if (!row) return null;

  const idx = row.intervalIndex;
  let nextState = "in_play";
  let due = null;
  let newIdx = idx;

  if (rating === "known" && idx >= config.knownIntervals.length) {
    nextState = "settled";
    due = null;
    newIdx = idx;
  } else if (rating === "known") {
    due = addDays(today, config.knownIntervals[idx]);
    newIdx = idx + 1;
  } else if (rating === "fuzzy") {
    due = addDays(today, config.fuzzyDays);
    newIdx = idx;
  } else {
    due = addDays(today, config.missedDays);
    newIdx = 0;
  }

  row.due = due;
  row.intervalIndex = newIdx;
  row.state = nextState;
  state.events.push({ ts: new Date().toISOString(), day: today, wordId: card.entry.id, kind: rating });

  return { entry: card.entry, rating, due, state: nextState, intervalIndex: newIdx };
}
