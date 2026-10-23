import { Info, Loader2, Search, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cx, toneClasses } from "../lib/format";

export function Card({
  children,
  className,
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
}) {
  return <Tag className={cx("card", className)}>{children}</Tag>;
}

export function SectionHeader({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        {icon ? <div className="mt-0.5 text-slate-400">{icon}</div> : null}
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight text-slate-900">{title}</h2>
          {description ? (
            <p className="mt-1 max-w-2xl text-[12.5px] leading-5 text-slate-500">{description}</p>
          ) : null}
        </div>
      </div>
      {action}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
  className,
  title,
}: {
  children: ReactNode;
  tone?: string;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-4",
        toneClasses[tone] ?? toneClasses.neutral,
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "secondary",
  size = "md",
  disabled,
  type = "button",
  className,
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
  title?: string;
}) {
  const variants: Record<string, string> = {
    primary:
      "bg-indigo-700 text-white border-indigo-700 hover:bg-indigo-800 disabled:bg-indigo-300 disabled:border-indigo-300",
    secondary:
      "bg-white text-slate-700 border-slate-300 hover:bg-slate-50 disabled:text-slate-400",
    ghost: "bg-transparent text-slate-600 border-transparent hover:bg-slate-100",
    danger: "bg-white text-rose-700 border-rose-200 hover:bg-rose-50",
  };
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md border font-medium transition-colors disabled:cursor-not-allowed",
        size === "sm" ? "px-2.5 py-1 text-[12px]" : "px-3 py-1.5 text-[13px]",
        variants[variant],
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  children,
  hint,
  htmlFor,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  htmlFor?: string;
}) {
  return (
    <label className="block" htmlFor={htmlFor}>
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </span>
      {children}
      {hint ? <span className="mt-1 block text-[11px] text-slate-400">{hint}</span> : null}
    </label>
  );
}

export function Select({
  value,
  onChange,
  options,
  ariaLabel,
  id,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  ariaLabel: string;
  id?: string;
  className?: string;
}) {
  return (
    <select
      id={id}
      aria-label={ariaLabel}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={cx(
        "w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[13px] text-slate-800 shadow-sm",
        className,
      )}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export function SearchBox({
  value,
  onChange,
  placeholder = "Search text, person, reference…",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
      <input
        type="search"
        value={value}
        aria-label="Search conversations"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-slate-300 bg-white py-1.5 pl-8 pr-2.5 text-[13px] shadow-sm placeholder:text-slate-400"
      />
    </div>
  );
}

export function Metric({
  label,
  value,
  sub,
  tone = "neutral",
  hint,
  onClick,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: string;
  hint?: string;
  onClick?: () => void;
}) {
  const content = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</span>
        {hint ? (
          <span title={hint} aria-label={hint} className="text-slate-300">
            <Info className="h-3.5 w-3.5" />
          </span>
        ) : null}
      </div>
      <div className="mt-1.5 flex items-baseline gap-2">
        <span className="text-[26px] font-semibold leading-none tracking-tight text-slate-900">{value}</span>
        {sub ? <span className="text-[12px] leading-4 text-slate-500">{sub}</span> : null}
      </div>
      <div className={cx("mt-3 h-1 rounded-full", toneClasses[tone]?.split(" ")[0] ?? "bg-slate-100")} />
    </>
  );
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="card group w-full px-4 py-3.5 text-left transition-colors hover:border-slate-300 hover:bg-slate-50/60"
      >
        {content}
      </button>
    );
  }
  return <div className="card px-4 py-3.5">{content}</div>;
}

export function EmptyState({
  title,
  body,
  action,
  icon,
}: {
  title: string;
  body: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      {icon ? <div className="mb-1 text-slate-300">{icon}</div> : null}
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <p className="max-w-md text-[12.5px] leading-5 text-slate-500">{body}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-10 text-[13px] text-slate-500" role="status">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}…
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3" role="alert">
      <div className="flex items-start gap-2">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-rose-800">Something went wrong</p>
          <p className="mt-0.5 break-words text-[12.5px] text-rose-700">{message}</p>
          {onRetry ? (
            <Button size="sm" className="mt-2" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
      <div>
        {eyebrow ? <p className="label-xs mb-1.5">{eyebrow}</p> : null}
        <h1 className="text-[22px] font-semibold tracking-tight text-slate-900">{title}</h1>
        {description ? (
          <div className="mt-1.5 max-w-3xl text-[13px] leading-5 text-slate-500">{description}</div>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[132px_1fr] gap-2 py-1.5 text-[12.5px]">
      <dt className="text-slate-500">{label}</dt>
      <dd className="min-w-0 break-words text-slate-800">{children}</dd>
    </div>
  );
}
