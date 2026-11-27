"use client";

import { useState } from "react";
import { Pencil, XCircle } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { LoadingRow, TableShell } from "@/components/ui/page";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import {
  poStatusTone,
  type PurchaseOrder,
  type Unit,
} from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";

interface PurchaseOrderDetailModalProps {
  open: boolean;
  poId: number | null;
  writable: boolean;
  onClose: () => void;
  onEdit: (po: PurchaseOrder) => void;
  onChanged: (message: string) => void;
}

export function PurchaseOrderDetailModal({
  open,
  poId,
  writable,
  onClose,
  onEdit,
  onChanged,
}: PurchaseOrderDetailModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const query = useApiQuery<PurchaseOrder>(
    open && poId ? `/purchase-orders/${poId}` : null,
  );
  const po = query.data;
  const unitsQuery = useApiQuery<Unit[]>(open ? "/units?include_inactive=true" : null);
  const unitNames = (po?.unit_ids ?? []).map((id) => unitsQuery.data?.find((unit) => unit.id === id)?.name ?? `Unit #${id}`);

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
      description={po ? `Bookkeeping reference · ${formatDate(po.po_date)}` : "Loading purchase order…"}
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
              <span className="text-slate-500">
                Units <span className="font-medium text-slate-800">{unitNames.length ? unitNames.join(", ") : "Not assigned"}</span>
              </span>
              <Badge tone={poStatusTone(po.status)}>{po.status}</Badge>
            </div>

            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-slate-200 ring-inset">
                <dt className="text-xs text-slate-500">PO item quantity</dt>
                <dd className="mt-0.5 text-base font-semibold tabular-nums text-slate-900">{formatQuantity(po.total_quantity)}</dd>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-slate-200 ring-inset">
                <dt className="text-xs text-slate-500">Item lines</dt>
                <dd className="mt-0.5 text-base font-semibold tabular-nums text-slate-900">{po.line_count}</dd>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-slate-200 ring-inset">
                <dt className="text-xs text-slate-500">Status</dt>
                <dd className="mt-0.5"><Badge tone={poStatusTone(po.status)}>{po.status}</Badge></dd>
              </div>
            </dl>

            <TableShell>
              <table className="min-w-full divide-y divide-slate-100 text-sm">
                <thead className="bg-slate-50/70">
                  <tr>
                    {[
                      "Item",
                      "Quantity",
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
                        <p className="text-xs text-slate-500">{line.project} · {line.item_family}</p>
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">
                        {formatQuantity(line.quantity)}
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
                <LoadingRow colSpan={2} />
              </tbody>
            </table>
          </TableShell>
        )}
      </div>
    </Modal>
  );
}
