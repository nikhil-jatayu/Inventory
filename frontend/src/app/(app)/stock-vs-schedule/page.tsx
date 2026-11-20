"use client";

import { useState } from "react";
import { AlertTriangle, ArrowDownRight, PackageSearch, ShieldAlert } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Field, Input, Select } from "@/components/ui/field";
import {
  EmptyRow,
  LoadingRow,
  PageHeader,
  SortHeader,
  TableShell,
} from "@/components/ui/page";
import { Pagination } from "@/components/ui/pagination";
import { qs } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import {
  type ScheduleFilter,
  type SchedulePage,
  type StockStatus,
} from "@/lib/types";
import { cn, currentMonth, formatDate, formatQuantity, monthRange } from "@/lib/utils";

const PAGE_SIZE = 25;

const FILTER_OPTIONS: { value: ScheduleFilter; label: string }[] = [
  { value: "ALL", label: "All items" },
  { value: "CRITICAL", label: "Critical stock" },
  { value: "BELOW_REORDER", label: "Below reorder" },
  { value: "SHORTFALL", label: "Shortfall vs schedule" },
  { value: "REPLENISH", label: "Needs replenishment" },
  { value: "OK", label: "Covered & OK" },
];

function statusTone(status: StockStatus) {
  return status === "CRITICAL" ? "rose" : status === "BELOW_REORDER" ? "amber" : "emerald";
}

function statusLabel(status: StockStatus) {
  return status === "CRITICAL" ? "Critical" : status === "BELOW_REORDER" ? "Below reorder" : "OK";
}

