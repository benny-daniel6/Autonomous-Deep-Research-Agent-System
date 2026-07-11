import type { Stage } from "@/hooks/useResearch";

interface Props {
  stages: Stage[];
  elapsed: number;
  waitingFinal: boolean;
}

const TOTAL_ESTIMATED = 26.5;

export function PipelineVisualizer({ stages, elapsed, waitingFinal }: Props) {
  const completed = stages.filter((s) => s.status === "complete").length;
  const pct = Math.min(100, (completed / stages.length) * 100);
  const remaining = Math.max(0, TOTAL_ESTIMATED - elapsed);

  return (
    <div className="glass p-6 animate-fade-in-up">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-sm text-muted-foreground">Pipeline Status</div>
          <div className="text-lg font-semibold">
            {waitingFinal ? "Finalizing report…" : "Running agents"}
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-2xl font-semibold gradient-text">
            {formatClock(elapsed)}
          </div>
          <div className="text-xs text-muted-foreground">
            {waitingFinal
              ? "waiting on API"
              : `~${Math.ceil(remaining)}s remaining`}
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 rounded-full bg-white/5 overflow-hidden mb-8 relative">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: "var(--gradient-primary)",
            boxShadow: "var(--shadow-glow)",
          }}
        />
        {waitingFinal && <div className="absolute inset-0 shimmer" />}
      </div>

      {/* Stepper */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4 relative">
        {stages.map((s, i) => (
          <StageNode key={s.key} stage={s} index={i} />
        ))}
      </div>
    </div>
  );
}

function StageNode({ stage, index }: { stage: Stage; index: number }) {
  const { status, icon, label } = stage;

  const bg =
    status === "complete"
      ? "var(--color-success)"
      : status === "active"
        ? "var(--color-primary)"
        : status === "error"
          ? "var(--color-danger)"
          : "oklch(1 0 0 / 0.05)";

  return (
    <div
      className="flex flex-col items-center text-center gap-2 animate-fade-in-up"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div
        className={`relative h-14 w-14 rounded-2xl flex items-center justify-center text-2xl transition-all ${
          status === "active" ? "animate-pulse-glow" : ""
        }`}
        style={{
          background:
            status === "pending"
              ? "oklch(1 0 0 / 0.04)"
              : status === "active"
                ? "oklch(0.62 0.19 275 / 0.2)"
                : status === "complete"
                  ? "oklch(0.70 0.17 160 / 0.15)"
                  : "oklch(0.65 0.22 25 / 0.15)",
          border: `1px solid ${status === "pending" ? "var(--color-border)" : bg}`,
        }}
      >
        {status === "complete" ? (
          <span style={{ color: "var(--color-success)" }}>✓</span>
        ) : status === "error" ? (
          <span style={{ color: "var(--color-danger)" }}>✕</span>
        ) : (
          <span>{icon}</span>
        )}
      </div>
      <div
        className={`text-xs font-medium ${
          status === "pending" ? "text-muted-foreground" : "text-foreground"
        }`}
      >
        {label}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {status}
      </div>
    </div>
  );
}

function formatClock(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
