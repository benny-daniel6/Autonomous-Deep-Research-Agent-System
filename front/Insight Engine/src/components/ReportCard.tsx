import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Report } from "@/types/api";
import { formatDate, scorePct, scoreTier } from "@/utils/formatters";

interface Props {
  report: Report;
}

export function ReportCard({ report }: Props) {
  const [copied, setCopied] = useState(false);

  const toMarkdown = () => {
    const parts: string[] = [`# ${report.title}`, ""];
    for (const s of report.sections) {
      parts.push(`## ${s.heading}`, "", s.content, "");
      if (s.supporting_sources.length) {
        parts.push("**Sources:**");
        s.supporting_sources.forEach((u) => parts.push(`- ${u}`));
        parts.push("");
      }
    }
    if (report.citations.length) {
      parts.push("## References");
      report.citations.forEach((u, i) => parts.push(`${i + 1}. ${u}`));
    }
    return parts.join("\n");
  };

  const download = () => {
    const blob = new Blob([toMarkdown()], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.title.replace(/[^a-z0-9]+/gi, "_").slice(0, 60)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copy = async () => {
    await navigator.clipboard.writeText(toMarkdown());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const tier = scoreTier(report.quality_score);
  const tierColor =
    tier === "high"
      ? "var(--color-success)"
      : tier === "med"
        ? "var(--color-warning)"
        : "var(--color-danger)";

  return (
    <article className="glass animate-fade-in-up overflow-hidden">
      <header className="sticky top-16 z-10 backdrop-blur-xl bg-background/95 border-b border-border/60 px-6 py-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            {report.title}
          </h1>
          <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
            <span>Generated {formatDate(report.generated_at)}</span>
            <span>·</span>
            <span>{report.sections.length} sections</span>
            <span>·</span>
            <span>{report.citations.length} citations</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border"
            style={{
              color: tierColor,
              borderColor: tierColor,
              background: `color-mix(in oklab, ${tierColor} 12%, transparent)`,
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: tierColor }}
            />
            Quality {scorePct(report.quality_score)}
          </div>
          <button className="btn-ghost text-sm" onClick={copy}>
            {copied ? "Copied ✓" : "Copy"}
          </button>
          <button className="btn-ghost text-sm" onClick={download}>
            ↓ Markdown
          </button>
        </div>
      </header>

      <div className="p-6 md:p-8 space-y-8">
        {report.sections.map((s, i) => (
          <SectionBlock key={i} index={i} section={s} />
        ))}

        {report.citations.length > 0 && (
          <section className="pt-6 border-t border-border/60">
            <h2 className="text-lg font-semibold mb-4">References</h2>
            <ol className="space-y-2 text-sm">
              {report.citations.map((url, i) => (
                <li key={i} className="flex gap-3">
                  <span className="text-muted-foreground font-mono">
                    [{i + 1}]
                  </span>
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all hover:underline"
                    style={{ color: "var(--color-accent)" }}
                  >
                    {url}
                  </a>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </article>
  );
}

function SectionBlock({
  section,
  index,
}: {
  section: Report["sections"][number];
  index: number;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section
      className="animate-fade-in-up"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <h2 className="text-xl md:text-2xl font-bold mb-4">{section.heading}</h2>
      <div className="prose-custom">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {section.content}
        </ReactMarkdown>
      </div>
      {section.supporting_sources.length > 0 && (
        <div className="mt-4 rounded-lg border border-border/70 bg-white/[0.02]">
          <button
            onClick={() => setOpen((o) => !o)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-sm hover:bg-white/[0.02] rounded-lg"
          >
            <span className="text-muted-foreground">
              {section.supporting_sources.length} supporting source
              {section.supporting_sources.length !== 1 ? "s" : ""}
            </span>
            <span
              className="transition-transform"
              style={{ transform: open ? "rotate(180deg)" : "none" }}
            >
              ▾
            </span>
          </button>
          {open && (
            <ul className="px-4 pb-3 space-y-1.5 text-sm">
              {section.supporting_sources.map((u, i) => (
                <li key={i}>
                  <a
                    href={u}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all hover:underline"
                    style={{ color: "var(--color-accent)" }}
                  >
                    {u}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
