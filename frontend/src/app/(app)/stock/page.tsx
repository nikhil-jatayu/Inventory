"use client";

import { useEffect, useState } from "react";

import { AlertTriangle, ArrowDownToLine, Boxes, CheckCircle2, Plus, Search, SlidersHorizontal, TrendingDown, } from "lucide-react";

import { TransactionModal } from "@/components/stock/transaction-modal";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import { qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useDebouncedValue } from "@/lib/hooks";
import {
  canWrite,
  type Page,
  type StockRow,
  type StockStatus,
  type StockSummary,
  type StockTransaction,
  type StockTxnType,
} from "@/lib/types";
import { cn, formatDate, formatQuantity } from "@/lib/utils";

const PAGE_SIZE = 20;

const STATUS_OPTIONS: { value: StockStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "CRITICAL", label: "Critical" },
  { value: "BELOW_REORDER", label: "Below reorder" },
  { value: "OK", label: "OK" },
];

const TYPE_OPTIONS: { value: StockTxnType | ""; label: string }[] = [
  { value: "", label: "All entries" },
  { value: "RECEIPT", label: "Receipt" },
  { value: "OPENING", label: "Opening stock" },
  { value: "ADJUSTMENT", label: "Adjustment" },
  { value: "DISPATCH", label: "Dispatch" },
];

const TYPE_LABELS: Record<StockTxnType, string> = {
  OPENING: "Opening",
  RECEIPT: "Receipt",
  ADJUSTMENT: "Adjustment",
  DISPATCH: "Dispatch",
};

function statusTone(status: StockStatus) {
  return status === "CRITICAL" ? "rose" : status === "BELOW_REORDER" ? "amber" : "emerald";
}

function statusLabel(status: StockStatus) {
  return status === "CRITICAL" ? "Critical" : status === "BELOW_REORDER" ? "Below reorder" : "OK";
}

function txnTone(type: StockTxnType) {
  if (type === "RECEIPT") return "emerald";
  if (type === "OPENING") return "sky";
  if (type === "DISPATCH") return "indigo";
  return "slate";
}

