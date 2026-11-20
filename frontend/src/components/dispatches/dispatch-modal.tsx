"use client";

import { useState } from "react";
import { Truck } from "lucide-react";

import { POLinePicker } from "@/components/planning/po-line-picker";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import type { POLineOption } from "@/lib/types";
import { formatQuantity, todayISO } from "@/lib/utils";

export interface DispatchLineContext {
  po_line_id: number;
  po_number: string;
  customer_name: string;
  unit_number: string;
  item_name: string;
  item_family: string;
  quantity: number;
  planned_quantity: number;
  dispatched_quantity: number;
  balance_quantity: number;
}

export function dispatchLineFromOption(option: POLineOption): DispatchLineContext {
  return {
    po_line_id: option.po_line_id,
    po_number: option.po_number,
    customer_name: option.customer_name,
    unit_number: option.unit_number,
    item_name: option.item_name,
    item_family: option.item_family,
    quantity: option.quantity,
    planned_quantity: option.planned_quantity,
    dispatched_quantity: option.dispatched_quantity,
    balance_quantity: option.balance_quantity,
  };
}

interface DispatchModalProps {
  open: boolean;
  line?: DispatchLineContext | null;
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function DispatchModal({ open, line, onClose, onSaved }: DispatchModalProps) {
  const [picked, setPicked] = useState<POLineOption | null>(null);
  const [dispatchDate, setDispatchDate] = useState(todayISO());
  const [quantity, setQuantity] = useState("");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const context = line ?? (picked ? dispatchLineFromOption(picked) : null);
  const maxQuantity = context?.balance_quantity ?? 0;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!context) {
      setError("Select a purchase order line.");
      return;
    }
    const value = Number(quantity);
    if (!quantity.trim() || !Number.isFinite(value) || value <= 0) {
      setError("Enter a dispatch quantity greater than zero.");
      return;
    }
    if (value > maxQuantity) {
      setError(`Dispatch quantity cannot exceed the line balance of ${formatQuantity(maxQuantity)}.`);
      return;
    }

    setSaving(true);
    try {
      await api("/dispatches", {
        method: "POST",
        body: {
          po_line_id: context.po_line_id,
          dispatch_date: dispatchDate,
          quantity: value,
          remarks: remarks.trim() || null,
        },
      });
      onSaved(
        `Dispatch of ${formatQuantity(value)} ${context.item_name} recorded against ${context.po_number}.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to record the dispatch.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Record dispatch"
      description="Post an actual dispatched quantity. Stock and planning status update automatically."
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="dispatch-form" loading={saving}>
            <Truck className="h-4 w-4" />
            Record dispatch
          </Button>
        </div>
      }
    >
      <form id="dispatch-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}

        {!line && (
          <Field label="Purchase order line" required>
            <POLinePicker
              value={picked}
              onChange={setPicked}
              disabled={saving}
              mode="dispatch"
            />
          </Field>
        )}

        {context && (
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-slate-900">{context.item_name}</p>
                <p className="text-xs text-slate-500">
                  {context.po_number} · {context.customer_name} · {context.unit_number}
                </p>
              </div>
              <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-slate-200 ring-inset">
                {context.item_family}
              </span>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
              {[
                ["Ordered", context.quantity],
                ["Planned", context.planned_quantity],
                ["Dispatched", context.dispatched_quantity],
                ["Balance", context.balance_quantity],
              ].map(([label, value]) => (
                <div
                  key={String(label)}
                  className="rounded-lg bg-white px-2.5 py-2 ring-1 ring-slate-200 ring-inset"
                >
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="mt-0.5 text-sm font-semibold tabular-nums text-slate-900">
                    {formatQuantity(Number(value))}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Dispatch date" htmlFor="dispatch-date" required>
            <Input
              id="dispatch-date"
              type="date"
              value={dispatchDate}
              onChange={(event) => setDispatchDate(event.target.value)}
              disabled={saving}
              required
            />
          </Field>
          <Field
            label="Quantity"
            htmlFor="dispatch-quantity"
            hint={context ? `Maximum ${formatQuantity(maxQuantity)}` : undefined}
            required
          >
            <Input
              id="dispatch-quantity"
              type="number"
              min="0.01"
              max={maxQuantity || undefined}
              step="0.01"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              placeholder="e.g. 25"
              disabled={saving}
              required
            />
          </Field>
        </div>

        <Field label="Remarks" htmlFor="dispatch-remarks">
          <Textarea
            id="dispatch-remarks"
            value={remarks}
            onChange={(event) => setRemarks(event.target.value)}
            placeholder="Vehicle, gate pass or other notes (optional)"
            maxLength={2000}
            disabled={saving}
          />
        </Field>

        <p className="rounded-lg bg-indigo-50/70 px-3.5 py-2.5 text-xs leading-relaxed text-indigo-800 ring-1 ring-indigo-100 ring-inset">
          The dispatch is limited by the PO line balance and available stock. It posts a negative
          <span className="font-semibold"> DISPATCH</span> entry to the stock ledger and fulfils
          open plans in planned-date order.
        </p>
      </form>
    </Modal>
  );
}
