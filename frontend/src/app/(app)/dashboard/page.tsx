"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertTriangle,
  BadgeAlert,
  CalendarDays,
  SlidersHorizontal,
  Target,
  TrendingDown,
  Truck,
} from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page";
import { StatCard } from "@/components/ui/stat-card";
import { qs } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import type { DashboardCalendarDay, DashboardSummary } from "@/lib/types";
import { cn, currentMonth, formatDate, formatQuantity, isoDate, todayISO } from "@/lib/utils";

const DashboardCharts = dynamic(
  () =>
    import("@/components/dashboard/dashboard-charts").then(
      (module) => module.DashboardCharts,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-72 items-center justify-center rounded-xl border border-slate-200 bg-white text-sm text-slate-500 shadow-sm">
        Loading charts…
      </div>
    ),
  },
);

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function parseLocalDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

function buildWeeks(startISO: string, endISO: string): (string | null)[] {
  const start = parseLocalDate(startISO);
  const end = parseLocalDate(endISO);
  const offset = (start.getDay() + 6) % 7;
  const cells: (string | null)[] = Array(offset).fill(null);
  for (let day = 1; day <= end.getDate(); day += 1) {
    cells.push(isoDate(new Date(start.getFullYear(), start.getMonth(), day)));
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function priorityTone(day: DashboardCalendarDay): string {
  if (day.emergency > 0) return "bg-rose-500";
  if (day.urgent > 0) return "bg-amber-500";
  return "bg-emerald-500";
}

export default function DashboardPage() {
  const [month, setMonth] = useState(currentMonth());
  const [fy, setFy] = useState("");
  const [family, setFamily] = useState("");
  const refresh = 0;

  const familiesQuery = useApiQuery<{ families: string[] }>("/items/families", refresh);
  const dashboardQuery = useApiQuery<DashboardSummary>(
    `/dashboard${qs({ month, fy, family })}`,
    refresh,
  );

  const report = dashboardQuery.data;
  const families = familiesQuery.data?.families ?? [];
  const activeFy = fy || report?.fy || "";
  const today = todayISO();

  const calendarDays = new Map(
    (report?.calendar ?? []).map((day) => [day.date, day] as const),
  );
  const weeks = report ? buildWeeks(report.month_start, report.month_end) : [];
  const plannedTotal = (report?.calendar ?? []).reduce(
    (sum, day) => sum + day.planned,
    0,
  );
  const plannedDays = report?.calendar.length ?? 0;
  const urgentDays = (report?.calendar ?? []).filter((day) => day.urgent > 0).length;
  const emergencyDays = (report?.calendar ?? []).filter(
    (day) => day.emergency > 0,
  ).length;

  const kpis = report?.kpis;
  const cards = [
    {
      label: "Critical items",
      value: kpis ? String(kpis.critical_items) : "–",
      hint: "Active items below critical level",
      icon: AlertTriangle,
      tone: "rose" as const,
    },
    {
      label: "Below reorder",
      value: kpis ? String(kpis.below_reorder_items) : "–",
      hint: "Active items below reorder level",
      icon: TrendingDown,
      tone: "amber" as const,
    },
    {
      label: "Total shortfall",
      value: kpis ? formatQuantity(kpis.total_shortfall) : "–",
      hint: report ? `Planned vs stock in ${report.month_label}` : "Selected month",
      icon: Target,
      tone: "rose" as const,
    },
    {
      label: "Planned this month",
      value: kpis ? formatQuantity(kpis.month_planned) : "–",
      hint: report ? report.month_label : "Selected month",
      icon: CalendarDays,
      tone: "amber" as const,
    },
    {
      label: "Dispatched this month",
      value: kpis ? formatQuantity(kpis.month_dispatched) : "–",
      hint: report ? report.month_label : "Selected month",
      icon: Truck,
      tone: "indigo" as const,
    },
    {
      label: "Rejected this month",
      value: kpis ? formatQuantity(kpis.month_rejected) : "–",
      hint: report ? report.month_label : "Selected month",
      icon: BadgeAlert,
      tone: "rose" as const,
    },
  ];

  function resetFilters() {
    setMonth(currentMonth());
    setFy("");
    setFamily("");
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Dashboard"
        description="A single view of stock health, dispatch commitments and quality performance."
      />

      {dashboardQuery.error && <Alert tone="error">{dashboardQuery.error}</Alert>}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:w-[32rem]">
            <Field label="Month" htmlFor="dashboard-month">
              <Input
                id="dashboard-month"
                type="month"
                value={month}
                onChange={(event) => setMonth(event.target.value)}
              />
            </Field>
            <Field label="Financial year" htmlFor="dashboard-fy">
              <Select
                id="dashboard-fy"
                value={activeFy}
                onChange={(event) => setFy(event.target.value)}
                disabled={!report}
              >
                {!report && <option value="">Current year</option>}
                {report?.fy_options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Family" htmlFor="dashboard-family">
              <Select
                id="dashboard-family"
                value={family}
                onChange={(event) => setFamily(event.target.value)}
              >
                <option value="">All families</option>
                {families.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {(month !== currentMonth() || fy || family) && (
            <Button variant="ghost" onClick={resetFilters}>
              <SlidersHorizontal className="h-4 w-4" />
              Reset
            </Button>
          )}
          {report && (
            <p className="text-xs text-slate-500 sm:ml-auto">
              {formatDate(report.fy_start)} – {formatDate(report.fy_end)} · family and month
              filters apply to all cards
            </p>
          )}
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {cards.map((card) => (
          <StatCard key={card.label} {...card} />
        ))}
      </section>

      {report && (
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Dispatch calendar summary
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                {report.month_label} · {plannedDays} day{plannedDays === 1 ? "" : "s"} with
                planned dispatches
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500" /> Normal
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-amber-500" /> Urgent
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-rose-500" /> Emergency
              </span>
              <span className="font-medium text-slate-700">
                {formatQuantity(plannedTotal)} planned
              </span>
            </div>
          </div>

          <div className="px-3 py-3 sm:px-4">
            <div className="grid grid-cols-7 gap-1 text-center text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
              {WEEKDAYS.map((day) => (
                <span key={day} className="py-1">
                  {day}
                </span>
              ))}
            </div>
            <div className="mt-1 grid grid-cols-7 gap-1">
              {weeks.map((dateKey, index) => {
                if (!dateKey) {
                  return <div key={`empty-${index}`} className="min-h-16 rounded-lg bg-slate-50/40" />;
                }
                const day = calendarDays.get(dateKey);
                const dayNumber = Number(dateKey.slice(8, 10));
                return (
                  <div
                    key={dateKey}
                    className={cn(
                      "min-h-16 rounded-lg border p-1.5 text-left transition-colors",
                      day
                        ? "border-slate-200 bg-white"
                        : "border-slate-100 bg-slate-50/40",
                      dateKey === today && "ring-2 ring-indigo-500/30",
                    )}
                    title={
                      day
                        ? `${formatQuantity(day.planned)} planned · ${day.count} plan${day.count === 1 ? "" : "s"}`
                        : "No planned dispatches"
                    }
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span
                        className={cn(
                          "text-[11px] font-medium",
                          dateKey === today ? "text-indigo-600" : "text-slate-500",
                        )}
                      >
                        {dayNumber}
                      </span>
                      {day && (
                        <span className={cn("h-1.5 w-1.5 rounded-full", priorityTone(day))} />
                      )}
                    </div>
                    {day && (
                      <div className="mt-1">
                        <p className="text-xs font-semibold tabular-nums text-slate-800">
                          {formatQuantity(day.planned)}
                        </p>
                        <p className="text-[10px] text-slate-500">
                          {day.count} plan{day.count === 1 ? "" : "s"}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-slate-200 ring-inset">
                <p className="text-slate-500">Planned quantity</p>
                <p className="mt-0.5 font-semibold tabular-nums text-slate-900">
                  {formatQuantity(plannedTotal)}
                </p>
              </div>
              <div className="rounded-lg bg-amber-50 px-3 py-2 ring-1 ring-amber-100 ring-inset">
                <p className="text-amber-700">Urgent days</p>
                <p className="mt-0.5 font-semibold tabular-nums text-amber-900">{urgentDays}</p>
              </div>
              <div className="rounded-lg bg-rose-50 px-3 py-2 ring-1 ring-rose-100 ring-inset">
                <p className="text-rose-700">Emergency days</p>
                <p className="mt-0.5 font-semibold tabular-nums text-rose-900">
                  {emergencyDays}
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {report && <DashboardCharts report={report} />}
    </div>
  );
}
