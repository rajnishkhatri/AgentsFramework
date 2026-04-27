import Link from "next/link";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/", icon: "chart" },
  { label: "Trace Explorer", href: "/traces", icon: "search" },
  { label: "Guardrail Monitor", href: "/guardrails", icon: "shield" },
  { label: "Decision Audit", href: "/decisions", icon: "brain" },
  { label: "Compliance Center", href: "/compliance", icon: "clipboard" },
  { label: "Agent Registry", href: "/agents", icon: "user" },
  { label: "Log Viewer", href: "/logs", icon: "file" },
] as const;

export function Sidebar() {
  return (
    <aside className={cn("flex h-screen w-64 flex-col border-r border-border bg-card")}>
      <div className="flex h-14 items-center border-b border-border px-4">
        <h1 className="text-lg font-semibold text-foreground">
          Explainability
        </h1>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center rounded-md px-3 py-2 text-sm font-medium",
              "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              "transition-colors"
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="border-t border-border p-4">
        <span className="text-xs text-muted-foreground">Settings</span>
      </div>
    </aside>
  );
}
