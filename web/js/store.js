import { DEFAULT_CONFIG, EXPORT_FORMAT } from "./engine.js";

const STATE_KEY = "tepi.state.v1";
const PREFS_KEY = "tepi.prefs.v1";

export function loadState() {
  try {
    const raw = JSON.parse(localStorage.getItem(STATE_KEY) || "null");
    if (raw && Array.isArray(raw.progress) && Array.isArray(raw.events) && Array.isArray(raw.plans)) {
      return raw;
    }
  } catch {
    // ignore corrupt storage
  }
  return { progress: [], events: [], plans: [] };
}

export function saveState(state) {
  localStorage.setItem(STATE_KEY, JSON.stringify(state));
}

export function loadPrefs() {
  try {
    const raw = JSON.parse(localStorage.getItem(PREFS_KEY) || "null");
    if (raw && typeof raw === "object") {
      return {
        config: { ...DEFAULT_CONFIG, ...(raw.config || {}) },
        theme: raw.theme || "dark",
        audio: raw.audio !== false,
      };
    }
  } catch {
    // ignore
  }
  return { config: { ...DEFAULT_CONFIG }, theme: "dark", audio: true };
}

export function savePrefs(prefs) {
  localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
}

export function buildSnapshot(state, config) {
  return {
    format: EXPORT_FORMAT,
    exportedAt: new Date().toISOString(),
    config: { ...config },
    progress: state.progress,
    events: state.events,
    plans: state.plans,
  };
}

export function parseSnapshot(text) {
  const payload = JSON.parse(text);
  if (!payload || payload.format !== EXPORT_FORMAT) {
    throw new Error(`Expected a ${EXPORT_FORMAT} JSON snapshot.`);
  }
  if (!Array.isArray(payload.progress)) {
    throw new Error("Snapshot is missing progress list.");
  }
  return {
    state: {
      progress: payload.progress,
      events: Array.isArray(payload.events) ? payload.events : [],
      plans: Array.isArray(payload.plans) ? payload.plans : [],
    },
    config: payload.config ? { ...DEFAULT_CONFIG, ...payload.config } : null,
  };
}
