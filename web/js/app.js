import {
  addDays,
  cousinFamilies,
  cousinsOf,
  getPresentation,
  localIsoDate,
  rateCurrent,
  revealCurrent,
  settledPromptSentence,
} from "./engine.js";
import {
  buildSnapshot,
  loadPrefs,
  loadState,
  parseSnapshot,
  savePrefs,
  saveState,
} from "./store.js";

let entries = [];
let state = loadState();
let prefs = loadPrefs();
let activeTab = "today";
let lastRated = null;
let heldNewCard = null;
let revealedWordId = null;
let malayVoice = null;

function $(sel) { return document.querySelector(sel); }

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showToast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => { el.hidden = true; }, 2600);
}

function applyTheme() {
  const theme = prefs.theme === "system"
    ? (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
    : prefs.theme;
  document.documentElement.dataset.theme = theme;
}

function detectMalayVoice() {
  if (!("speechSynthesis" in window)) return;
  const pick = () => {
    const voices = window.speechSynthesis.getVoices();
    malayVoice =
      voices.find((v) => v.lang.toLowerCase() === "ms-my") ||
      voices.find((v) => v.lang.toLowerCase().startsWith("ms")) ||
      null;
    if (activeTab === "today" && entries.length) renderToday();
  };
  pick();
  window.speechSynthesis.onvoiceschanged = pick;
}

function speakMalay(text) {
  if (!malayVoice || !prefs.audio || !text) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.voice = malayVoice;
  u.lang = "ms-MY";
  u.rate = 0.92;
  window.speechSynthesis.speak(u);
}

async function loadCurriculum() {
  const bases = ["./deck", "../deck"];
  for (const base of bases) {
    try {
      const idxRes = await fetch(`${base}/index.json`);
      if (!idxRes.ok) continue;
      const { decks } = await idxRes.json();
      const loaded = [];
      for (const file of decks) {
        const res = await fetch(`${base}/${file}`);
        if (!res.ok) throw new Error(`Could not load ${file}`);
        const data = await res.json();
        for (const w of data.words) {
          loaded.push({ ...w, index: loaded.length });
        }
      }
      return loaded;
    } catch {
      // try next base
    }
  }
  throw new Error("Could not load Tepi decks. Serve from the repo root (e.g. python3 -m http.server).");
}

function rungDots(index, total) {
  const dots = [];
  for (let i = 0; i < total; i++) {
    dots.push(`<span class="rung-dot ${i < index ? "is-filled" : ""}" aria-hidden="true"></span>`);
  }
  return `<span class="rungs" title="Recall rung ${index} of ${total}">${dots.join("")}</span>`;
}

function renderToday() {
  const container = $("#view-today");
  const today = localIsoDate();
  const card = heldNewCard || lastRated?.card || getPresentation(state, entries, prefs.config, today);
  saveState(state);

  if (!card.entry) {
    container.innerHTML = `<div class="card"><div class="card-front"><p class="prompt-hint">No words in deck yet.</p></div></div>`;
    return;
  }

  const entry = card.entry;
  const cousins = cousinsOf(entries, entry);
  const showBack = card.mode === "rest" || Boolean(lastRated) || Boolean(heldNewCard) || (card.mode === "review" && revealedWordId === entry.id);
  const totalToday = card.plan.reviews.length + card.plan.introduced.length;
  const doneToday = totalToday - card.reviewsRemaining - card.newRemaining;
  const counterText = totalToday > 0 ? `${Math.min(doneToday + (card.mode === "rest" ? 0 : 1), totalToday)} / ${totalToday}` : "Resting";

  const modeLabel =
    card.mode === "new" ? "New today" :
    card.mode === "review" ? (card.promptMode === "cloze" ? "Sentence cloze" : card.promptMode === "reverse" ? "Recall Malay" : "Review") :
    "Resting";

  let frontHtml = "";
  if (!showBack && card.promptMode === "cloze" && card.cloze) {
    const highlighted = escapeHtml(card.cloze).replace("___", `<span class="cloze-blank">___</span>`);
    frontHtml = `
      <div class="prompt-kicker">Fill in the blank</div>
      <p class="sentence-hero">${highlighted}</p>
      ${entry.sentenceGloss ? `<p class="prompt-hint">${escapeHtml(entry.sentenceGloss)}</p>` : ""}
    `;
  } else if (!showBack && card.promptMode === "reverse") {
    frontHtml = `
      <div class="prompt-kicker">Say in Bahasa Melayu</div>
      <p class="sentence-hero">${escapeHtml(entry.sentenceGloss || entry.gloss)}</p>
      ${entry.sentenceGloss ? `<p class="prompt-hint">Key word: ${escapeHtml(entry.gloss)}</p>` : ""}
    `;
  } else {
    frontHtml = `
      <div class="prompt-kicker">${card.mode === "new" ? "Meet a new word" : "Bahasa Melayu"}</div>
      <h1 class="lemma-hero">${escapeHtml(entry.lemma)}</h1>
      ${!showBack && entry.sentence ? `<p class="prompt-hint">${escapeHtml(entry.sentence)}</p>` : ""}
    `;
  }

  const listenBtn = (malayVoice && prefs.audio && (showBack || card.promptMode === "word"))
    ? `<button class="listen-btn" data-action="listen" data-text="${escapeHtml(showBack ? entry.sentence : entry.lemma)}">Listen (ms-MY)</button>`
    : "";

  const backHtml = showBack ? `
    <div class="card-back">
      ${card.promptMode !== "word" ? `<div class="prompt-kicker">${escapeHtml(entry.lemma)}</div>` : ""}
      <p class="gloss-main">${escapeHtml(entry.gloss)}</p>
      <div class="example-box">
        <p class="example-bm">${escapeHtml(entry.sentence)}</p>
        ${entry.sentenceGloss ? `<p class="example-en">${escapeHtml(entry.sentenceGloss)}</p>` : ""}
      </div>
      ${entry.note ? `<p class="note-line">${escapeHtml(entry.note)}</p>` : ""}
      ${cousins.length ? `
        <div class="cousins-row">
          <span>Root family (${escapeHtml(entry.root)}):</span>
          ${cousins.map((c) => `<button class="cousin-chip" data-action="open-family" data-root="${escapeHtml(entry.root)}">${escapeHtml(c)}</button>`).join("")}
        </div>
      ` : ""}
    </div>
  ` : "";

  let actionsHtml = "";
  if (lastRated) {
    const dueLabel = lastRated.state === "settled" ? "Settled!" : `Due ${lastRated.due}`;
    actionsHtml = `
      <div class="actions">
        <span class="pill pill-accent">${escapeHtml(lastRated.rating)} · ${escapeHtml(dueLabel)}</span>
        <button class="btn btn-primary" data-action="next">Next word</button>
      </div>
    `;
  } else if (heldNewCard) {
    actionsHtml = `
      <div class="actions">
        <span class="pill pill-accent">Introduced · due tomorrow</span>
        <button class="btn btn-primary" data-action="next">Continue</button>
      </div>
    `;
  } else if (!showBack) {
    actionsHtml = `
      <div class="actions">
        <button class="btn btn-primary" data-action="reveal">Reveal meaning</button>
      </div>
    `;
  } else if (card.mode === "review") {
    actionsHtml = `
      <div class="actions">
        <button class="btn btn-known" data-action="rate" data-rating="known">Known (1)</button>
        <button class="btn btn-fuzzy" data-action="rate" data-rating="fuzzy">Fuzzy (2)</button>
        <button class="btn btn-missed" data-action="rate" data-rating="missed">Missed (3)</button>
      </div>
    `;
  }

  const progressMap = new Map(state.progress.map((r) => [r.wordId, r]));
  const promptObj = settledPromptSentence(entries, progressMap);
  const restBanner = card.mode === "rest" ? `
    <div class="rest-banner">
      <span>Today's plan is complete. Rest easy until tomorrow.</span>
      ${promptObj ? `<span class="rest-sentence">"${escapeHtml(promptObj.sentence)}"</span>` : ""}
    </div>
  ` : "";

  container.innerHTML = `
    <article class="card">
      <div class="card-meta">
        <div class="meta-left">
          <span class="pill pill-accent">${escapeHtml(modeLabel)}</span>
          ${entry.register !== "neutral" ? `<span class="pill pill-casual">${escapeHtml(entry.register)}</span>` : ""}
          ${card.plan.catchUp ? `<span class="pill">catch-up</span>` : ""}
          <span>${escapeHtml(counterText)}</span>
        </div>
        ${rungDots(card.intervalIndex, card.ladderLength)}
      </div>
      <div class="card-front">
        ${frontHtml}
        ${listenBtn}
      </div>
      ${backHtml}
      ${actionsHtml}
    </article>
    ${restBanner}
  `;
}

function renderFamilies(highlightRoot = null) {
  const container = $("#view-families");
  const families = cousinFamilies(entries);
  const progressMap = new Map(state.progress.map((r) => [r.wordId, r]));

  container.innerHTML = `
    <div class="section-head">
      <h2 class="section-title">Root Families</h2>
      <p class="section-sub">${families.length} families across ${entries.length} words</p>
    </div>
    <div class="family-grid">
      ${families.map((fam) => `
        <div class="family-card" style="${highlightRoot === fam.root ? "border-color: var(--accent);" : ""}">
          <div class="family-root">
            <strong>${escapeHtml(fam.root)}</strong>
            <span class="pill">${fam.members.length} words</span>
          </div>
          <ul class="family-members">
            ${fam.members.map((m) => {
              const prog = progressMap.get(m.id);
              const badge = !prog ? "upcoming" : prog.state === "settled" ? "settled" : `rung ${prog.intervalIndex}`;
              const cls = !prog ? "" : prog.state === "settled" ? "is-settled" : "is-play";
              return `
                <li class="family-member">
                  <span><strong>${escapeHtml(m.lemma)}</strong> · ${escapeHtml(m.gloss)}</span>
                  <span class="member-state ${cls}">${badge}</span>
                </li>
              `;
            }).join("")}
          </ul>
        </div>
      `).join("")}
    </div>
  `;
}

function renderGarden() {
  const container = $("#view-garden");
  const byId = new Map(entries.map((e) => [e.id, e]));
  const settled = state.progress.filter((r) => r.state === "settled");
  const inPlay = state.progress.filter((r) => r.state === "in_play");
  const waiting = Math.max(0, entries.length - state.progress.length);
  const activeDays = new Set(state.events.map((e) => e.day)).size;

  const today = localIsoDate();
  const countsByDay = new Map();
  for (const ev of state.events) {
    if (["known", "fuzzy", "missed", "introduced"].includes(ev.kind)) {
      countsByDay.set(ev.day, (countsByDay.get(ev.day) || 0) + 1);
    }
  }
  const cells = [];
  for (let offset = 27; offset >= 0; offset--) {
    const day = addDays(today, -offset);
    const n = countsByDay.get(day) || 0;
    const lvl = n === 0 ? "" : n <= 3 ? "lvl-1" : n <= 8 ? "lvl-2" : "lvl-3";
    cells.push(`<div class="cal-cell ${lvl}" title="${day}: ${n} actions"></div>`);
  }

  const settledHtml = settled.length
    ? settled.map((r) => {
        const e = byId.get(r.wordId);
        return `<span class="word-pill"><strong>${escapeHtml(e?.lemma || r.wordId)}</strong> <span>${escapeHtml(e?.gloss || "")}</span></span>`;
      }).join("")
    : `<p class="section-sub">No settled words yet — keep climbing the 5-rung ladder!</p>`;

  const nearSettled = [...inPlay]
    .sort((a, b) => b.intervalIndex - a.intervalIndex || (a.due || "").localeCompare(b.due || ""))
    .slice(0, 16);

  container.innerHTML = `
    <div class="section-head">
      <h2 class="section-title">Garden</h2>
      <p class="section-sub">${activeDays} active days</p>
    </div>
    <div class="stats-row">
      <div class="stat-box"><div class="stat-num">${settled.length}</div><div class="stat-label">Settled</div></div>
      <div class="stat-box"><div class="stat-num">${inPlay.length}</div><div class="stat-label">In play</div></div>
      <div class="stat-box"><div class="stat-num">${waiting}</div><div class="stat-label">Waiting</div></div>
      <div class="stat-box"><div class="stat-num">${entries.length}</div><div class="stat-label">Curriculum</div></div>
    </div>
    <div class="section-head"><h3 class="section-title" style="font-size:1.05rem;">Last 28 days</h3></div>
    <div class="calendar-grid">${cells.join("")}</div>
    <div class="section-head"><h3 class="section-title" style="font-size:1.05rem;">Settled words</h3></div>
    <div class="word-list" style="margin-bottom:22px;">${settledHtml}</div>
    <div class="section-head"><h3 class="section-title" style="font-size:1.05rem;">Closest to settling</h3></div>
    <div class="word-list">
      ${nearSettled.map((r) => {
        const e = byId.get(r.wordId);
        return `<span class="word-pill"><strong>${escapeHtml(e?.lemma || r.wordId)}</strong> <span>rung ${r.intervalIndex} · due ${escapeHtml(r.due || "—")}</span></span>`;
      }).join("") || `<p class="section-sub">Start your first day in Today.</p>`}
    </div>
  `;
}

function renderSettings() {
  const container = $("#view-settings");
  const c = prefs.config;
  container.innerHTML = `
    <div class="section-head">
      <h2 class="section-title">Settings</h2>
      <p class="section-sub">Stored locally in your browser</p>
    </div>
    <div class="settings-card">
      <h3>Daily Pacing</h3>
      <div class="field-row">
        <label for="cfg-new">New words per day</label>
        <input id="cfg-new" type="number" min="0" max="10" value="${c.newPerDay}">
      </div>
      <div class="field-row">
        <label for="cfg-rev">Daily review cap</label>
        <input id="cfg-rev" type="number" min="1" max="30" value="${c.reviewCap}">
      </div>
      <div class="field-row">
        <label for="cfg-catch">Catch-up review cap (when overdue)</label>
        <input id="cfg-catch" type="number" min="1" max="50" value="${c.catchUpReviewCap}">
      </div>
      <div class="field-row">
        <label for="cfg-theme">Theme</label>
        <select id="cfg-theme">
          <option value="dark" ${prefs.theme === "dark" ? "selected" : ""}>Dark</option>
          <option value="light" ${prefs.theme === "light" ? "selected" : ""}>Light</option>
          <option value="system" ${prefs.theme === "system" ? "selected" : ""}>System</option>
        </select>
      </div>
      <div class="field-row">
        <label for="cfg-audio">Optional Malay voice button</label>
        <input id="cfg-audio" type="checkbox" ${prefs.audio ? "checked" : ""}>
      </div>
    </div>

    <div class="settings-card">
      <h3>How to Install &amp; Use</h3>
      <p class="section-sub" style="margin-bottom:10px;">
        <strong>Install as an app (works offline):</strong><br>
        • <strong>iPhone / iPad (Safari):</strong> Tap the <strong>Share</strong> button, then <strong>Add to Home Screen</strong>.<br>
        • <strong>Android (Chrome):</strong> Tap the <strong>⋮</strong> menu, then <strong>Install app</strong> (or <strong>Add to Home screen</strong>).<br>
        • <strong>Computer (Chrome / Edge):</strong> Click the <strong>Install</strong> icon in the address bar.
      </p>
      <p class="section-sub" style="margin-bottom:0;">
        <strong>Daily review:</strong> Read the Bahasa Malaysia word and sentence, tap <strong>Reveal meaning</strong>, choose <strong>Known</strong>, <strong>Fuzzy</strong>, or <strong>Missed</strong>, then tap <strong>Next word</strong>. Your progress is saved automatically in your browser.
      </p>
    </div>

    <div class="settings-card">
      <h3>Backup &amp; CLI Sync</h3>
      <p class="section-sub" style="margin-bottom:10px;">
        Compatible with <code>tepi export</code> and <code>tepi import</code> (<code>tepi-progress-v1</code>).
      </p>
      <div class="btn-row">
        <button class="btn" data-action="export-json">Export JSON snapshot</button>
        <label class="btn" style="display:inline-flex;align-items:center;">
          Import JSON snapshot
          <input id="import-file" type="file" accept="application/json" hidden>
        </label>
      </div>
    </div>
  `;
}

function switchTab(tab, highlightRoot = null) {
  activeTab = tab;
  document.querySelectorAll(".tab").forEach((btn) => {
    const active = btn.dataset.tab === tab;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".view").forEach((el) => {
    const active = el.id === `view-${tab}`;
    el.hidden = !active;
    el.classList.toggle("is-active", active);
  });
  if (tab === "today") renderToday();
  if (tab === "families") renderFamilies(highlightRoot);
  if (tab === "garden") renderGarden();
  if (tab === "settings") renderSettings();
}

function handleReveal() {
  if (lastRated || heldNewCard) return;
  const today = localIsoDate();
  const card = getPresentation(state, entries, prefs.config, today);
  if (!card.entry) return;
  if (card.mode === "review" && revealedWordId === card.entry.id) return;
  const revealed = card.revealed ? card : revealCurrent(state, entries, prefs.config, today);
  saveState(state);
  if (card.mode === "new") {
    heldNewCard = revealed;
  } else if (card.mode === "review") {
    revealedWordId = card.entry.id;
  }
  renderToday();
}

function handleRate(rating) {
  if (lastRated || heldNewCard) return;
  const today = localIsoDate();
  const card = getPresentation(state, entries, prefs.config, today);
  if (!card.entry || card.mode !== "review" || revealedWordId !== card.entry.id) return;
  const res = rateCurrent(state, entries, prefs.config, today, rating);
  if (!res) return;
  saveState(state);
  lastRated = { ...res, card: { ...card, revealed: true, intervalIndex: res.intervalIndex } };
  renderToday();
}

function handleNext() {
  lastRated = null;
  heldNewCard = null;
  revealedWordId = null;
  renderToday();
}

document.addEventListener("click", (ev) => {
  const tabBtn = ev.target.closest(".tab");
  if (tabBtn) {
    switchTab(tabBtn.dataset.tab);
    return;
  }
  const btn = ev.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  if (action === "reveal") handleReveal();
  else if (action === "rate") handleRate(btn.dataset.rating);
  else if (action === "next") handleNext();
  else if (action === "listen") speakMalay(btn.dataset.text);
  else if (action === "open-family") switchTab("families", btn.dataset.root);
  else if (action === "export-json") {
    const snap = buildSnapshot(state, prefs.config);
    const blob = new Blob([JSON.stringify(snap, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tepi-progress-${localIsoDate()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Exported progress snapshot.");
  }
});

document.addEventListener("change", async (ev) => {
  if (ev.target.id === "import-file" && ev.target.files?.[0]) {
    try {
      const text = await ev.target.files[0].text();
      const parsed = parseSnapshot(text);
      state = parsed.state;
      saveState(state);
      if (parsed.config) {
        prefs.config = parsed.config;
        savePrefs(prefs);
      }
      lastRated = null;
      heldNewCard = null;
      revealedWordId = null;
      showToast(`Imported ${state.progress.length} words.`);
      switchTab("today");
    } catch (err) {
      showToast(err.message || "Could not import snapshot.");
    }
    return;
  }
  if (["cfg-new", "cfg-rev", "cfg-catch", "cfg-theme", "cfg-audio"].includes(ev.target.id)) {
    prefs.config.newPerDay = Math.max(0, Number($("#cfg-new").value) || 0);
    prefs.config.reviewCap = Math.max(1, Number($("#cfg-rev").value) || 4);
    prefs.config.catchUpReviewCap = Math.max(prefs.config.reviewCap, Number($("#cfg-catch").value) || 12);
    prefs.theme = $("#cfg-theme").value;
    prefs.audio = $("#cfg-audio").checked;
    savePrefs(prefs);
    applyTheme();
    showToast("Settings saved.");
  }
});

document.addEventListener("keydown", (ev) => {
  if (activeTab !== "today") return;
  if (ev.target.matches("input, textarea, select")) return;
  if (ev.code === "Space") {
    ev.preventDefault();
    if (lastRated || heldNewCard) handleNext();
    else handleReveal();
  } else if (ev.key === "1") {
    handleRate("known");
  } else if (ev.key === "2") {
    handleRate("fuzzy");
  } else if (ev.key === "3") {
    handleRate("missed");
  }
});

async function boot() {
  applyTheme();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  try {
    entries = await loadCurriculum();
    detectMalayVoice();
    renderToday();
  } catch (err) {
    $("#view-today").innerHTML = `<div class="card"><div class="card-front"><p class="prompt-hint">${escapeHtml(err.message)}</p></div></div>`;
  }
}

boot();