export default function StockPage() {
  const { user } = useAuth();
  const writable = canWrite(user?.role, "stock");

  const [tab, setTab] = useState<"status" | "transactions">("status");
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [family, setFamily] = useState("");
  const [statusFilter, setStatusFilter] = useState<StockStatus | "">("");
  const [statusPage, setStatusPage] = useState(1);
  const [statusSort, setStatusSort] = useState("status");
  const [statusOrder, setStatusOrder] = useState<"asc" | "desc">("asc");

  const [txSearch, setTxSearch] = useState("");
  const debouncedTxSearch = useDebouncedValue(txSearch);
  const [txType, setTxType] = useState<StockTxnType | "">("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [txPage, setTxPage] = useState(1);
  const [txSort, setTxSort] = useState("date");
  const [txOrder, setTxOrder] = useState<"asc" | "desc">("desc");

  const [modal, setModal] = useState<{
    open: boolean;
    item: StockRow | null;
    type: "OPENING" | "RECEIPT" | "ADJUSTMENT";
  }>({ open: false, item: null, type: "RECEIPT" });

  const summaryQuery = useApiQuery<StockSummary>("/stock/summary", refresh);
  const familiesQuery = useApiQuery<{ families: string[] }>("/items/families", refresh);
  const statusQuery = useApiQuery<Page<StockRow>>(
    tab === "status"
      ? `/stock/status${qs({
          search: debouncedSearch,
          family,
          status: statusFilter,
          sort: statusSort,
          order: statusOrder,
          page: statusPage,
          page_size: PAGE_SIZE,
        })}`
      : null,
    refresh,
  );
  const txQuery = useApiQuery<Page<StockTransaction>>(
    tab === "transactions"
      ? `/stock/transactions${qs({
          search: debouncedTxSearch,
          type: txType,
          date_from: dateFrom,
          date_to: dateTo,
          sort: txSort,
          order: txOrder,
          page: txPage,
          page_size: PAGE_SIZE,
        })}`
      : null,
    refresh,
  );

  const summary = summaryQuery.data;
  const families = familiesQuery.data?.families ?? [];
  const statusData = statusQuery.data;
  const statusLoading = statusQuery.loading;
  const txData = txQuery.data;
  const txLoading = txQuery.loading;
  const loadError = tab === "status" ? statusQuery.error : txQuery.error;

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timer);
  }, [notice]);

  function handleStatusSort(column: string) {
    if (statusSort === column) {
      setStatusOrder((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setStatusSort(column);
      setStatusOrder(column === "available" ? "desc" : "asc");
    }
    setStatusPage(1);
  }

  function handleTxSort(column: string) {
    if (txSort === column) {
      setTxOrder((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setTxSort(column);
      setTxOrder(column === "date" ? "desc" : "asc");
    }
    setTxPage(1);
  }

  function applyStatusFilter(status: StockStatus | "") {
    setStatusFilter(status);
    setStatusPage(1);
    setTab("status");
  }

  function openEntry(item: StockRow | null, type: "OPENING" | "RECEIPT" | "ADJUSTMENT") {
    setModal({ open: true, item, type });
  }

  const summaryCards = [
    {
      key: "CRITICAL" as const,
      label: "Critical",
      value: summary?.critical ?? 0,
      icon: AlertTriangle,
      classes: "text-rose-600 bg-rose-50 ring-rose-100",
      selected: statusFilter === "CRITICAL",
    },
    {
      key: "BELOW_REORDER" as const,
      label: "Below reorder",
      value: summary?.below_reorder ?? 0,
      icon: TrendingDown,
      classes: "text-amber-600 bg-amber-50 ring-amber-100",
      selected: statusFilter === "BELOW_REORDER",
    },
    {
      key: "OK" as const,
      label: "OK",
      value: summary?.ok ?? 0,
      icon: CheckCircle2,
      classes: "text-emerald-600 bg-emerald-50 ring-emerald-100",
      selected: statusFilter === "OK",
    },
    {
      key: "" as const,
      label: "Active items",
      value: summary?.total_items ?? 0,
      icon: Boxes,
      classes: "text-slate-600 bg-slate-100 ring-slate-200",
      selected: statusFilter === "",
    },
  ];

  const statusColumns = writable ? 7 : 6;
  const txColumns = 6;

  const fixedItem = modal.item
    ? { id: modal.item.item_id, name: modal.item.name, family: modal.item.family }
    : null;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Stock"
        description="Available stock is calculated from the transaction ledger — it is never edited directly."
        actions={
          writable && (
            <Button onClick={() => openEntry(null, "RECEIPT")}>
              <Plus className="h-4 w-4" />
              New stock entry
            </Button>
          )
        }
      />

      {notice && (
        <Alert tone="success" onDismiss={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {loadError && <Alert tone="error">{loadError}</Alert>}

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {summaryCards.map(({ key, label, value, icon: Icon, classes, selected }) => (
          <button
            key={label}
            type="button"
            onClick={() => applyStatusFilter(key)}
            className={cn(
              "rounded-xl border bg-white p-3.5 text-left shadow-sm transition-all hover:border-slate-300 hover:shadow",
              selected ? "border-slate-300 ring-2 ring-indigo-500/20" : "border-slate-200",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">{label}</span>
              <span className={cn("flex h-7 w-7 items-center justify-center rounded-lg ring-1 ring-inset", classes)}>
                <Icon className="h-3.5 w-3.5" />
              </span>
            </div>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
              {summary ? value : "–"}
            </p>
          </button>
        ))}
      </section>

      <div className="border-b border-slate-200">
        <nav className="-mb-px flex gap-5" aria-label="Stock views">
          {(
            [
              { key: "status", label: "Stock status" },
              { key: "transactions", label: "Transaction ledger" },
            ] as const
          ).map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={cn(
                "border-b-2 px-1 pb-2.5 text-sm font-medium transition-colors",
                tab === key
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700",
              )}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "status" ? (
        <>
          <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setStatusPage(1);
                  }}
                  placeholder="Search stock by item or family"
                  className="pl-9"
                  aria-label="Search stock"
                />
              </div>
              <div className="grid grid-cols-2 gap-3 lg:w-96">
                <Field label="Family" htmlFor="stock-family">
                  <Select
                    id="stock-family"
                    value={family}
                    onChange={(event) => {
                      setFamily(event.target.value);
                      setStatusPage(1);
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
                <Field label="Status" htmlFor="stock-status">
                  <Select
                    id="stock-status"
                    value={statusFilter}
                    onChange={(event) => applyStatusFilter(event.target.value as StockStatus | "")}
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option.value || "all"} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              {(search || family || statusFilter) && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setSearch("");
                    setFamily("");
                    setStatusFilter("");
                    setStatusPage(1);
                  }}
                >
                  <SlidersHorizontal className="h-4 w-4" />
                  Reset
                </Button>
              )}
            </div>
          </section>

          <TableShell
            footer={
              statusData && statusData.total > 0 ? (
                <Pagination
                  page={statusData.page}
                  pages={statusData.pages}
                  total={statusData.total}
                  pageSize={statusData.page_size}
                  onPageChange={setStatusPage}
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
                    sort={statusSort}
                    order={statusOrder}
                    onSort={handleStatusSort}
                  />
                  <SortHeader
                    label="Family"
                    column="family"
                    sort={statusSort}
                    order={statusOrder}
                    onSort={handleStatusSort}
                  />
                  <SortHeader
                    label="Available"
                    column="available"
                    sort={statusSort}
                    order={statusOrder}
                    onSort={handleStatusSort}
                  />
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Reorder
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Critical
                  </th>
                  <SortHeader
                    label="Status"
                    column="status"
                    sort={statusSort}
                    order={statusOrder}
                    onSort={handleStatusSort}
                  />
                  {writable && (
                    <th scope="col" className="px-4 py-3 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">
                      Actions
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {statusLoading ? (
                  <LoadingRow colSpan={statusColumns} />
                ) : !statusData || statusData.items.length === 0 ? (
                  <EmptyRow colSpan={statusColumns} message="No active items match these filters." />
                ) : (
                  statusData.items.map((row) => (
                    <tr key={row.item_id} className="transition-colors hover:bg-slate-50/60">
                      <td className="px-4 py-3 font-medium text-slate-900">{row.name}</td>
                      <td className="px-4 py-3 text-slate-600">{row.family}</td>
                      <td className="px-4 py-3 font-semibold tabular-nums text-slate-900">
                        {formatQuantity(row.available)}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-slate-500">
                        {formatQuantity(row.reorder_level)}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-slate-500">
                        {formatQuantity(row.critical_level)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={statusTone(row.status)}>{statusLabel(row.status)}</Badge>
                      </td>
                      {writable && (
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEntry(row, "RECEIPT")}
                              title="Receive stock"
                            >
                              <ArrowDownToLine className="h-3.5 w-3.5" />
                              Receive
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEntry(row, "ADJUSTMENT")}
                            >
                              Adjust
                            </Button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </TableShell>
        </>
      ) : (
        <>
          <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-end">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  value={txSearch}
                  onChange={(event) => {
                    setTxSearch(event.target.value);
                    setTxPage(1);
                  }}
                  placeholder="Search by item or reference"
                  className="pl-9"
                  aria-label="Search stock entries"
                />
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:w-[34rem]">
                <Field label="Entry type" htmlFor="tx-type">
                  <Select
                    id="tx-type"
                    value={txType}
                    onChange={(event) => {
                      setTxType(event.target.value as StockTxnType | "");
                      setTxPage(1);
                    }}
                  >
                    {TYPE_OPTIONS.map((option) => (
                      <option key={option.value || "all"} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="From" htmlFor="tx-from">
                  <Input
                    id="tx-from"
                    type="date"
                    value={dateFrom}
                    onChange={(event) => {
                      setDateFrom(event.target.value);
                      setTxPage(1);
                    }}
                  />
                </Field>
                <Field label="To" htmlFor="tx-to">
                  <Input
                    id="tx-to"
                    type="date"
                    value={dateTo}
                    onChange={(event) => {
                      setDateTo(event.target.value);
                      setTxPage(1);
                    }}
                  />
                </Field>
              </div>
              {(txSearch || txType || dateFrom || dateTo) && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setTxSearch("");
                    setTxType("");
                    setDateFrom("");
                    setDateTo("");
                    setTxPage(1);
                  }}
                >
                  <SlidersHorizontal className="h-4 w-4" />
                  Reset
                </Button>
              )}
            </div>
          </section>

          <TableShell
            footer={
              txData && txData.total > 0 ? (
                <Pagination
                  page={txData.page}
                  pages={txData.pages}
                  total={txData.total}
                  pageSize={txData.page_size}
                  onPageChange={setTxPage}
                />
              ) : null
            }
          >
            <table className="min-w-full divide-y divide-slate-100 text-sm">
              <thead className="bg-slate-50/70">
                <tr>
                  <SortHeader
                    label="Date"
                    column="date"
                    sort={txSort}
                    order={txOrder}
                    onSort={handleTxSort}
                  />
                  <SortHeader
                    label="Item"
                    column="item"
                    sort={txSort}
                    order={txOrder}
                    onSort={handleTxSort}
                  />
                  <SortHeader
                    label="Type"
                    column="type"
                    sort={txSort}
                    order={txOrder}
                    onSort={handleTxSort}
                  />
                  <SortHeader
                    label="Quantity"
                    column="quantity"
                    sort={txSort}
                    order={txOrder}
                    onSort={handleTxSort}
                  />
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Reference
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                    Remarks
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {txLoading ? (
                  <LoadingRow colSpan={txColumns} />
                ) : !txData || txData.items.length === 0 ? (
                  <EmptyRow colSpan={txColumns} message="No stock entries match these filters." />
                ) : (
                  txData.items.map((txn) => (
                    <tr key={txn.id} className="transition-colors hover:bg-slate-50/60">
                      <td className="px-4 py-3 whitespace-nowrap text-slate-600">{formatDate(txn.date)}</td>
                      <td className="px-4 py-3 font-medium text-slate-900">{txn.item_name}</td>
                      <td className="px-4 py-3">
                        <Badge tone={txnTone(txn.type)}>{TYPE_LABELS[txn.type]}</Badge>
                      </td>
                      <td
                        className={cn(
                          "px-4 py-3 font-semibold tabular-nums",
                          txn.quantity < 0 ? "text-rose-600" : "text-emerald-700",
                        )}
                      >
                        {txn.quantity > 0 ? "+" : ""}
                        {formatQuantity(txn.quantity)}
                      </td>
                      <td className="px-4 py-3 text-slate-600">{txn.ref ?? "—"}</td>
                      <td className="max-w-64 truncate px-4 py-3 text-slate-500" title={txn.remarks ?? ""}>
                        {txn.remarks ?? "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </TableShell>
        </>
      )}

      <TransactionModal
        key={`${modal.open}-${modal.item?.item_id ?? "new"}-${modal.type}`}
        open={modal.open}
        fixedItem={fixedItem}
        defaultType={modal.type}
        onClose={() => setModal((current) => ({ ...current, open: false }))}
        onSaved={(message) => {
          setModal((current) => ({ ...current, open: false }));
          setNotice(message);
          setRefresh((value) => value + 1);
        }}
      />
    </div>
  );
}