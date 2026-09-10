import { cn } from "@/lib/utils";

export function Card({ className, children }) {
  return (
    <div className={cn("bg-[var(--card)] rounded-xl border border-[var(--border)] p-5", className)}>
      {children}
    </div>
  );
}

export function Button({ variant = "primary", className, disabled, children, ...props }) {
  const variants = {
    primary: "bg-[var(--primary)] text-white hover:opacity-90",
    success: "bg-[var(--success)] text-white hover:opacity-90",
    ghost: "border border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--secondary)]",
    danger: "bg-[var(--destructive)] text-white hover:opacity-90",
  };
  return (
    <button
      disabled={disabled}
      className={cn(
        "px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-opacity disabled:opacity-40 disabled:cursor-not-allowed",
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Field({ label, unit, help, children }) {
  return (
    <label className="block mb-4">
      <span className="block text-sm font-medium mb-1">
        {label}
        {unit && <span className="text-[var(--muted-foreground)]"> [{unit}]</span>}
      </span>
      {children}
      {help && <span className="block text-xs text-[var(--muted-foreground)] mt-1">{help}</span>}
    </label>
  );
}

export function Input(props) {
  return (
    <input
      className="w-full px-3 py-2 rounded-lg bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] focus:outline-none focus:border-[var(--primary)]"
      {...props}
    />
  );
}

export function Select({ options, ...props }) {
  return (
    <select
      className="w-full px-3 py-2 rounded-lg bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] focus:outline-none focus:border-[var(--primary)]"
      {...props}
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

const sevStyle = {
  pass: "text-[var(--success)] border-[var(--success)]",
  warn: "text-[var(--warning)] border-[var(--warning)]",
  fail: "text-[var(--destructive)] border-[var(--destructive)]",
};

export function Badge({ severity = "pass", children }) {
  return (
    <span className={cn("inline-block px-2 py-0.5 rounded text-xs font-semibold border", sevStyle[severity])}>
      {children}
    </span>
  );
}

export function Stat({ label, value }) {
  return (
    <div className="bg-[var(--secondary)] rounded-lg px-3 py-2">
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className="text-sm font-semibold font-mono">{value}</div>
    </div>
  );
}
