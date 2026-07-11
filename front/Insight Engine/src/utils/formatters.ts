export function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export function scorePct(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function scoreTier(score: number): "high" | "med" | "low" {
  if (score >= 0.8) return "high";
  if (score >= 0.5) return "med";
  return "low";
}

export function truncate(s: string, n = 80): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export function fmtSecs(s: number): string {
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}m ${r}s`;
}
