import { Construction } from "lucide-react";

interface PlaceholderProps {
  title: string;
  description: string;
  phase: string;
}

export function Placeholder({ title, description, phase }: PlaceholderProps) {
  return (
    <div>
      <h1 className="text-3xl font-bold m-0 mb-2">{title}</h1>
      <p className="text-[var(--muted-foreground)] mb-8">{description}</p>

      <div className="border border-dashed border-[var(--border)] rounded-xl p-16 text-center">
        <Construction className="w-10 h-10 mx-auto mb-4 text-[var(--muted-foreground)]" />
        <p className="text-[var(--muted-foreground)] m-0">
          Planned for <span className="text-[var(--primary)] font-medium">{phase}</span> — see ROADMAP.md
        </p>
      </div>
    </div>
  );
}
