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
      <aside className="w-60 border-r border-[var(--border)] bg-[var(--card)] flex flex-col">
        <div className="p-5 border-b border-[var(--border)]">
          <div className="flex items-center gap-3">
            <Wind className="w-7 h-7 text-[var(--primary)]" />
            <div>
              <h1 className="text-base font-bold m-0">OpenFOAM GUI</h1>
              <p className="text-xs text-[var(--muted-foreground)] m-0">
                CFD Made Simple
              </p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3">
          {navItems.map(({ path, label, icon: Icon, end }) => (
            <NavLink
              key={path}
              to={path}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 no-underline transition-colors text-sm font-medium",
                  isActive
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
                )
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-[var(--border)] flex items-center gap-2">
          <Box
            className={cn(
              "w-4 h-4",
              docker?.connected
                ? "text-[var(--success)]"
                : "text-[var(--destructive)]"
            )}
          />
          <span className="text-xs text-[var(--muted-foreground)]">
            {docker?.connected ? "Docker connected" : "Docker offline"}
          </span>
        </div>
      </aside>

      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
