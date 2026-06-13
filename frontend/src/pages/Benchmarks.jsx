import { useQuery } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

export function Benchmarks() {
  const { data: list = [] } = useQuery({
    queryKey: ["benchmarks"],
    queryFn: api.listBenchmarks,
    retry: false,
  });
  const { data: naca } = useQuery({
    queryKey: ["benchmark", "naca0012"],
    queryFn: () => api.getBenchmark("naca0012"),
    retry: false,
  });

  return (
    <div className="max-w-3xl">
      <h1 className="text-3xl font-bold m-0 mb-2">Benchmarks</h1>
      <p className="text-[var(--muted-foreground)] mb-8">
        Reference data to verify the toolchain before trusting your own results.
        Build the matching case, run an AoA sweep, and compare against these curves.
      </p>

      {naca && (
        <Card>
          <div className="text-sm font-semibold">{naca.name}</div>
          <div className="text-xs text-[var(--muted-foreground)] mb-3">
            Re ≈ {naca.reynolds.toExponential(0)} · {naca.source}
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={naca.reference}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="alpha" stroke="var(--muted-foreground)" fontSize={11}
                label={{ value: "AoA [deg]", position: "insideBottom", offset: -2, fontSize: 11 }} />
              <YAxis stroke="var(--muted-foreground)" fontSize={11} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
              <Legend />
              <Line type="monotone" dataKey="cl" name="Cl (reference)" stroke="#3b82f6" />
              <Line type="monotone" dataKey="cd" name="Cd (reference)" stroke="#ef4444" />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div className="text-xs text-[var(--muted-foreground)] mt-4">
        {list.length} benchmark{list.length === 1 ? "" : "s"} available.
      </div>
    </div>
  );
}
