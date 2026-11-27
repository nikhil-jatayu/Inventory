"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, LocateFixed } from "lucide-react";
import { PRIORITY_COLORS, type Priority } from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";
import { timelineDates } from "@/lib/planning";

export type TimelineRow = {
  id: number;
  item_name: string;
  project: string;
  planned_date: string;
  planned_end_date: string;
  quantity: number;
  category: Priority;
  detail: string;
  totals: string;
  closed?: boolean;
  actuals?: { id: number; dispatch_date: string; quantity: number }[];
};

export type TimelineRange = { from: string; to: string; today: string };

const dayLabel = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
const navigationClass = "inline-flex min-h-9 items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40";

export function ContinuousTimeline({ rows, range, loading, mode, onSelectPlan, onSelectDate }: {
  rows: TimelineRow[];
  range: TimelineRange;
  loading?: boolean;
  mode: "purchase" | "dispatch";
  onSelectPlan?: (id: number) => void;
  onSelectDate?: (date: string) => void;
}) {
  const { from, to, today } = range;
  const dates = useMemo(() => timelineDates(from, to), [from, to]);
  const [anchor, setAnchor] = useState<string>();
  const [dayCount, setDayCount] = useState(7);
  const grid = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = grid.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const width = entry.contentRect.width;
      const labelWidth = Math.min(width * 0.45, 220);
      setDayCount(Math.max(1, Math.min(21, Math.floor((width - labelWidth) / 42))));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const requestedDate = anchor ?? today;
  const start = dates.indexOf(requestedDate < from ? from : requestedDate > to ? to : requestedDate);
  const windowDates = dates.slice(start, start + dayCount);
  const first = windowDates[0];
  const last = windowDates.at(-1)!;
  const indices = new Map(windowDates.map((date, index) => [date, index]));
  const columnWidth = 100 / windowDates.length;
  const visibleRows = rows
    .filter(row => (row.planned_date <= last && row.planned_end_date >= first)
      || row.actuals?.some(event => indices.has(event.dispatch_date)))
    .sort((a, b) => Number(Boolean(a.closed)) - Number(Boolean(b.closed))
      || a.planned_end_date.localeCompare(b.planned_end_date)
      || a.item_name.localeCompare(b.item_name) || a.id - b.id);
  const isDispatch = mode === "dispatch";

  return (
    <section className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 px-3 py-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{isDispatch ? "Dispatch" : "Purchase"} timeline</h3>
          <p className="text-xs text-slate-500" aria-live="polite">
            {formatDate(first)} – {formatDate(last)}
            {!loading && ` · ${visibleRows.length} ${visibleRows.length === 1 ? "plan" : "plans"}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button type="button" className={navigationClass} aria-label="Previous dates" disabled={start === 0}
            onClick={() => setAnchor(dates[Math.max(0, start - dayCount)])}>
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button type="button" className={navigationClass} onClick={() => setAnchor(undefined)}>
            <LocateFixed className="h-4 w-4" /> Today
          </button>
          <button type="button" className={navigationClass} aria-label="Next dates" disabled={start + dayCount >= dates.length}
            onClick={() => setAnchor(dates[start + dayCount])}>
            <ChevronRight className="h-4 w-4" />
          </button>
          <input type="date" aria-label="Jump to date" className={`${navigationClass} tabular-nums`}
            min={from} max={to} value={first} onChange={event => {
              if (event.target.value) setAnchor(event.target.value);
            }} />
        </div>
      </div>

      <div ref={grid} className="border-y border-slate-200">
        <div className="grid grid-cols-[min(45%,220px)_minmax(0,1fr)] bg-slate-50">
          <div className="border-r border-slate-200 px-2.5 py-2 text-xs text-slate-600">
            <div className="font-semibold text-slate-900">Item / deadline</div>
            <div>{isDispatch ? "Planned / Actual / Left" : "Planned / Received / Cancelled / Left"}</div>
          </div>
          <div className="flex">
            {windowDates.map(date => (
              <button type="button" key={date} disabled={!onSelectDate} onClick={() => onSelectDate?.(date)}
                title={formatDate(date)} aria-label={formatDate(date)} aria-current={date === today ? "date" : undefined}
                className={`min-w-0 flex-1 whitespace-nowrap border-r border-slate-200 py-2 text-[10px] last:border-r-0 enabled:hover:bg-indigo-50 ${date === today ? "bg-indigo-100 font-bold text-indigo-800" : "text-slate-600"}`}>
                {dayLabel.format(new Date(`${date}T00:00:00`))}
              </button>
            ))}
          </div>
        </div>

        {loading || !visibleRows.length ? (
          <p className="border-t border-slate-200 px-3 py-4 text-sm text-slate-500">
            {loading ? "Loading timeline…" : "No matching plans or activity on these dates."}
          </p>
        ) : visibleRows.map(row => {
          const startColumn = indices.get(row.planned_date < first ? first : row.planned_date);
          const endColumn = indices.get(row.planned_end_date > last ? last : row.planned_end_date);
          const actualsByDate = new Map<string, NonNullable<TimelineRow["actuals"]>>();
          for (const event of row.actuals ?? []) {
            if (!indices.has(event.dispatch_date)) continue;
            const events = actualsByDate.get(event.dispatch_date) ?? [];
            events.push(event);
            actualsByDate.set(event.dispatch_date, events);
          }
          const color = row.closed ? "#64748b" : PRIORITY_COLORS[row.category].background;
          const description = `${row.item_name} · ${formatDate(row.planned_date)} – ${formatDate(row.planned_end_date)} · ${row.category} · ${formatQuantity(row.quantity)}`;

          return (
            <div key={row.id} className="grid grid-cols-[min(45%,220px)_minmax(0,1fr)] border-t border-slate-200 even:bg-slate-50/50">
              <div className="min-w-0 border-r border-slate-200 px-2.5 py-1.5 text-xs">
                <button type="button" disabled={!onSelectPlan} onClick={() => onSelectPlan?.(row.id)}
                  className="block max-w-full truncate text-left font-semibold enabled:hover:text-indigo-700" title={row.item_name}>
                  {row.item_name}
                </button>
                <p className="truncate text-slate-500" title={`${row.project} · ${row.detail}`}>{row.project} · {row.detail}</p>
                <p className="tabular-nums text-slate-700">{row.totals}</p>
                <p className="font-medium text-slate-700">Due {formatDate(row.planned_end_date)}</p>
              </div>
              <div className="relative min-w-0">
                <div aria-hidden className="pointer-events-none absolute inset-0 flex">
                  {windowDates.map(date => (
                    <div key={date} className={`flex-1 border-r border-slate-200 last:border-r-0 ${date === today ? "bg-indigo-50" : ""}`} />
                  ))}
                </div>
                {startColumn !== undefined && endColumn !== undefined && endColumn >= startColumn && (
                  <button type="button" disabled={!onSelectPlan} onClick={() => onSelectPlan?.(row.id)}
                    title={description} aria-label={description}
                    className="absolute top-2 h-6 truncate rounded px-1.5 text-left text-xs font-semibold text-white enabled:hover:brightness-90"
                    style={{ left: `calc(${startColumn * columnWidth}% + 1px)`, width: `calc(${(endColumn - startColumn + 1) * columnWidth}% - 2px)`, backgroundColor: color }}>
                    {formatQuantity(row.quantity)} · {row.category}
                  </button>
                )}
                {[...actualsByDate].map(([date, events]) => (
                  <div key={date} className="absolute top-9 flex justify-center"
                    style={{ left: `${indices.get(date)! * columnWidth}%`, width: `${columnWidth}%` }}>
                    <span tabIndex={0} title={events.map(event => `${date}: ${formatQuantity(event.quantity)} (dispatch #${event.id})`).join("\n")}
                      className="max-w-full truncate rounded bg-indigo-600 px-1 py-0.5 text-[10px] font-semibold text-white">
                      {formatQuantity(events.reduce((sum, event) => sum + Number(event.quantity), 0))}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 px-3 py-2 text-xs text-slate-600">
        {[
          [PRIORITY_COLORS.NORMAL.background, "Normal"],
          [PRIORITY_COLORS.URGENT.background, "Urgent"],
          [PRIORITY_COLORS.EMERGENCY.background, "Emergency"],
          ["#64748b", "Closed / completed"],
          ...(isDispatch ? [["#4f46e5", "Actual dispatch (daily total)"]] : []),
        ].map(([color, label]) => (
          <span key={label} className="inline-flex items-center gap-1">
            <i className="h-2 w-2 rounded" style={{ backgroundColor: color }} />{label}
          </span>
        ))}
      </div>
    </section>
  );
}
