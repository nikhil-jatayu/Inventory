"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import { ItemPicker, type ItemOption } from "@/components/item-picker";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import type { PurchaseOrder } from "@/lib/types";
import { formatQuantity, todayISO } from "@/lib/utils";

interface LineDraft {
  key: string;
  item: ItemOption | null;
  quantity: string;
  committed: number;
}

function blankLine(): LineDraft {
  return {
    key: `new-${Math.random().toString(36).slice(2)}`,
    item: null,
    quantity: "",
    committed: 0,
  };
}

function draftsFromOrder(po: PurchaseOrder): LineDraft[] {
  if (po.lines.length === 0) return [blankLine()];
  return po.lines.map((line) => ({
    key: `line-${line.id}`,
    item: { id: line.item_id, name: line.item_name, family: line.item_family },
    quantity: String(line.quantity),
    committed: line.planned_quantity + line.dispatched_quantity,
  }));
}

interface PurchaseOrderModalProps {
  open: boolean;
  po?: PurchaseOrder | null;
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function PurchaseOrderModal({ open, po, onClose, onSaved }: PurchaseOrderModalProps) {
  const [poNumber, setPoNumber] = useState(po?.po_number ?? "");
  const [customerName, setCustomerName] = useState(po?.customer_name ?? "");
  const [unitNumber, setUnitNumber] = useState(po?.unit_number ?? "");
  const [poDate, setPoDate] = useState(po?.po_date ?? todayISO());
  const [lines, setLines] = useState<LineDraft[]>(po ? draftsFromOrder(po) : [blankLine()]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function updateLine(key: string, changes: Partial<LineDraft>) {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...changes } : line)),
    );
  }

  function removeLine(key: string) {
    setLines((current) =>
      current.length === 1 ? current : current.filter((line) => line.key !== key),
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!poNumber.trim() || !customerName.trim() || !unitNumber.trim()) {
      setError("PO number, customer name and unit number are required.");
      return;
    }

    const itemIds = lines.map((line) => line.item?.id).filter((id): id is number => !!id);
    if (itemIds.length !== lines.length) {
      setError("Select an item for every line.");
      return;
    }
    if (new Set(itemIds).size !== itemIds.length) {
      setError("Each item can appear only once on a purchase order.");
      return;
    }

    for (const line of lines) {
      const value = Number(line.quantity);
      if (!line.quantity.trim() || !Number.isFinite(value) || value <= 0) {
        setError(`Enter an ordered quantity greater than zero for ${line.item?.name ?? "each line"}.`);
        return;
      }
      if (value < line.committed) {
        setError(
          `${line.item?.name} cannot be reduced below its planned and dispatched quantity (${formatQuantity(line.committed)}).`,
        );
        return;
      }
    }

    setSaving(true);
    try {
      const body = {
        po_number: poNumber.trim(),
        customer_name: customerName.trim(),
        unit_number: unitNumber.trim(),
        po_date: poDate,
        lines: lines.map((line) => ({
          item_id: line.item!.id,
          quantity: Number(line.quantity),
        })),
      };

      if (po) {
        await api(`/purchase-orders/${po.id}`, { method: "PATCH", body });
        onSaved(`Purchase order ${body.po_number} updated.`);
      } else {
        await api("/purchase-orders", { method: "POST", body });
        onSaved(`Purchase order ${body.po_number} created.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the purchase order.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={po ? `Edit ${po.po_number}` : "New purchase order"}
      description={
        po
          ? "Update the header or line quantities. Quantities with planning or dispatch history cannot be reduced below the committed amount."
          : "Record a customer purchase order and its item lines."
      }
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="po-form" loading={saving}>
            {po ? "Save changes" : "Create purchase order"}
          </Button>
        </div>
      }
    >
      <form id="po-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="PO number" htmlFor="po-number" required>
            <Input
              id="po-number"
              value={poNumber}
              onChange={(event) => setPoNumber(event.target.value)}
              placeholder="e.g. PO-1042"
              autoFocus
              required
            />
          </Field>
          <Field label="PO date" htmlFor="po-date" required>
            <Input
              id="po-date"
              type="date"
              value={poDate}
              onChange={(event) => setPoDate(event.target.value)}
              required
            />
          </Field>
          <Field label="Customer" htmlFor="po-customer" required>
            <Input
              id="po-customer"
              value={customerName}
              onChange={(event) => setCustomerName(event.target.value)}
              placeholder="Customer name"
              required
            />
          </Field>
          <Field label="Unit number" htmlFor="po-unit" required>
            <Input
              id="po-unit"
              value={unitNumber}
              onChange={(event) => setUnitNumber(event.target.value)}
              placeholder="e.g. UNIT-77"
              required
            />
          </Field>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800">Lines</h3>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setLines((current) => [...current, blankLine()])}
              disabled={saving}
            >
              <Plus className="h-3.5 w-3.5" />
              Add line
            </Button>
          </div>

          <div className="space-y-2.5">
            {lines.map((line, index) => (
              <div
                key={line.key}
                className="rounded-xl border border-slate-200 bg-slate-50/60 p-3"
              >
                <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start">
                  <div className="min-w-0 flex-1">
                    <Field label={`Item ${index + 1}`} required>
                      <ItemPicker
                        value={line.item}
                        onChange={(item) => updateLine(line.key, { item })}
                        disabled={saving}
                      />
                    </Field>
                  </div>
                  <div className="sm:w-40">
                    <Field
                      label="Quantity"
                      htmlFor={`po-qty-${line.key}`}
                      hint={
                        line.committed > 0
                          ? `Committed ${formatQuantity(line.committed)}`
                          : undefined
                      }
                      required
                    >
                      <Input
                        id={`po-qty-${line.key}`}
                        type="number"
                        min={line.committed > 0 ? line.committed : 0.01}
                        step="0.01"
                        value={line.quantity}
                        onChange={(event) =>
                          updateLine(line.key, { quantity: event.target.value })
                        }
                        placeholder="0"
                        disabled={saving}
                        required
                      />
                    </Field>
                  </div>
                  <div className="sm:pt-6">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeLine(line.key)}
                      disabled={saving || lines.length === 1}
                      aria-label={`Remove line ${index + 1}`}
                      title={
                        lines.length === 1
                          ? "A purchase order needs at least one line"
                          : "Remove line"
                      }
                    >
                      <Trash2 className="h-4 w-4 text-rose-500" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-slate-500">
          Lines with planning or dispatch history cannot be removed, and their ordered quantity
          cannot drop below planned + dispatched.
        </p>
      </form>
    </Modal>
  );
}
