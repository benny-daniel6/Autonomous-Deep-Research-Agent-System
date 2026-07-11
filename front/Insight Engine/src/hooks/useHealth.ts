import { useEffect, useState } from "react";
import { checkHealth } from "@/api/client";
import type { HealthResponse } from "@/types/api";

export function useHealth(intervalMs = 30_000) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const r = await checkHealth();
        if (!cancelled) {
          setHealth(r);
          setError(null);
          setLastChecked(new Date());
        }
      } catch (e: any) {
        if (!cancelled) {
          setHealth({ status: "error", detail: e.message });
          setError(e.message);
          setLastChecked(new Date());
        }
      }
    }
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return { health, lastChecked, error };
}
