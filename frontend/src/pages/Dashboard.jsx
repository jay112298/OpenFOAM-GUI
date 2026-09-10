import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";

export function Dashboard() {
  const { data: docker } = useQuery({
    queryKey: ["docker-status"],
    queryFn: api.dockerStatus,
    retry: false,
  });
  const { data: cases = [] } = useQuery({
    queryKey: ["cases"],
    queryFn: api.listCases,
    retry: false,
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold m-0">Dashboard</h1>
          <p className="text-[var(--muted-foreground)] mt-1 mb-0">
            System status and recent activity
          </p>
        </div>
        <Link
          to="/cases/new"
          className="flex items-center gap-2 px-5 py-3 bg-[var(--primary)] text-white rounded-lg no-underline font-medium hover:opacity-90"
        >
          <Plus className="w-5 h-5" />
          New Case
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatusCard
          label="Docker"
          value={docker?.connected ? "Connected" : "Offline"}
          ok={!!docker?.connected}
        />
        <StatusCard
          label="OpenFOAM image"
          value={
            docker?.image?.available
              ? docker.image.name
              : "Not pulled"
          }
          ok={!!docker?.image?.available}
        />
        <StatusCard label="Cases" value={String(cases.length)} ok />
      </div>

      <div className="bg-[var(--card)] rounded-xl border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="text-lg font-semibold m-0">Recent cases</h2>
        </div>
        {cases.length === 0 ? (
          <div className="p-12 text-center text-[var(--muted-foreground)]">
            <FolderOpen className="w-10 h-10 mx-auto mb-3 opacity-50" />
            <p className="m-0">No cases yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {cases.slice(0, 8).map((c) => (
              <Link
                key={c.id}
                to={`/cases/${c.id}`}
                className="flex justify-between p-4 no-underline hover:bg-[var(--secondary)]"
              >
                <span className="font-medium text-[var(--foreground)]">
                  {c.name}
                </span>
                <span className="text-sm text-[var(--muted-foreground)]">
                  {c.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusCard({ label, value, ok }) {
  return (
    <div className="bg-[var(--card)] rounded-xl border border-[var(--border)] p-4">
      <p className="text-sm text-[var(--muted-foreground)] m-0 mb-1">{label}</p>
      <p
        className={`text-lg font-semibold m-0 ${
          ok ? "text-[var(--success)]" : "text-[var(--destructive)]"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
