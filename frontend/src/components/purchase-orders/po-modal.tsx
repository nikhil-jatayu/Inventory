"use client";

import { useState } from "react";
import { ItemLines } from "@/components/ui/item-lines";

import { type ItemOption } from "@/components/item-picker";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import type { PurchaseOrder, Unit } from "@/lib/types";
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
    item: { id: line.item_id, name: line.item_name, family: line.item_family, project: line.project },
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
  const [poDate] = useState(po?.po_date ?? todayISO());
  const [unitIds, setUnitIds] = useState<string[]>(po?.unit_ids?.map(String) ?? []);
  const [lines, setLines] = useState<LineDraft[]>(po ? draftsFromOrder(po) : [blankLine()]);
  const unitsQuery = useApiQuery<Unit[]>(open ? "/units" : null);
  const units = unitsQuery.data ?? [];
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!/^\d{8}$/.test(poNumber.trim())) {
      setError("PO number must contain exactly eight digits.");
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
      const selectedUnits = unitIds.filter(Boolean).map(Number);
      if (new Set(selectedUnits).size !== selectedUnits.length) {
        setError("Select a different location in each Unit field.");
        setSaving(false);
        return;
      }
      const body = {
        po_number: poNumber.trim(),
        customer_name: po?.customer_name ?? "",
        unit_number: po?.unit_number ?? "",
        po_date: poDate,
        unit_ids: selectedUnits,
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
          : "Record the eight-digit PO reference and item quantities for bookkeeping. Dispatch plans and sales are managed separately."
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
              onChange={(event) => setPoNumber(event.target.value.replace(/\D/g, "").slice(0, 8))}
              placeholder="e.g. 00012345"
              inputMode="numeric"
              maxLength={8}
              pattern="[0-9]{8}"
              autoFocus
              required
            />
          </Field>
          <Field label="PO date (automatic)" htmlFor="po-date">
            <Input id="po-date" type="date" value={poDate} readOnly disabled />
          </Field>
        </div>

        <Field label="Units / Locations (optional)"><div className="flex flex-wrap gap-3 rounded-lg border border-slate-200 p-3">{units.map(unit=><label key={unit.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={unitIds.includes(String(unit.id))} disabled={saving} onChange={e=>setUnitIds(old=>e.target.checked?[...old,String(unit.id)]:old.filter(id=>id!==String(unit.id)))}/>{unit.name}</label>)}</div></Field>
        {unitsQuery.error && <Alert tone="error">{unitsQuery.error}</Alert>}

        <ItemLines lines={lines} onChange={setLines} blank={blankLine} disabled={saving}/>
        {po && <p className="text-xs text-slate-500">Historical PO-linked quantities cannot be reduced or removed.</p>}
      </form>
    </Modal>
  );
}
