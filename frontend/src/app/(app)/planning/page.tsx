"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertTriangle,
  CalendarDays,
  Clock,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";

import { PlanModal } from "@/components/planning/plan-modal";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page";
import { qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useDebouncedValue } from "@/lib/hooks";
import {
  canWrite,
  planStatusTone,
  PRIORITY_COLORS,
  PRIORITY_LABELS,
  priorityTone,
  type DispatchPlan,
  type PlanStatus,
  type Priority,
} from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";

const DispatchCalendar = dynamic(
  () =>
    import("@/components/planning/dispatch-calendar").then((module) => module.DispatchCalendar),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-120 items-center justify-center text-sm text-slate-500">
        Loading calendar…
      </div>
    ),
  },
);

const PRIORITY_OPTIONS: { value: Priority | ""; label: string }[] = [
  { value: "", label: "All priorities" },
  { value: "NORMAL", label: "Normal" },
  { value: "URGENT", label: "Urgent" },
  { value: "EMERGENCY", label: "Emergency" },
];

const STATUS_OPTIONS: { value: PlanStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "PLANNED", label: "Planned" },
  { value: "PARTIAL", label: "Partial" },
  { value: "DONE", label: "Done" },
];

export default function PlanningPage() {
  const { user } = useAuth();
  const writable = canWrite(user?.role, "planning");

  const [range, setRange] = useState<{ from: string; to: string } | null>(null);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [priority, setPriority] = useState<Priority | "">("");
  const [statusFilter, setStatusFilter] = useState<PlanStatus | "">("");
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [selected, setSelected] = useState<DispatchPlan | null>(null);
  const [modal, setModal] = useState<{
    open: boolean;
    plan: DispatchPlan | null;
    defaultDate?: string;
  }>({ open: false, plan: null });

  const handleRangeChange = useCallback((from: string, to: string) => {
    setRange((current) =>
      current?.from === from && current?.to === to ? current : { from, to },
    );
  }, []);

  const query = useApiQuery<DispatchPlan[]>(
    range
      ? `/dispatch-plans${qs({
          date_from: range.from,
          date_to: range.to,
          priority,
          status: statusFilter,
          search: debouncedSearch,
        })}`
      : null,
    refresh,
  );

  const plans = useMemo(() => query.data ?? [], [query.data]);
  const warnings = useMemo(
    () =>
      plans
        .filter((plan) => plan.warning)
        .sort((a, b) => a.planned_date.localeCompare(b.planned_date)),
    [plans],
  );

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timer);
  }, [notice]);

  function handleSaved(message: string) {
    setModal({ open: false, plan: null });
    setSelected(null);
    setNotice(message);
    setRefresh((value) => value + 1);
  }

  const canEditSelected = writable && selected && selected.status !== "DONE";

  return (
    <div className="space-y-5">
      <PageHeader
        title="Dispatch Planning"
        description="Monthly dispatch calendar. Warnings flag plans that fall inside the lead time for their priority."
        actions={
          writable && (
            <Button onClick={() => setModal({ open: true, plan: null })}>
              <Plus className="h-4 w-4" />
              New plan
            </Button>
          )
        }
      />

      {notice && (
        <Alert tone="success" onDismiss={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {query.error && <Alert tone="error">{query.error}</Alert>}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by item, PO, customer or unit"
              className="pl-9"
              aria-label="Search dispatch plans"
            />
          </div>
          <div className="grid grid-cols-2 gap-3 xl:w-96">
            <Field label="Priority" htmlFor="plan-priority-filter">
              <Select
                id="plan-priority-filter"
                value={priority}
                onChange={(event) => setPriority(event.target.value as Priority | "")}
              >
                {PRIORITY_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status" htmlFor="plan-status-filter">
              <Select
                id="plan-status-filter"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as PlanStatus | "")}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {(search || priority || statusFilter) && (
            <Button
              variant="ghost"
              onClick={() => {
                setSearch("");
                setPriority("");
                setStatusFilter("");
              }}
            >
              <SlidersHorizontal className="h-4 w-4" />
              Reset
            </Button>
          )}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-600">
              {(Object.keys(PRIORITY_COLORS) as Priority[]).map((option) => (
                <span key={option} className="inline-flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: PRIORITY_COLORS[option].background }}
                  />
                  {PRIORITY_LABELS[option]}
                </span>
              ))}
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-400 ring-2 ring-amber-200" />
                Lead-time warning
              </span>
              <span className="inline-flex items-center gap-1.5">
                <CalendarDays className="h-3.5 w-3.5" />
                {query.loading ? "Loading…" : `${plans.length} plans`}
              </span>
            </div>
          </div>

          <div className="p-2 sm:p-3">
            <DispatchCalendar
              plans={plans}
              onSelectPlan={setSelected}
              onRangeChange={handleRangeChange}
              onSelectDate={
                writable
                  ? (date) => setModal({ open: true, plan: null, defaultDate: date })
                  : undefined
              }
            />
          </div>
        </section>

        <aside className="space-y-4">
          {selected && (
            <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-start justify-between gap-2 border-b border-slate-100 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {selected.item_name}
                  </p>
                  <p className="truncate text-xs text-slate-500">
                    {selected.po_number} · {selected.customer_name}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                  aria-label="Clear selected plan"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-3 px-4 py-3">
                <div className="flex flex-wrap gap-1.5">
                  <Badge tone={priorityTone(selected.priority)}>
                    {PRIORITY_LABELS[selected.priority]}
                  </Badge>
                  <Badge tone={planStatusTone(selected.status)}>{selected.status}</Badge>
                  {selected.warning && <Badge tone="rose">Lead time</Badge>}
                </div>
                <dl className="grid grid-cols-2 gap-2 text-xs">
                  {[
                    ["Dispatch date", formatDate(selected.planned_date)],
                    ["Quantity", formatQuantity(selected.quantity)],
                    ["Fulfilled", formatQuantity(selected.fulfilled_quantity)],
                    ["Outstanding", formatQuantity(selected.outstanding_quantity)],
                    ["Unit", selected.unit_number],
                    ["Family", selected.item_family],
                    ["Lead time", `${selected.lead_time_days} days`],
                    [
                      "Days from today",
                      selected.days_until === 0
                        ? "Today"
                        : selected.days_until > 0
                          ? `+${selected.days_until}`
                          : String(selected.days_until),
                    ],
                  ].map(([label, value]) => (
                    <div
                      key={label}
                      className="rounded-lg bg-slate-50 px-2.5 py-1.5 ring-1 ring-slate-200 ring-inset"
                    >
                      <dt className="text-slate-500">{label}</dt>
                      <dd className="mt-0.5 font-semibold text-slate-800">{value}</dd>
                    </div>
                  ))}
                </dl>
                {canEditSelected && (
                  <Button
                    size="sm"
                    variant="secondary"
                    className="w-full"
                    onClick={() => setModal({ open: true, plan: selected })}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit plan
                  </Button>
                )}
                {selected.status === "DONE" && (
                  <p className="text-xs text-slate-500">
                    Completed plans are read-only; their dispatch has been recorded.
                  </p>
                )}
              </div>
            </section>
          )}

          <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
              <h2 className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                Lead-time warnings
              </h2>
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-amber-200 ring-inset">
                {warnings.length}
              </span>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {warnings.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-slate-500">
                  No plans fall inside their priority lead time in this period.
                </p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {warnings.map((plan) => (
                    <li key={plan.id}>
                      <button
                        type="button"
                        onClick={() => setSelected(plan)}
                        className="flex w-full items-start justify-between gap-3 px-4 py-2.5 text-left transition-colors hover:bg-amber-50/60"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-800">
                            {plan.item_name}
                          </p>
                          <p className="truncate text-xs text-slate-500">
                            {plan.po_number} · {plan.customer_name}
                          </p>
                          <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-slate-500">
                            <Clock className="h-3 w-3" />
                            {formatDate(plan.planned_date)} ·{" "}
                            {plan.days_until < 0
                              ? `${Math.abs(plan.days_until)}d overdue`
                              : `${plan.days_until}d away`}
                          </p>
                        </div>
                        <Badge tone={priorityTone(plan.priority)}>
                          {PRIORITY_LABELS[plan.priority]}
                        </Badge>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <p className="rounded-xl bg-slate-100/70 px-3.5 py-3 text-xs leading-relaxed text-slate-500">
            Click a date to add a plan, or click an event to inspect it. Lead times are configured
            on the server: Normal, Urgent and Emergency priorities each have their own window.
          </p>
        </aside>
      </div>

      {modal.open && (
        <PlanModal
          key={modal.plan?.id ?? modal.defaultDate ?? "new"}
          open
          plan={modal.plan}
          defaultDate={modal.defaultDate}
          onClose={() => setModal({ open: false, plan: null })}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
