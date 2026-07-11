import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { QueryInput } from "@/components/QueryInput";
import { PipelineVisualizer } from "@/components/PipelineVisualizer";
import { ReportCard } from "@/components/ReportCard";
import { useResearch } from "@/hooks/useResearch";
import { loadLastReport } from "@/utils/storage";

export const Route = createFileRoute("/")({
  component: HomePage,
});

function HomePage() {
  const { stages, running, waitingFinal, elapsed, report, error, start, setReport } =
    useResearch();
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
    if (!report) {
      const cached = loadLastReport();
      if (cached) setReport(cached);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-12 md:py-20 space-y-10">
      {/* Hero */}
      <section className="text-center space-y-5 animate-fade-in-up">
        <div className="inline-flex items-center gap-2 chip">
          <span
            className="h-1.5 w-1.5 rounded-full animate-pulse-dot"
            style={{ background: "var(--color-accent)" }}
          />
          Multi-agent research pipeline
        </div>
        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight leading-[1.05]">
          Deep Research,
          <br />
          <span className="gradient-text">Autonomously.</span>
        </h1>
        <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
          Ask any research question. Five specialized AI agents plan, search,
          summarize, critique, and compile a cited report — automatically.
        </p>
      </section>

      {/* Query */}
      <section className="animate-fade-in-up" style={{ animationDelay: "120ms" }}>
        <QueryInput onSubmit={start} disabled={running} />
      </section>

      {/* Pipeline */}
      {(running || waitingFinal) && hydrated && (
        <PipelineVisualizer
          stages={stages}
          elapsed={elapsed}
          waitingFinal={waitingFinal}
        />
      )}

      {/* Error */}
      {error && !running && (
        <div
          className="glass p-6 animate-fade-in-up"
          style={{ borderColor: "var(--color-danger)" }}
        >
          <div
            className="text-sm font-semibold mb-1"
            style={{ color: "var(--color-danger)" }}
          >
            Research failed
          </div>
          <div className="text-sm text-muted-foreground">{error}</div>
          <div className="mt-3 text-xs text-muted-foreground">
            Check that the FastAPI backend is running at{" "}
            <code className="font-mono">http://localhost:8000</code>.
          </div>
        </div>
      )}

      {/* Report */}
      {report && !running && <ReportCard report={report} />}

      {!report && !running && !error && (
        <div className="text-center text-sm text-muted-foreground pt-8">
          Reports typically complete in 15–180 seconds.
        </div>
      )}
    </div>
  );
}
