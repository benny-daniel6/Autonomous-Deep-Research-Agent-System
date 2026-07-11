const NODES = [
  { icon: "🔍", label: "Memory Check", desc: "Vector cache lookup" },
  { icon: "📋", label: "Planner", desc: "Decompose into subtasks" },
  { icon: "🌐", label: "Search Workers", desc: "Parallel web retrieval" },
  { icon: "📝", label: "Summarizers", desc: "Distill findings" },
  { icon: "🔬", label: "Critic", desc: "Verdict: PASS / REVISE / FAIL" },
  { icon: "📄", label: "Report Compiler", desc: "Cited final report" },
];

export function ArchitectureDiagram() {
  return (
    <div className="glass p-6">
      <div className="mb-6">
        <h3 className="text-lg font-semibold">Agent Architecture</h3>
        <p className="text-sm text-muted-foreground mt-1">
          LangGraph state machine · 5 specialized agents · critic-refinement loop
        </p>
      </div>

      <div className="relative">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {NODES.map((n, i) => (
            <div
              key={n.label}
              className="glass-hover glass p-4 flex items-start gap-3 animate-fade-in-up"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div
                className="h-10 w-10 shrink-0 rounded-xl flex items-center justify-center text-lg"
                style={{
                  background: "oklch(0.62 0.19 275 / 0.15)",
                  border: "1px solid oklch(0.62 0.19 275 / 0.3)",
                }}
              >
                {n.icon}
              </div>
              <div className="min-w-0">
                <div className="text-xs text-muted-foreground font-mono">
                  0{i + 1}
                </div>
                <div className="font-semibold text-sm">{n.label}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {n.desc}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 p-3 rounded-lg text-xs text-muted-foreground border border-dashed border-border">
          On <span style={{ color: "var(--color-warning)" }}>REVISE</span>, the
          critic feeds a refined query back into the planner — up to N loops
          before compiling the final report.
        </div>
      </div>
    </div>
  );
}
