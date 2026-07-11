import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArchitectureDiagram } from "@/components/ArchitectureDiagram";
import { BenchmarkTable } from "@/components/BenchmarkTable";
import { getBenchmarks } from "@/api/client";
import type { BenchmarkResult, HistoryEntry } from "@/types/api";
import { loadHistory } from "@/utils/storage";
import { useHealth } from "@/hooks/useHealth";
import { fmtSecs, formatDate, scorePct, scoreTier } from "@/utils/formatters";

export const Route = createFileRoute("/dashboard")({
  component: DashboardPage,
});

function DashboardPage() {
  const [rows, setRows] = useState<BenchmarkResult[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const { health, lastChecked } = useHealth();

  useEffect(() => {
    setHistory(loadHistory());
    getBenchmarks()
      .then(setRows)
      .catch((e) => setErr(e.message));
  }, []);

  const stats = rows ? computeStats(rows) : null;

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 space-y-8">
      <header className="animate-fade-in-up">
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
          Dashboard
        </h1>
        <p className="text-muted-foreground mt-1">
          System health, benchmark performance, and pipeline architecture.
        </p>
      </header>

      {/* Health + summary stats */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="API Status"
          value={
            <span
              style={{
                color:
                  health?.status === "ok"
                    ? "var(--color-success)"
                    : "var(--color-danger)",
              }}
            >
              {health?.status === "ok" ? "Online" : "Offline"}
            </span>
          }
          hint={lastChecked ? `checked ${lastChecked.toLocaleTimeString()}` : "…"}
        />
        <StatCard
          label="Cached Reports"
          value={health?.memory_count ?? "—"}
          hint="ChromaDB"
        />
        <StatCard
          label="Completion Rate"
          value={stats ? `${Math.round(stats.completion * 100)}%` : "—"}
          hint={stats ? `${stats.successes} / ${stats.total} runs` : ""}
        />
        <StatCard
          label="Avg Quality"
          value={stats ? scorePct(stats.avgQuality) : "—"}
          hint={stats ? `avg ${fmtSecs(stats.avgLatency)} latency` : ""}
        />
      </section>

      {/* Architecture */}
      <ArchitectureDiagram />

      {/* Benchmarks */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold">Benchmark Results</h2>
          {rows && (
            <span className="text-xs text-muted-foreground">
              {rows.length} runs
            </span>
          )}
        </div>
        {err && (
          <div className="glass p-4 text-sm text-muted-foreground">
            Unable to load benchmarks: {err}
          </div>
        )}
        {!err && !rows && (
          <div className="glass p-8 text-center text-sm text-muted-foreground">
            Loading benchmarks…
          </div>
        )}
        {rows && rows.length === 0 && (
          <div className="glass p-8 text-center text-sm text-muted-foreground">
            No benchmark data yet.
          </div>
        )}
        {rows && rows.length > 0 && <BenchmarkTable rows={rows} />}
      </section>

      {/* History */}
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Recent Queries</h2>
        {history.length === 0 ? (
          <div className="glass p-8 text-center text-sm text-muted-foreground">
            No queries yet — run one from the{" "}
            <a href="/" className="underline">
              research page
            </a>
            .
          </div>
        ) : (
          <div className="glass divide-y divide-border/50">
            {history.map((h, i) => {
              const tier = scoreTier(h.quality_score);
              const c =
                tier === "high"
                  ? "var(--color-success)"
                  : tier === "med"
                    ? "var(--color-warning)"
                    : "var(--color-danger)";
              return (
                <div
                  key={i}
                  className="p-4 flex items-center justify-between gap-4"
                >
                  <div className="min-w-0">
                    <div className="font-medium truncate">{h.title}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {h.query}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-xs shrink-0">
                    <span className="font-mono" style={{ color: c }}>
                      {scorePct(h.quality_score)}
                    </span>
                    <span className="text-muted-foreground">
                      {formatDate(h.generated_at)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="glass glass-hover p-5">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-2 text-2xl md:text-3xl font-bold">{value}</div>
      {hint && (
        <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
      )}
    </div>
  );
}

function computeStats(rows: BenchmarkResult[]) {
  const total = rows.length;
  const successes = rows.filter((r) => r.status.toLowerCase() === "success").length;
  const avgQuality =
    rows.reduce((s, r) => s + r.quality_score, 0) / Math.max(1, total);
  const avgLatency =
    rows.reduce((s, r) => s + r.latency_s, 0) / Math.max(1, total);
  return { total, successes, completion: successes / total, avgQuality, avgLatency };
}
