export function cx(...values: (string | false | null | undefined)[]): string {
  return values.filter(Boolean).join(" ");
}

const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function fmtDateTime(iso: string | null): string {
  if (!iso) return "Not supplied";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${DATE_TIME.format(date)} IST`;
}

export function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function fmtDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return mins > 0 ? `${mins}m ${secs.toString().padStart(2, "0")}s` : `${secs}s`;
}

export function pct(value: number | null): string {
  return value == null ? "n/a" : `${value.toFixed(1)}%`;
}

export function shortId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

export function initials(name: string | null): string {
  if (!name) return "—";
  const cleaned = name.split("@")[0].replace(/[._-]+/g, " ");
  return cleaned
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export const toneClasses: Record<string, string> = {
  accent: "bg-indigo-50 text-indigo-700 border-indigo-200",
  info: "bg-sky-50 text-sky-700 border-sky-200",
  warning: "bg-amber-50 text-amber-800 border-amber-200",
  danger: "bg-rose-50 text-rose-700 border-rose-200",
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
  muted: "bg-slate-50 text-slate-600 border-slate-200",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

export function reviewTone(state: string): string {
  switch (state) {
    case "reviewed":
      return "success";
    case "needs_review":
      return "warning";
    case "awaiting_text":
      return "neutral";
    default:
      return "info";
  }
}

export function freshnessTone(state: string): string {
  switch (state) {
    case "current":
      return "success";
    case "pending_review":
      return "warning";
    case "stale":
      return "danger";
    case "unavailable":
      return "neutral";
    default:
      return "muted";
  }
}

export function originTone(origin: string): string {
  switch (origin) {
    case "human_assisted":
      return "accent";
    case "pre_generated":
      return "info";
    default:
      return "muted";
  }
}

export function routeTone(tone: string): string {
  return toneClasses[tone] ?? toneClasses.neutral;
}

export function stateLabel(state: string): string {
  return state.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
