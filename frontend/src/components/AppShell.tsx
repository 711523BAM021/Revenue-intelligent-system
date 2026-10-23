import {
  ClipboardList,
  Database,
  Download,
  Gauge,
  History,
  MessagesSquare,
  Route as RouteIcon,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import { cx } from "../lib/format";
import type { Meta } from "../lib/types";

const NAV = [
  { to: "/", label: "Overview", icon: Gauge, end: true },
  { to: "/conversations", label: "Conversations", icon: MessagesSquare },
  { to: "/routing", label: "Routing & Review", icon: RouteIcon },
  { to: "/brief", label: "Manager Brief", icon: ClipboardList },
  { to: "/exports", label: "Exports", icon: Download },
  { to: "/imports", label: "Import History", icon: History },
  { to: "/quality", label: "Data Quality", icon: ShieldCheck },
];

export interface ShellContext {
  meta: Meta | null;
  refreshMeta: () => void;
}

export function AppShell() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const location = useLocation();

  const load = useCallback(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  useEffect(() => {
    load();
  }, [load, location.pathname]);

  const datasetsReady = meta?.datasets.every((dataset) => dataset.exists) ?? false;

  return (
    <div className="min-h-screen bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow"
      >
        Skip to content
      </a>
      <div className="mx-auto flex min-h-screen w-full max-w-[1560px]">
        <aside className="hidden w-[236px] shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
          <Brand />
          <nav aria-label="Primary" className="flex-1 px-3 py-4">
            <ul className="space-y-0.5">
              {NAV.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cx(
                        "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors",
                        isActive
                          ? "bg-indigo-50 text-indigo-800"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className="border-t border-slate-200 px-4 py-4">
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span
                className={cx(
                  "h-1.5 w-1.5 rounded-full",
                  datasetsReady ? "bg-emerald-500" : "bg-amber-500",
                )}
              />
              {datasetsReady ? "Deliveries detected" : "Deliveries not found"}
            </div>
            <p className="mt-1.5 text-[11px] leading-4 text-slate-400">
              21 Aug 2026 · Asia/Kolkata
              <br />
              Selected records only
            </p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
            <div className="flex items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
              <div className="flex items-center gap-2 lg:hidden">
                <div className="grid h-6 w-6 place-items-center rounded bg-slate-900 text-[10px] font-bold text-white">
                  RI
                </div>
                <span className="text-[13px] font-semibold text-slate-800">Revenue Intelligence</span>
              </div>
              <div className="hidden items-center gap-2 text-[12px] text-slate-500 lg:flex">
                <Database className="h-3.5 w-3.5" />
                <span>
                  <span className="font-medium text-slate-700">
                    {meta?.counts.records ?? "—"}
                  </span>{" "}
                  selected records
                </span>
                <span className="text-slate-300">|</span>
                <span>Reporting date 21 Aug 2026 (IST)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden text-[11px] text-slate-400 sm:inline">
                  Analyses: pre-generated + runtime calculations
                </span>
                <NavLink
                  to="/imports"
                  className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-2.5 py-1.5 text-[12px] font-medium text-white hover:bg-slate-800"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Import lab
                </NavLink>
              </div>
            </div>
            <nav aria-label="Primary mobile" className="scroll-thin overflow-x-auto border-t border-slate-100 lg:hidden">
              <ul className="flex gap-1 px-2 py-1.5">
                {NAV.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) =>
                        cx(
                          "flex items-center gap-1.5 whitespace-nowrap rounded px-2 py-1.5 text-[12px]",
                          isActive ? "bg-indigo-50 text-indigo-800" : "text-slate-600",
                        )
                      }
                    >
                      <item.icon className="h-3.5 w-3.5" />
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
          </header>
          <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <Outlet context={{ meta, refreshMeta: load } satisfies ShellContext} />
          </main>
          <footer className="border-t border-slate-200 px-4 py-4 text-[11px] leading-4 text-slate-400 sm:px-6">
            Revenue Intelligence Inbox · de-identified assessment data · no pipeline value, revenue or
            performance ranking is inferred. Meeting organisers are organisers, not confirmed salespeople.
          </footer>
        </div>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 border-b border-slate-200 px-4 py-3.5">
      <div className="grid h-8 w-8 place-items-center rounded-md bg-slate-900 text-[11px] font-bold tracking-tight text-white">
        RI
      </div>
      <div className="leading-tight">
        <div className="text-[13px] font-semibold tracking-tight text-slate-900">Revenue Intelligence</div>
        <div className="text-[11px] text-slate-500">Conversation inbox</div>
      </div>
    </div>
  );
}
