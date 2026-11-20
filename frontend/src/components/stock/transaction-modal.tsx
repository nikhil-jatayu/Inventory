"use client";

import { useState } from "react";
import { ArrowDownCircle, ArrowUpCircle } from "lucide-react";

import { ItemPicker, type ItemOption } from "@/components/item-picker";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import type { StockTxnType } from "@/lib/types";
import { todayISO } from "@/lib/utils";

interface TransactionModalProps {
  open: boolean;
  fixedItem?: { id: number; name: string; family: string } | null;
  defaultType?: Extract<StockTxnType, "OPENING" | "RECEIPT" | "ADJUSTMENT">;
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function TransactionModal({
  open,
  fixedItem,
  defaultType = "RECEIPT",
  onClose,
  onSaved,
}: TransactionModalProps) {
  const [item, setItem] = useState<ItemOption | null>(
    fixedItem ? { id: fixedItem.id, name: fixedItem.name, family: fixedItem.family } : null,
  );
  const [type, setType] = useState<"OPENING" | "RECEIPT" | "ADJUSTMENT">(defaultType);
  const [quantity, setQuantity] = useState("");
  const [date, setDate] = useState(todayISO());
  const [ref, setRef] = useState("");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const isAdjustment = type === "ADJUSTMENT";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!item) {
      setError("Select an item.");
      return;
    }
    const value = Number(quantity);
    if (!quantity.trim() || !Number.isFinite(value) || value === 0) {
      setError("Enter a non-zero quantity.");
      return;
    }
    if (!isAdjustment && value < 0) {
      setError("Opening stock and receipts must be positive. Use an adjustment to reduce stock.");
      return;
    }

    setSaving(true);
    try {
      await api("/stock/transactions", {
        method: "POST",
        body: {
          item_id: item.id,
          type,
          quantity: value,
          date,
          ref: ref.trim() || null,
          remarks: remarks.trim() || null,
        },
      });
      const label =
        type === "RECEIPT" ? "Receipt" : type === "OPENING" ? "Opening stock" : "Adjustment";
      onSaved(`${label} recorded for ${item.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the stock entry.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New stock entry"
      description="Post opening stock, a receipt, or a signed adjustment to the ledger."
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="stock-form" loading={saving}>
            Save entry
          </Button>
        </div>
      }
    >
      <form id="stock-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}

        {fixedItem ? (
          <Field label="Item">
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-sm font-medium text-slate-800">{fixedItem.name}</p>
              <p className="text-xs text-slate-500">{fixedItem.family}</p>
            </div>
          </Field>
        ) : (
          <Field label="Item" required>
            <ItemPicker value={item} onChange={setItem} />
          </Field>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Entry type" htmlFor="stock-type" required>
            <Select
              id="stock-type"
              value={type}
              onChange={(event) =>
                setType(event.target.value as "OPENING" | "RECEIPT" | "ADJUSTMENT")
              }
            >
              <option value="RECEIPT">Receipt</option>
              <option value="OPENING">Opening stock</option>
              <option value="ADJUSTMENT">Adjustment</option>
            </Select>
          </Field>
          <Field
            label="Quantity"
            htmlFor="stock-quantity"
            hint={isAdjustment ? "Use a negative number to reduce stock." : "Must be positive."}
            required
          >
            <Input
              id="stock-quantity"
              type="number"
              step="0.01"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              placeholder={isAdjustment ? "-5" : "100"}
              autoFocus={!fixedItem}
            />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Date" htmlFor="stock-date" required>
            <Input
              id="stock-date"
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </Field>
          <Field label="Reference" htmlFor="stock-ref" hint="GRN, invoice or note number.">
            <Input
              id="stock-ref"
              value={ref}
              onChange={(event) => setRef(event.target.value)}
              placeholder="Optional"
            />
          </Field>
        </div>

        <Field label="Remarks" htmlFor="stock-remarks">
          <Textarea
            id="stock-remarks"
            value={remarks}
            onChange={(event) => setRemarks(event.target.value)}
            placeholder="Optional note"
            rows={2}
          />
        </Field>

        <div className="flex items-start gap-3 rounded-lg bg-slate-50 px-3 py-2.5 text-xs text-slate-500">
          {isAdjustment ? (
            <ArrowDownCircle className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
          ) : (
            <ArrowUpCircle className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
          )}
          <span>
            Stock entries are permanent ledger transactions. An adjustment cannot make available
            stock negative.
          </span>
        </div>
      </form>
    </Modal>
  );
}
