"use client";

import { useState } from "react";
import { CalendarPlus, Pencil, Truck, XCircle } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { LoadingRow, TableShell } from "@/components/ui/page";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import {
  poStatusTone,
  type POLine,
  type PurchaseOrder,
} from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";

interface PurchaseOrderDetailModalProps {
  open: boolean;
  poId: number | null;
  writable: boolean;
  onClose: () => void;
  onEdit: (po: PurchaseOrder) => void;
  onPlan: (po: PurchaseOrder, line: POLine) => void;
  onDispatch: (po: PurchaseOrder, line: POLine) => void;
  onChanged: (message: string) => void;
}

export function PurchaseOrderDetailModal({
  open,
  poId,
  writable,
  onClose,
  onEdit,
  onPlan,
  onDispatch,
  onChanged,
}: PurchaseOrderDetailModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const query = useApiQuery<PurchaseOrder>(
    open && poId ? `/purchase-orders/${poId}` : null,
  );
  const po = query.data;

  async function handleCancel() {
    if (!po) return;
    if (
      !window.confirm(
        `Cancel ${po.po_number}? Cancelling is permanent and is blocked while plans or dispatches exist.`,
      )
    ) {
      return;
    }

    setError(null);
    setCancelling(true);
    try {
      const result = await api<{ message: string }>(`/purchase-orders/${po.id}/cancel`, {
        method: "POST",
      });
      onChanged(result.message);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to cancel the purchase order.");
      setCancelling(false);
    }
  }

  const cancellable = writable && po && po.status !== "CANCELLED" && po.status !== "COMPLETED";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={po ? po.po_number : "Purchase order"}
      description={po ? `${po.customer_name} · Unit ${po.unit_number}` : "Loading purchase order…"}
      size="lg"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            {cancellable && (
              <Button
                type="button"
                variant="ghost"
                className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                onClick={handleCancel}
                loading={cancelling}
                disabled={query.loading}
              >
                <XCircle className="h-4 w-4" />
                Cancel PO
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onClose} disabled={cancelling}>
              Close
            </Button>
            {writable && po && po.status !== "CANCELLED" && (
              <Button
                type="button"
                onClick={() => onEdit(po)}
                disabled={cancelling}
              >
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
            )}
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {query.error && <Alert tone="error">{query.error}</Alert>}

        {po && (
          <>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
              <span className="text-slate-500">
                PO date <span className="font-medium text-slate-800">{formatDate(po.po_date)}</span>
              </span>
              <span className="text-slate-500">
                Lines <span className="font-medium text-slate-800">{po.line_count}</span>
              </span>
              <Badge tone={poStatusTone(po.status)}>{po.status}</Badge>
            </div>

            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                ["Ordered", po.total_quantity],
                ["Planned", po.total_planned],
                ["Dispatched", po.total_dispatched],
                ["Balance", po.total_balance],
              ].map(([label, value]) => (
                <div
                  key={String(label)}
                  className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-slate-200 ring-inset"
                >
                  <dt className="text-xs text-slate-500">{label}</dt>
                  <dd className="mt-0.5 text-base font-semibold tabular-nums text-slate-900">
                    {formatQuantity(Number(value))}
                  </dd>
                </div>
              ))}
            </dl>

            <TableShell>
              <table className="min-w-full divide-y divide-slate-100 text-sm">
                <thead className="bg-slate-50/70">
                  <tr>
                    {[
                      "Item",
                      "Ordered",
                      "Planned",
                      "Dispatched",
                      "Balance",
                      "Available to plan",
                      "Actions",
                    ].map((label, index) => (
                      <th
                        key={label || index}
                        scope="col"
                        className={
                          index === 0
                            ? "px-3 py-2.5 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase"
                            : "px-3 py-2.5 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase"
                        }
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {po.lines.map((line) => (
                    <tr key={line.id} className="hover:bg-slate-50/60">
                      <td className="px-3 py-2.5">
                        <p className="font-medium text-slate-900">{line.item_name}</p>
                        <p className="text-xs text-slate-500">{line.item_family}</p>
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">
                        {formatQuantity(line.quantity)}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-amber-700">
                        {formatQuantity(line.planned_quantity)}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-indigo-700">
                        {formatQuantity(line.dispatched_quantity)}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">
                        {formatQuantity(line.balance_quantity)}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        {line.available_to_plan > 0 ? (
                          <span className="font-semibold tabular-nums text-emerald-700">
                            {formatQuantity(line.available_to_plan)}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">Fully planned</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {writable && po.status !== "CANCELLED" && line.balance_quantity > 0 && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onDispatch(po, line)}
                              title={`Dispatch ${line.item_name}`}
                            >
                              <Truck className="h-3.5 w-3.5" />
                              Dispatch
                            </Button>
                          )}
                          {writable && po.status !== "CANCELLED" && line.available_to_plan > 0 && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onPlan(po, line)}
                              title={`Plan a dispatch for ${line.item_name}`}
                            >
                              <CalendarPlus className="h-3.5 w-3.5" />
                              Plan
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
          </>
        )}

        {query.loading && (
          <TableShell>
            <table>
              <tbody>
                <LoadingRow colSpan={7} />
              </tbody>
            </table>
          </TableShell>
        )}
      </div>
    </Modal>
  );
}
