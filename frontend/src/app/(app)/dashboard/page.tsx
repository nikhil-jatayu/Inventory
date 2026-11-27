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
import { DispatchCalendar, type GanttPlan } from "@/components/planning/dispatch-calendar";
import { timelineRange } from "@/lib/planning";
import type { DashboardSummary } from "@/lib/types";
import { currentMonth, formatDate, formatQuantity } from "@/lib/utils";

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

export default function DashboardPage() {
  const [ganttRange] = useState(() => timelineRange());
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
  const gantt = useApiQuery<GanttPlan[]>(report ? `/dispatch-gantt${qs({date_from: ganttRange.from, date_to: ganttRange.to, family})}` : null, refresh);

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
      label: "Real-time stock / plan",
      value: kpis ? `${formatQuantity(kpis.month_stock_available)} / ${formatQuantity(kpis.month_planned)}` : "–",
      hint: report ? `${report.month_label} · available stock / monthly plan` : "Selected month",
      icon: Target,
      tone: "rose" as const,
    },
    {
      label: "Monthly dispatch plan",
      value: kpis ? formatQuantity(kpis.month_planned) : "–",
      hint: report ? report.month_label : "Selected month",
      icon: CalendarDays,
      tone: "amber" as const,
    },
    {
      label: "Monthly net sales",
      value: kpis ? formatQuantity(kpis.month_sales) : "–",
      hint: kpis ? `${formatQuantity(kpis.month_gross_sales)} gross − ${formatQuantity(kpis.month_sales_rejected)} linked rejected` : "Selected month",
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

  const primaryCards = [cards[3], cards[2], cards[4]];
  const secondaryCards = [cards[0], cards[1], cards[5], {
    label: "Stock shortfall", value: kpis ? formatQuantity(kpis.total_shortfall) : "–",
    hint: "Item-level outstanding demand not covered", icon: AlertTriangle, tone: "rose" as const,
  }];

  function resetFilters() {
    setMonth(currentMonth());
    setFy("");
    setFamily("");
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Dashboard"
        description="Monthly dispatch plan, live stock coverage, sales and quality performance."
      />

      {dashboardQuery.error && <Alert tone="error">{dashboardQuery.error}</Alert>}
      {kpis && kpis.month_unlinked_rejected > 0 && <Alert>{formatQuantity(kpis.month_unlinked_rejected)} historical rejected pieces in the selected month have no dispatch reference and are not deducted from net sales.</Alert>}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:w-[32rem]">
            <Field label="Month" htmlFor="dashboard-month">
              <Input
                id="dashboard-month"
                type="month"
                value={month}
                onChange={(event) => { setMonth(event.target.value || currentMonth()); setFy(""); }}
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
              {formatDate(report.fy_start)} – {formatDate(report.fy_end)} · Monthly cards use the selected month; annual charts use the financial year. Stock is live.
            </p>
          )}
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        {primaryCards.map((card) => (
          <StatCard key={card.label} {...card} />
        ))}
      </section>

      <section className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {secondaryCards.map(card => <StatCard key={card.label} {...card} />)}
      </section>
      {report && <section className="space-y-2">
        <h2 className="text-sm font-semibold">Continuous dispatch plan vs actual dispatch</h2>
        <p className="text-xs text-slate-500">Use the timeline’s date controls to browse dispatch plans. The reporting filters above apply to the cards and charts.</p>
        {gantt.error && <Alert tone="error">{gantt.error}</Alert>}
        <DispatchCalendar plans={gantt.data ?? []} range={ganttRange} loading={gantt.loading} />
      </section>}

      {report && <DashboardCharts report={report} />}
    </div>
  );
}
