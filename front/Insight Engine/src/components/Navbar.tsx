import { Link } from "@tanstack/react-router";
import { HealthIndicator } from "./HealthIndicator";

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 backdrop-blur-xl bg-background/60">
      <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 group">
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center text-primary-foreground font-bold"
            style={{ background: "var(--gradient-primary)" }}
          >
            D
          </div>
          <span className="font-semibold tracking-tight">
            Deep <span className="gradient-text">Research</span>
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          <Link
            to="/"
            className="px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-foreground transition-colors"
            activeProps={{ className: "px-3 py-2 rounded-md text-sm text-foreground bg-white/5" }}
            activeOptions={{ exact: true }}
          >
            Research
          </Link>
          <Link
            to="/dashboard"
            className="px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-foreground transition-colors"
            activeProps={{ className: "px-3 py-2 rounded-md text-sm text-foreground bg-white/5" }}
          >
            Dashboard
          </Link>
          <div className="ml-3">
            <HealthIndicator />
          </div>
        </nav>
      </div>
    </header>
  );
}
