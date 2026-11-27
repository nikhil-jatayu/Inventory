"use client";

import { useState } from "react";
import { CalendarClock, Trash2 } from "lucide-react";

import { ItemPicker, type ItemOption } from "@/components/item-picker";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import { PRIORITY_LABELS, type DispatchPlan, type Priority, type Unit } from "@/lib/types";
import { categoryForRange } from "@/lib/planning";
import { formatQuantity, todayISO } from "@/lib/utils";

interface PlanModalProps {
  open: boolean;
  plan?: DispatchPlan | null;
  defaultDate?: string;
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function PlanModal({ open, plan, defaultDate, onClose, onSaved }: PlanModalProps) {
  const [item, setItem] = useState<ItemOption | null>(plan ? {
    id: plan.item_id, name: plan.item_name, family: plan.item_family, project: plan.project,
  } : null);
  const [unitId, setUnitId] = useState(plan?.unit_id ? String(plan.unit_id) : "");
  const [plannedDate, setPlannedDate] = useState(plan?.planned_date ?? defaultDate ?? todayISO());
  const [plannedEndDate, setPlannedEndDate] = useState(plan?.planned_end_date ?? plan?.planned_date ?? defaultDate ?? todayISO());
  const [quantity, setQuantity] = useState(plan ? String(plan.quantity) : "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const unitsQuery = useApiQuery<Unit[]>(open ? "/units" : null);
  const units = unitsQuery.data ?? [];
  const settingsQuery = useApiQuery<{ today: string; lead_times: Record<Priority, number> }>(open ? "/planning/settings" : null);
  const settings = settingsQuery.data;

  const result = categoryForRange(plannedDate, plannedEndDate, settings?.lead_times);
  const category = result?.category;
  const warning = result?.warning;
  const minQuantity = plan?.fulfilled_quantity ?? 0;
  const legacyPoPlan = Boolean(plan?.po_line_id);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!item) {
      setError("Select an item from the Item Master.");
      return;
    }
    if (!unitId) {
      setError("Select a dispatch unit.");
      return;
    }
    if (!plannedDate || !plannedEndDate || plannedEndDate < plannedDate) {
      setError("The date range end must be on or after the start date.");
      return;
    }
    const value = Number(quantity);
    if (!quantity.trim() || !Number.isFinite(value) || value <= 0) {
      setError("Enter a planned quantity greater than zero.");
      return;
    }
    if (value < minQuantity) {
      setError(`Planned quantity cannot be less than the already dispatched quantity (${formatQuantity(minQuantity)}).`);
      return;
    }

    setSaving(true);
    try {
      const body = {
        ...(!legacyPoPlan ? { item_id: item.id } : {}),
        unit_id: Number(unitId),
        planned_date: plannedDate,
        planned_end_date: plannedEndDate,
        quantity: value,
      };
      if (plan) {
        await api(`/dispatch-plans/${plan.id}`, { method: "PATCH", body });
        onSaved(`Dispatch plan for ${item.name} updated.`);
      } else {
        await api("/dispatch-plans", { method: "POST", body: { ...body, item_id: item.id } });
        onSaved(`Dispatch plan created for ${item.name}.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the dispatch plan.");
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!plan || !window.confirm("Delete this dispatch plan? This cannot be undone.")) return;
    setError(null);
    setDeleting(true);
    try {
      await api(`/dispatch-plans/${plan.id}`, { method: "DELETE" });
      onSaved("Dispatch plan deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete the dispatch plan.");
      setDeleting(false);
    }
  }

  const busy = saving || deleting;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={plan ? "Edit dispatch plan" : "Create dispatch plan"}
      description="Plan required item quantities independently of purchase orders. The date range is shown on the Gantt schedule."
      size="lg"
      footer={
        <div className="flex w-full items-center justify-between gap-2">
          <div>
            {plan && plan.status === "PLANNED" && (
              <Button type="button" variant="danger" onClick={handleDelete} loading={deleting}>
                <Trash2 className="h-4 w-4" /> Delete plan
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button type="submit" form="plan-form" loading={saving}> {plan ? "Save changes" : "Create plan"} </Button>
          </div>
        </div>
      }
    >
      <form id="plan-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {unitsQuery.error && <Alert tone="error">{unitsQuery.error}</Alert>}
        <Field label="Item" required>
          <ItemPicker value={item} onChange={setItem} disabled={busy || legacyPoPlan} />
        </Field>
        <Field label="Dispatch location / unit" htmlFor="plan-unit" required>
          <Select id="plan-unit" value={unitId} onChange={(event) => setUnitId(event.target.value)} disabled={busy || unitsQuery.loading} required>
            <option value="">Select unit</option>
            {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
          </Select>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Date range – start" htmlFor="plan-start-date" required>
            <Input id="plan-start-date" type="date" value={plannedDate} onChange={(event) => setPlannedDate(event.target.value)} disabled={busy} required />
          </Field>
          <Field label="Date range – end" htmlFor="plan-end-date" required>
            <Input id="plan-end-date" type="date" min={plannedDate} value={plannedEndDate} onChange={(event) => setPlannedEndDate(event.target.value)} disabled={busy} required />
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Quantity" htmlFor="plan-quantity" hint={minQuantity > 0 ? `Already dispatched: ${formatQuantity(minQuantity)}` : undefined} required>
            <Input id="plan-quantity" type="number" min={Math.max(minQuantity, 0.01)} step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="0" disabled={busy} required />
          </Field>
        </div>
        <p className="text-sm font-medium">Category (Auto): {category ? `${PRIORITY_LABELS[category]} · ${result?.duration} days` : "Set valid dates"}</p>
        {warning && (
          <div className="flex items-start gap-2 rounded-lg bg-amber-50 px-3.5 py-2.5 text-xs leading-relaxed text-amber-800 ring-1 ring-amber-200 ring-inset">
            <CalendarClock className="mt-0.5 h-4 w-4 shrink-0" />
            This plan has a short date range of {result?.duration} days. Review the schedule before saving.
          </div>
        )}
        {plan?.po_number && <p className="text-xs text-slate-500">Legacy bookkeeping reference: PO {plan.po_number}</p>}
      </form>
    </Modal>
  );
}