export default function StockVsSchedulePage() {
  const [month, setMonth] = useState(currentMonth());
  const [family, setFamily] = useState("");
  const [statusFilter, setStatusFilter] = useState<ScheduleFilter>("ALL");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("shortfall");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const { from, to } = monthRange(month);
  const query = useApiQuery<SchedulePage>(
    `/stock-vs-schedule${qs({
      date_from: from,
      date_to: to,
      family,
      status: statusFilter,
      sort,
      order,
      page,
      page_size: PAGE_SIZE,
    })}`,
  );
  const familiesQuery = useApiQuery<{ families: string[] }>("/items/families");

  const data = query.data;
  const summary = data?.summary;
  const families = familiesQuery.data?.families ?? [];

  function handleSort(column: string) {
    if (sort === column) {
      setOrder((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSort(column);
      setOrder(column === "name" ? "asc" : "desc");
    }
    setPage(1);
  }

  function applyFilter(filter: ScheduleFilter) {
    setStatusFilter(filter);
    setPage(1);
  }

  const cards = [
    {
      label: "Shortfall items",
      value: summary ? String(summary.shortfall_items) : "–",
      hint: "stock below planned demand",
      icon: AlertTriangle,
      classes: "text-rose-600 bg-rose-50 ring-rose-100",
      filter: "SHORTFALL" as ScheduleFilter,
    },
    {
      label: "Total shortfall",
      value: summary ? formatQuantity(summary.total_shortfall) : "–",
      hint: "units across all items",
      icon: ArrowDownRight,
      classes: "text-amber-600 bg-amber-50 ring-amber-100",
      filter: "SHORTFALL" as ScheduleFilter,
    },
    {
      label: "Critical stock",
      value: summary ? String(summary.critical) : "–",
      hint: "below critical level",
      icon: ShieldAlert,
      classes: "text-rose-600 bg-rose-50 ring-rose-100",
      filter: "CRITICAL" as ScheduleFilter,
    },
    {
      label: "Needs replenishment",
      value: summary ? String(summary.needs_replenishment) : "–",
      hint: "shortfall or below reorder",
      icon: PackageSearch,
      classes: "text-indigo-600 bg-indigo-50 ring-indigo-100",
      filter: "REPLENISH" as ScheduleFilter,
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Stock vs Schedule"
        description="Compare available stock with planned dispatch quantities for the selected period."
      />

      {query.error && <Alert tone="error">{query.error}</Alert>}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="lg:w-52">
            <Field label="Period month" htmlFor="svs-month">
              <Input
                id="svs-month"
                type="month"
                value={month}
                onChange={(event) => {
                  setMonth(event.target.value || currentMonth());
                  setPage(1);
                }}
              />
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:w-96">
            <Field label="Family" htmlFor="svs-family">
              <Select
                id="svs-family"
                value={family}
                onChange={(event) => {
                  setFamily(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All families</option>
                {families.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Filter" htmlFor="svs-filter">
              <Select
                id="svs-filter"
                value={statusFilter}
                onChange={(event) => applyFilter(event.target.value as ScheduleFilter)}
              >
                {FILTER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <p className="text-xs text-slate-500 lg:ml-auto lg:pb-2.5">
            Period: <span className="font-medium text-slate-700">{formatDate(from)}</span> –{" "}
            <span className="font-medium text-slate-700">{formatDate(to)}</span>
          </p>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {cards.map(({ label, value, hint, icon: Icon, classes, filter }) => (
          <button
            key={label}
            type="button"
            onClick={() => applyFilter(filter)}
            className={cn(
              "rounded-xl border bg-white p-3.5 text-left shadow-sm transition-all hover:border-slate-300 hover:shadow",
              statusFilter === filter
                ? "border-slate-300 ring-2 ring-indigo-500/20"
                : "border-slate-200",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">{label}</span>
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-lg ring-1 ring-inset",
                  classes,
                )}
              >
                <Icon className="h-3.5 w-3.5" />
              </span>
            </div>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
            <p className="mt-0.5 text-xs text-slate-500">{hint}</p>
          </button>
        ))}
      </section>

      <p className="rounded-lg bg-slate-100/70 px-3.5 py-2.5 text-xs leading-relaxed text-slate-500">
        Planned quantity counts dispatch plans dated inside the period that are not yet completed.
        Shortfall is the positive difference between planned quantity and available stock.
      </p>

      <TableShell
        footer={
          data && data.total > 0 ? (
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              pageSize={data.page_size}
              onPageChange={setPage}
            />
          ) : null
        }
      >
        <table className="min-w-full divide-y divide-slate-100 text-sm">
          <thead className="bg-slate-50/70">
            <tr>
              <SortHeader
                label="Item"
                column="name"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Family
              </th>
              <SortHeader
                label="Available"
                column="available"
                sort={sort}
                order={order}
                onSort={handleSort}
                align="right"
              />
              <SortHeader
                label="Planned"
                column="planned"
                sort={sort}
                order={order}
                onSort={handleSort}
                align="right"
              />
              <SortHeader
                label="Shortfall"
                column="shortfall"
                sort={sort}
                order={order}
                onSort={handleSort}
                align="right"
              />
              <SortHeader
                label="Stock status"
                column="status"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Replenishment
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {query.loading ? (
              <LoadingRow colSpan={7} />
            ) : !data || data.items.length === 0 ? (
              <EmptyRow colSpan={7} message="No items match these filters for the selected period." />
            ) : (
              data.items.map((row) => (
                <tr key={row.item_id} className="transition-colors hover:bg-slate-50/60">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{row.name}</p>
                    {row.flags.includes("SHORTFALL") && (
                      <p className="text-xs text-rose-600">Shortfall against schedule</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{row.family}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">
                    {formatQuantity(row.available)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700">
                    {formatQuantity(row.planned_quantity)}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-3 text-right font-semibold tabular-nums",
                      row.shortfall > 0 ? "text-rose-600" : "text-slate-400",
                    )}
                  >
                    {row.shortfall > 0 ? formatQuantity(row.shortfall) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={statusTone(row.stock_status)}>
                      {statusLabel(row.stock_status)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {row.needs_replenishment ? (
                      <Badge tone={row.shortfall > 0 ? "rose" : "amber"}>Replenish</Badge>
                    ) : (
                      <span className="text-xs text-slate-400">Covered</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </TableShell>

      {data && (
        <p className="text-xs text-slate-500">
          Showing {data.total} active {data.total === 1 ? "item" : "items"} for this period.
          Reorder and critical levels come from the Item Master.
        </p>
      )}
    </div>
  );
}
