import { useCallback, useEffect, useRef, useState } from "react";
import { runResearch } from "@/api/client";
import type { Report } from "@/types/api";
import { pushHistory, saveLastReport } from "@/utils/storage";

export type StageStatus = "pending" | "active" | "complete" | "error";

export interface Stage {
  key: string;
  label: string;
  icon: string;
  status: StageStatus;
  detail?: string;
}

const INITIAL_STAGES: Stage[] = [
  { key: "memory", label: "Memory Check", icon: "🔍", status: "pending" },
  { key: "plan", label: "Planning", icon: "📋", status: "pending" },
  { key: "search", label: "Searching", icon: "🌐", status: "pending" },
  { key: "summarize", label: "Summarizing", icon: "📝", status: "pending" },
  { key: "critic", label: "Critic Review", icon: "🔬", status: "pending" },
  { key: "report", label: "Compiling Report", icon: "📄", status: "pending" },
];

// Simulated durations (ms) for each stage.
const STAGE_DURATIONS: Record<string, number> = {
  memory: 1500,
  plan: 4000,
  search: 8000,
  summarize: 6500,
  critic: 4000,
  report: 2500,
};

export function useResearch() {
  const [stages, setStages] = useState<Stage[]>(INITIAL_STAGES);
  const [running, setRunning] = useState(false);
  const [waitingFinal, setWaitingFinal] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timers = useRef<Array<ReturnType<typeof setTimeout>>>([]);
  const startedAt = useRef<number>(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearAll = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
  };

  useEffect(() => () => clearAll(), []);

  const runProgress = useCallback(() => {
    let acc = 0;
    INITIAL_STAGES.forEach((stage, idx) => {
      const startAt = acc;
      timers.current.push(
        setTimeout(() => {
          setStages((prev) =>
            prev.map((s, i) =>
              i === idx
                ? { ...s, status: "active" }
                : i < idx
                  ? { ...s, status: "complete" }
                  : s,
            ),
          );
        }, startAt),
      );
      acc += STAGE_DURATIONS[stage.key];
      timers.current.push(
        setTimeout(() => {
          setStages((prev) =>
            prev.map((s, i) =>
              i === idx ? { ...s, status: "complete" } : s,
            ),
          );
          if (idx === INITIAL_STAGES.length - 1) {
            setWaitingFinal(true);
          }
        }, acc),
      );
    });
  }, []);

  const start = useCallback(
    async (query: string) => {
      if (running) return;
      clearAll();
      setError(null);
      setReport(null);
      setStages(INITIAL_STAGES.map((s) => ({ ...s, status: "pending" })));
      setRunning(true);
      setWaitingFinal(false);
      setElapsed(0);
      startedAt.current = Date.now();
      tickRef.current = setInterval(() => {
        setElapsed((Date.now() - startedAt.current) / 1000);
      }, 100);
      runProgress();

      try {
        const r = await runResearch(query);
        // snap all to complete
        setStages((prev) => prev.map((s) => ({ ...s, status: "complete" })));
        setWaitingFinal(false);
        setReport(r);
        saveLastReport(r);
        pushHistory({
          query,
          title: r.title,
          quality_score: r.quality_score,
          generated_at: r.generated_at,
        });
      } catch (e: any) {
        setStages((prev) =>
          prev.map((s) =>
            s.status === "active" || s.status === "pending"
              ? { ...s, status: "error" }
              : s,
          ),
        );
        setError(e.message || "Request failed");
      } finally {
        clearAll();
        setRunning(false);
      }
    },
    [running, runProgress],
  );

  const reset = useCallback(() => {
    clearAll();
    setStages(INITIAL_STAGES);
    setReport(null);
    setError(null);
    setRunning(false);
    setWaitingFinal(false);
    setElapsed(0);
  }, []);

  return { stages, running, waitingFinal, elapsed, report, error, start, reset, setReport };
}
