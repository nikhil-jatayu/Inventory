"use client";

import { useEffect, useState } from "react";
import { Eye, Plus, Search, SlidersHorizontal } from "lucide-react";

import { PurchaseOrderDetailModal } from "@/components/purchase-orders/po-detail-modal";
import { PurchaseOrderModal } from "@/components/purchase-orders/po-modal";
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
  poStatusTone,
  type POStatus,
  type Page,
  type PurchaseOrder,
  type PurchaseOrderSummary,
  type Unit,
} from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";

const PAGE_SIZE = 20;

const STATUS_OPTIONS: { value: POStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "OPEN", label: "Open" },
  { value: "PARTIAL", label: "Partial" },
  { value: "COMPLETED", label: "Completed" },
  { value: "CANCELLED", label: "Cancelled" },
];

const STATUS_LABELS: Record<POStatus, string> = {
  OPEN: "Open",
  PARTIAL: "Partial",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export default function PurchaseOrdersPage() {
  const { user } = useAuth();
  const writable = canWrite(user?.role, "purchase_orders");

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [statusFilter, setStatusFilter] = useState<POStatus | "">("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("po_date");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  const [poModal, setPoModal] = useState<{ open: boolean; po: PurchaseOrder | null }>({
    open: false,
    po: null,
  });
  const [detailId, setDetailId] = useState<number | null>(null);

  const query = useApiQuery<Page<PurchaseOrderSummary>>(
    `/purchase-orders${qs({
      search: debouncedSearch,
      status: statusFilter,
      sort,
      order,
      page,
      page_size: PAGE_SIZE,
    })}`,
    refresh,
  );

  const data = query.data;
  const loading = query.loading;
  const columns = 7;
  const units = useApiQuery<Unit[]>("/units?include_inactive=true");

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
      setOrder(column === "po_date" ? "desc" : "asc");
    }
    setPage(1);
  }

  function openCreate() {
    setPoModal({ open: true, po: null });
  }

  function openEdit(po: PurchaseOrder) {
    setDetailId(null);
    setPoModal({ open: true, po });
  }

  function handleSaved(message: string) {
    setPoModal({ open: false, po: null });
    setNotice(message);
    setRefresh((value) => value + 1);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Purchase Orders"
        description="PO numbers and item quantities maintained for bookkeeping only. Dispatch plans and sales are managed independently."
        actions={
          writable && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New purchase order
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
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Search by eight-digit PO number"
              className="pl-9"
              aria-label="Search purchase orders"
            />
          </div>
          <div className="lg:w-52">
            <Field label="Status" htmlFor="po-status-filter">
              <Select
                id="po-status-filter"
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.target.value as POStatus | "");
                  setPage(1);
                }}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {(search || statusFilter) && (
            <Button
              variant="ghost"
              onClick={() => {
                setSearch("");
                setStatusFilter("");
                setPage(1);
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
                label="PO number"
                column="po_number"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <SortHeader
                label="PO date"
                column="po_date"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <th className="px-4 py-3 text-left text-xs uppercase text-slate-500">Units / Locations</th>
              <th scope="col" className="px-4 py-3 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">Items</th>
              <th scope="col" className="px-4 py-3 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">Total quantity</th>
              <SortHeader
                label="Status"
                column="status"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <th scope="col" className="px-4 py-3 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <LoadingRow colSpan={columns} />
            ) : !data || data.items.length === 0 ? (
              <EmptyRow
                colSpan={columns}
                message={
                  writable
                    ? "No purchase orders match these filters. Create one to keep the PO reference on record."
                    : "No purchase orders match these filters."
                }
              />
            ) : (
              data.items.map((po) => (
                <tr key={po.id} className="transition-colors hover:bg-slate-50/60">
                  <td className="px-4 py-3">
                    <p className="font-medium whitespace-nowrap text-slate-900">{po.po_number}</p>
                    <p className="text-xs text-slate-500">
                      {po.line_count}{" "}
                      {po.line_count === 1 ? "line" : "lines"}
                    </p>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                    {formatDate(po.po_date)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{po.unit_ids.map(id=>units.data?.find(u=>u.id===id)?.name??`#${id}`).join(", ")||po.unit_number||"—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-600">{po.line_count}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{formatQuantity(po.total_quantity)}</td>
                  <td className="px-4 py-3">
                    <Badge tone={poStatusTone(po.status)}>{STATUS_LABELS[po.status]}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="ghost" size="sm" onClick={() => setDetailId(po.id)}>
                      <Eye className="h-3.5 w-3.5" />
                      View
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </TableShell>

      {detailId !== null && (
        <PurchaseOrderDetailModal
          key={detailId}
          open
          poId={detailId}
          writable={writable}
          onClose={() => setDetailId(null)}
          onEdit={openEdit}
          onChanged={(message) => {
            setNotice(message);
            setRefresh((value) => value + 1);
          }}
        />
      )}

      {poModal.open && (
        <PurchaseOrderModal
          key={poModal.po?.id ?? "new"}
          open
          po={poModal.po}
          onClose={() => setPoModal({ open: false, po: null })}
          onSaved={handleSaved}
        />
      )}

    </div>
  );
}
