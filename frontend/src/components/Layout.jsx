import { Outlet, NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Wind,
  Home,
  FolderOpen,
  Plus,
  GitCompareArrows,
  LayoutTemplate,
  FlaskConical,
  Settings as SettingsIcon,
  Box,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const navItems = [
  { path: "/", label: "Dashboard", icon: Home, end: true },
  { path: "/cases", label: "Cases", icon: FolderOpen, end: true },
  { path: "/cases/new", label: "New Case", icon: Plus, end: true },
  { path: "/sweeps", label: "Sweeps", icon: GitCompareArrows, end: false },
  { path: "/templates", label: "Templates", icon: LayoutTemplate, end: false },
  { path: "/benchmarks", label: "Benchmarks", icon: FlaskConical, end: false },
  { path: "/settings", label: "Settings", icon: SettingsIcon, end: false },
];

export function Layout() {
  const { data: docker } = useQuery({
    queryKey: ["docker-status"],
    queryFn: api.dockerStatus,
    refetchInterval: 30000,
    retry: false,
  });

  return (
    <div className="flex h-screen">
      {/* Below lg the sidebar collapses to icons — a fixed 240px rail used to
          squeeze the content column to nothing in a narrow window. */}
      <aside className="w-14 lg:w-60 shrink-0 border-r border-[var(--border)] bg-[var(--card)] flex flex-col">
        <div className="p-3 lg:p-5 border-b border-[var(--border)]">
          <div className="flex items-center gap-3 justify-center lg:justify-start">
            <Wind className="w-7 h-7 shrink-0 text-[var(--primary)]" />
            <div className="hidden lg:block">
              <h1 className="text-base font-bold m-0">OpenFOAM GUI</h1>
              <p className="text-xs text-[var(--muted-foreground)] m-0">
                CFD Made Simple
              </p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-2 lg:p-3">
          {navItems.map(({ path, label, icon: Icon, end }) => (
            <NavLink
              key={path}
              to={path}
              end={end}
              title={label}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 no-underline transition-colors text-sm font-medium",
                  "justify-center lg:justify-start",
                  isActive
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-3 lg:p-4 border-t border-[var(--border)] flex items-center gap-2 justify-center lg:justify-start">
          <Box
            title={docker?.connected ? "Docker connected" : "Docker offline"}
            className={cn(
              "w-4 h-4 shrink-0",
              docker?.connected
                ? "text-[var(--success)]"
                : "text-[var(--destructive)]"
            )}
          />
          <span className="hidden lg:inline text-xs text-[var(--muted-foreground)]">
            {docker?.connected ? "Docker connected" : "Docker offline"}
          </span>
        </div>
      </aside>

      {/* min-w-0 so wide children (tables, canvas) shrink instead of pushing the page */}
      <main className="flex-1 min-w-0 overflow-auto p-4 lg:p-8">
        <Outlet />
      </main>
    </div>
  );
}
