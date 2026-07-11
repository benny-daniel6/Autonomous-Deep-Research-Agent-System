import { useMemo, useState } from "react";
import type { BenchmarkResult } from "@/types/api";
import { fmtSecs, scorePct, scoreTier, truncate } from "@/utils/formatters";

interface Props {
  rows: BenchmarkResult[];
}

type SortKey = "quality_score" | "latency_s" | "category" | "status";

export function BenchmarkTable({ rows }: Props) {
  const [filter, setFilter] = useState<string | null>(null);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({
    key: "quality_score",
    dir: -1,
  });

  const categories = useMemo(
    () => Array.from(new Set(rows.map((r) => r.category))).sort(),
    [rows],
  );

  const filtered = useMemo(() => {
    const f = filter ? rows.filter((r) => r.category === filter) : rows;
    return [...f].sort((a, b) => {
      const va = a[sort.key] as any;
      const vb = b[sort.key] as any;
      if (typeof va === "number") return (va - vb) * sort.dir;
      return String(va).localeCompare(String(vb)) * sort.dir;
    });
  }, [rows, filter, sort]);

  const setSortKey = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: (-s.dir) as 1 | -1 } : { key, dir: -1 }));

  return (
    <div className="glass overflow-hidden">
      <div className="p-4 border-b border-border/60 flex flex-wrap gap-2 items-center">
        <button
          onClick={() => setFilter(null)}
          className="chip"
          style={
            filter === null
              ? { color: "var(--color-foreground)", borderColor: "var(--color-primary)", background: "oklch(0.62 0.19 275 / 0.15)" }
              : undefined
          }
        >
          All ({rows.length})
        </button>
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setFilter(c)}
            className="chip"
            style={
              filter === c
                ? { color: "var(--color-foreground)", borderColor: "var(--color-primary)", background: "oklch(0.62 0.19 275 / 0.15)" }
                : undefined
            }
          >
            {c}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground border-b border-border/60">
              <th className="px-4 py-3">Query</th>
              <Th onClick={() => setSortKey("category")}>Category</Th>
              <Th onClick={() => setSortKey("status")}>Status</Th>
              <Th onClick={() => setSortKey("quality_score")}>Quality</Th>
              <Th onClick={() => setSortKey("latency_s")}>Latency</Th>
              <th className="px-4 py-3">Cache</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => {
              const tier = scoreTier(r.quality_score);
              const c =
                tier === "high"
                  ? "var(--color-success)"
                  : tier === "med"
                    ? "var(--color-warning)"
                    : "var(--color-danger)";
              const ok = r.status.toLowerCase() === "success";
              return (
                <tr
                  key={i}
                  className="border-b border-border/40 hover:bg-white/[0.02] transition-colors"
                >
                  <td className="px-4 py-3 max-w-[340px]" title={r.query}>
                    {truncate(r.query, 70)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{r.category}</td>
                  <td className="px-4 py-3">
                    <span
                      className="px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{
                        color: ok ? "var(--color-success)" : "var(--color-danger)",
                        background: ok
                          ? "oklch(0.70 0.17 160 / 0.12)"
                          : "oklch(0.65 0.22 25 / 0.12)",
                      }}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-20 rounded-full bg-white/5 overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${r.quality_score * 100}%`,
                            background: c,
                          }}
                        />
                      </div>
                      <span className="font-mono text-xs" style={{ color: c }}>
                        {scorePct(r.quality_score)}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {fmtSecs(r.latency_s)}
                  </td>
                  <td className="px-4 py-3">
                    {r.from_memory ? (
                      <span className="text-xs" style={{ color: "var(--color-accent)" }}>
                        cached
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                  No results.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <th className="px-4 py-3">
      <button
        className="uppercase tracking-wider text-xs text-muted-foreground hover:text-foreground transition-colors"
        onClick={onClick}
      >
        {children} ⇅
      </button>
    </th>
  );
}
