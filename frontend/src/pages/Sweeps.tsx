import { Placeholder } from "@/components/Placeholder";

export function Sweeps() {
  return (
    <Placeholder
      title="Parameter Sweeps"
      description="AoA sweeps → polar curves, RPM sweeps → fan/compressor maps. Queue of child cases from one base spec."
      phase="Phase 1 (polars), Phase 2 (maps)"
    />
  );
}
