import { useEffect, useRef, useState } from "react";

const EXAMPLES = [
  "How does CRISPR-Cas9 work?",
  "Compare quantum computing approaches",
  "Impact of climate change on ocean biodiversity",
];

interface Props {
  onSubmit: (q: string) => void;
  disabled?: boolean;
}

export function QueryInput({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 240) + "px";
  }, [value]);

  const submit = () => {
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
  };

  return (
    <div className="glass p-2 shadow-2xl" style={{ boxShadow: "var(--shadow-elevated)" }}>
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
        }}
        disabled={disabled}
        rows={3}
        placeholder="Ask a research question — e.g. 'What are the latest advances in fusion energy?'"
        aria-label="Research query"
        className="w-full resize-none bg-transparent px-4 py-4 text-base outline-none placeholder:text-muted-foreground/70 disabled:opacity-60"
      />
      <div className="flex items-center justify-between px-3 pb-2 pt-1">
        <div className="text-xs text-muted-foreground">
          {value.length} chars ·{" "}
          <kbd className="rounded border border-border px-1.5 py-0.5 text-[10px]">
            Ctrl
          </kbd>{" "}
          +{" "}
          <kbd className="rounded border border-border px-1.5 py-0.5 text-[10px]">
            Enter
          </kbd>{" "}
          to submit
        </div>
        <button
          className="btn-primary"
          onClick={submit}
          disabled={disabled || !value.trim()}
        >
          {disabled ? (
            <>
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70 animate-pulse-dot" />
                <span
                  className="h-1.5 w-1.5 rounded-full bg-current opacity-70 animate-pulse-dot"
                  style={{ animationDelay: "0.2s" }}
                />
                <span
                  className="h-1.5 w-1.5 rounded-full bg-current opacity-70 animate-pulse-dot"
                  style={{ animationDelay: "0.4s" }}
                />
              </span>
              Researching…
            </>
          ) : (
            <>Run Research →</>
          )}
        </button>
      </div>

      <div className="flex flex-wrap gap-2 px-3 pb-3 pt-1 border-t border-border/60 mt-1">
        <span className="text-xs text-muted-foreground self-center mr-1">Try:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            disabled={disabled}
            onClick={() => setValue(ex)}
            className="chip"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
