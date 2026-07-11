import { useHealth } from "@/hooks/useHealth";

export function HealthIndicator() {
  const { health, lastChecked } = useHealth();
  const ok = health?.status === "ok";

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border border-border bg-white/[0.03]"
      title={
        lastChecked
          ? `${ok ? "Online" : "Offline"} · ${health?.memory_count ?? 0} cached · checked ${lastChecked.toLocaleTimeString()}`
          : "Checking..."
      }
    >
      <span className="relative flex h-2 w-2">
        {ok && (
          <span
            className="absolute inline-flex h-full w-full rounded-full opacity-75 animate-pulse-dot"
            style={{ backgroundColor: "var(--color-success)" }}
          />
        )}
        <span
          className="relative inline-flex rounded-full h-2 w-2"
          style={{
            backgroundColor: ok ? "var(--color-success)" : "var(--color-danger)",
          }}
        />
      </span>
      <span className="text-muted-foreground">
        {ok ? `API · ${health?.memory_count ?? 0} cached` : "API offline"}
      </span>
    </div>
  );
}
