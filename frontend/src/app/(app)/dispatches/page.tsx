"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  ClipboardList,
  Search,
  SlidersHorizontal,
  Target,
  TrendingUp,
  Truck,
} from "lucide-react";

import { DispatchModal } from "@/components/dispatches/dispatch-modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import {
  EmptyRow,
  LoadingRow,
  PageHeader,
  SortHeader,
  TableShell,
} from "@/components/ui/page";
import { Pagination } from "@/components/ui/pagination";
import { StatCard } from "@/components/ui/stat-card";
import { qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useDebouncedValue } from "@/lib/hooks";
import {
  canWrite,
  type DispatchRecord,
  type DispatchReport,
  type Page,
} from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";

const DispatchCharts = dynamic(
  () => import("@/components/dispatches/dispatch-charts").then((module) => module.DispatchCharts),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-72 items-center justify-center rounded-xl border border-slate-200 bg-white text-sm text-slate-500 shadow-sm">
        Loading charts…
      </div>
    ),
  },
);

const PAGE_SIZE = 20;

export default function DispatchesPage() {
  const { user } = useAuth();
  const writable = canWrite(user?.role, "dispatches");

  const [fy, setFy] = useState("");
  const [family, setFamily] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("dispatch_date");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const reportQuery = useApiQuery<DispatchReport>(
    `/reports/dispatch${qs({ fy, family })}`,
    refresh,
  );
  const familiesQuery = useApiQuery<{ families: string[] }>("/items/families", refresh);
  const listQuery = useApiQuery<Page<DispatchRecord>>(
    `/dispatches${qs({
      search: debouncedSearch,
      date_from: dateFrom,
      date_to: dateTo,
      family,
      sort,
      order,
      page,
      page_size: PAGE_SIZE,
    })}`,
    refresh,
  );

  const report = reportQuery.data;
  const families = familiesQuery.data?.families ?? [];
  const records = listQuery.data;
  const activeFy = fy || report?.fy || "";

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timer);
  }, [notice]);

  function handleSort(column: string) {
    if (sort === column) {
      setOrder((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSort(column);
      setOrder(column === "dispatch_date" ? "desc" : "asc");
    }
    setPage(1);
  }

  function resetReportFilters() {
    setFy("");
    setFamily("");
  }

  function resetRecordFilters() {
    setSearch("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  }

  function handleSaved(message: string) {
    setModalOpen(false);
    setNotice(message);
    setRefresh((value) => value + 1);
  }

  const reportSummary = report
    ? [
        {
          label: "Net Sales (FY)",
          value: formatQuantity(report.total_sales),
          hint: activeFy ? `Actual dispatches · ${activeFy}` : "Selected financial year",
          icon: Truck,
          tone: "indigo" as const,
        },
        {
          label: "Total Dispatch Plan (FY)",
          value: formatQuantity(report.total_planned),
          hint: "Planned quantities dated in the year",
          icon: Target,
          tone: "amber" as const,
        },
        {
          label: "Cumulative dispatched",
          value: formatQuantity(report.cumulative_dispatched),
          hint: `All dispatches through ${formatDate(report.fy_end)}`,
          icon: TrendingUp,
          tone: "emerald" as const,
        },
        {
          label: "Dispatch records",
          value: String(report.dispatch_count),
          hint: "Recorded in the selected year",
          icon: ClipboardList,
          tone: "sky" as const,
        },
      ]
    : [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Actual Dispatch"
        description="Record actual quantities against a selected dispatch plan. Each dispatch updates stock and creates a sales invoice automatically."
        actions={
          writable && (
            <Button onClick={() => setModalOpen(true)}>
              <Truck className="h-4 w-4" />
              Record dispatch
            </Button>
          )
        }
      />

      {notice && (
        <Alert tone="success" onDismiss={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {reportQuery.error && <Alert tone="error">{reportQuery.error}</Alert>}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid grid-cols-2 gap-3 sm:w-[24rem]">
            <Field label="Financial year" htmlFor="dispatch-fy">
              <Select
                id="dispatch-fy"
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
            <Field label="Family" htmlFor="dispatch-family">
              <Select
                id="dispatch-family"
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
          {(fy || family) && (
            <Button variant="ghost" onClick={resetReportFilters}>
              <SlidersHorizontal className="h-4 w-4" />
              Reset
            </Button>
          )}
          {report && (
            <p className="text-xs text-slate-500 sm:ml-auto">
              {formatDate(report.fy_start)} – {formatDate(report.fy_end)} · April–March
            </p>
          )}
        </div>
      </section>

      {report && (
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {reportSummary.map((card) => (
            <StatCard key={card.label} {...card} />
          ))}
        </section>
      )}

      {report && <DispatchCharts report={report} />}

      {report && (
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Monthly summary</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Planned quantities, actual dispatches and net sales after linked unit rejections for {report.fy}.
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 text-sm">
              <thead className="bg-slate-50/70">
                <tr>
                  <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Month
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Planned
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Dispatched
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Net Sales
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Cumulative
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {report.months.map((month) => (
                  <tr key={month.month} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2 font-medium whitespace-nowrap text-slate-800">
                      {month.label}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-amber-700">
                      {formatQuantity(month.planned)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-indigo-700">
                      {formatQuantity(month.dispatched)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-emerald-700">
                      {formatQuantity(month.sales)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-700">
                      {formatQuantity(month.cumulative)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-50/70">
                <tr className="border-t border-slate-200">
                  <td className="px-4 py-2.5 text-xs font-semibold tracking-wide text-slate-700 uppercase">
                    FY total
                  </td>
                  <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-amber-700">
                    {formatQuantity(report.total_planned)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-indigo-700">
                    {formatQuantity(report.total_dispatched)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-slate-700">
                    {formatQuantity(report.months.at(-1)?.cumulative ?? 0)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Search by item, PO, customer, unit or remarks"
              className="pl-9"
              aria-label="Search dispatches"
            />
          </div>
          <div className="grid grid-cols-2 gap-3 sm:w-80">
            <Field label="From" htmlFor="dispatch-from">
              <Input
                id="dispatch-from"
                type="date"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(event) => {
                  setDateFrom(event.target.value);
                  setPage(1);
                }}
              />
            </Field>
            <Field label="To" htmlFor="dispatch-to">
              <Input
                id="dispatch-to"
                type="date"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(event) => {
                  setDateTo(event.target.value);
                  setPage(1);
                }}
              />
            </Field>
          </div>
          {(search || dateFrom || dateTo) && (
            <Button variant="ghost" onClick={resetRecordFilters}>
              <SlidersHorizontal className="h-4 w-4" />
              Reset
            </Button>
          )}
        </div>
      </section>

      {listQuery.error && <Alert tone="error">{listQuery.error}</Alert>}

      <TableShell
        footer={
          records && records.total > 0 ? (
            <Pagination
              page={records.page}
              pages={records.pages}
              total={records.total}
              pageSize={records.page_size}
              onPageChange={setPage}
            />
          ) : null
        }
      >
        <table className="min-w-full divide-y divide-slate-100 text-sm">
          <thead className="bg-slate-50/70">
            <tr>
              <SortHeader
                label="Date"
                column="dispatch_date"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <SortHeader
                label="Item"
                column="item"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <SortHeader
                label="PO / customer"
                column="po_number"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <SortHeader
                label="Quantity"
                column="quantity"
                sort={sort}
                order={order}
                onSort={handleSort}
                align="right"
              />
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Remarks
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {listQuery.loading ? (
              <LoadingRow colSpan={5} />
            ) : !records || records.items.length === 0 ? (
              <EmptyRow
                colSpan={5}
                message={
                  writable
                    ? "No dispatches match these filters. Record one to start the ledger."
                    : "No dispatches match these filters."
                }
              />
            ) : (
              records.items.map((record) => (
                <tr key={record.id} className="transition-colors hover:bg-slate-50/60">
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                    {formatDate(record.dispatch_date)}
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{record.item_name}</p>
                    <p className="text-xs text-slate-500">{record.project} · {record.item_family}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium whitespace-nowrap text-slate-900">
                      {record.invoice_number ?? "—"}
                    </p>
                    <p className="text-xs text-slate-500">
                      {record.po_number ? `PO ${record.po_number}` : "No PO reference"} · {record.unit_name ?? record.unit_number ?? "Unit not set"}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-indigo-700">
                    {formatQuantity(record.quantity)}
                  </td>
                  <td
                    className="max-w-64 truncate px-4 py-3 text-slate-500"
                    title={record.remarks ?? ""}
                  >
                    {record.remarks ?? "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </TableShell>

      {modalOpen && (
        <DispatchModal key="new-dispatch" open onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      )}
    </div>
  );
}
