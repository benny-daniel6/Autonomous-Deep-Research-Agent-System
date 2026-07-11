import type { HistoryEntry, Report } from "@/types/api";

const HISTORY_KEY = "dra_history_v1";
const LAST_REPORT_KEY = "dra_last_report_v1";

export function loadHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

export function pushHistory(entry: HistoryEntry) {
  if (typeof window === "undefined") return;
  const list = loadHistory();
  const next = [entry, ...list].slice(0, 10);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
}

export function saveLastReport(r: Report) {
  if (typeof window === "undefined") return;
  localStorage.setItem(LAST_REPORT_KEY, JSON.stringify(r));
}

export function loadLastReport(): Report | null {
  if (typeof window === "undefined") return null;
  try {
    const s = localStorage.getItem(LAST_REPORT_KEY);
    return s ? JSON.parse(s) : null;
  } catch {
    return null;
  }
}
