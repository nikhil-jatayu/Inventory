"use client";

import { useState } from "react";
import { AlertTriangle, CalendarClock, Trash2 } from "lucide-react";

import { POLinePicker } from "@/components/planning/po-line-picker";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import {
  PRIORITY_LABELS,
  type DispatchPlan,
  type POLineOption,
  type PlanningSettings,
  type Priority,
} from "@/lib/types";
import { daysBetween, formatQuantity, todayISO } from "@/lib/utils";

export interface PlanLineContext {
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
  available_to_plan: number;
}

export function planLineFromOption(option: POLineOption): PlanLineContext {
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
    available_to_plan: option.available_to_plan,
  };
}

function planLineFromPlan(plan: DispatchPlan): PlanLineContext {
  return {
    po_line_id: plan.po_line_id,
    po_number: plan.po_number,
    customer_name: plan.customer_name,
    unit_number: plan.unit_number,
    item_name: plan.item_name,
    item_family: plan.item_family,
    quantity: plan.po_quantity,
    planned_quantity: plan.po_planned,
    dispatched_quantity: plan.po_dispatched,
    balance_quantity: plan.po_balance,
    available_to_plan: plan.po_available_to_plan,
  };
}

interface PlanModalProps {
  open: boolean;
  plan?: DispatchPlan | null;
  line?: PlanLineContext | null;
  defaultDate?: string;
  onClose: () => void;
  onSaved: (message: string) => void;
}

const PRIORITIES: Priority[] = ["NORMAL", "URGENT", "EMERGENCY"];

export function PlanModal({ open, plan, line, defaultDate, onClose, onSaved }: PlanModalProps) {
  const [picked, setPicked] = useState<POLineOption | null>(null);
  const [plannedDate, setPlannedDate] = useState(plan?.planned_date ?? defaultDate ?? todayISO());
  const [quantity, setQuantity] = useState(plan ? String(plan.quantity) : "");
  const [priority, setPriority] = useState<Priority>(plan?.priority ?? "NORMAL");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const settingsQuery = useApiQuery<PlanningSettings>(open ? "/planning/settings" : null);
  const settings = settingsQuery.data;

  const fixedLine = plan ? planLineFromPlan(plan) : line ?? null;
  const context = fixedLine ?? (picked ? planLineFromOption(picked) : null);
  const minQuantity = plan?.fulfilled_quantity ?? 0;
  const maxQuantity = plan
    ? plan.po_available_to_plan + plan.outstanding_quantity
    : context?.available_to_plan ?? 0;
  const contextStats: Array<{ label: string; value: number }> = context
    ? [
        { label: "Ordered", value: context.quantity },
        { label: "Planned", value: context.planned_quantity },
        { label: "Dispatched", value: context.dispatched_quantity },
        ...(plan
          ? [
              { label: "Fulfilled", value: plan.fulfilled_quantity },
              { label: "Outstanding", value: plan.outstanding_quantity },
              { label: "Maximum for this plan", value: maxQuantity },
            ]
          : [{ label: "Available to plan", value: context.available_to_plan }]),
      ]
    : [];

  const leadTime = settings?.lead_times[priority];
  const daysUntil =
    settings && plannedDate ? daysBetween(settings.today, plannedDate) : null;
  const warning = leadTime !== undefined && daysUntil !== null && daysUntil < leadTime;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!context) {
      setError("Select a purchase order line.");
      return;
    }
    const value = Number(quantity);
    if (!quantity.trim() || !Number.isFinite(value) || value <= 0) {
      setError("Enter a planned quantity greater than zero.");
      return;
    }
    if (value < minQuantity) {
      setError(
        `Planned quantity cannot be less than the fulfilled quantity of ${formatQuantity(minQuantity)}.`,
      );
      return;
    }
    if (value > maxQuantity) {
      setError(
        `Planned quantity cannot exceed the available balance of ${formatQuantity(maxQuantity)}.`,
      );
      return;
    }

    setSaving(true);
    try {
      if (plan) {
        await api(`/dispatch-plans/${plan.id}`, {
          method: "PATCH",
          body: { planned_date: plannedDate, quantity: value, priority },
        });
        onSaved(`Dispatch plan for ${context.item_name} updated.`);
      } else {
        await api("/dispatch-plans", {
          method: "POST",
          body: {
            po_line_id: context.po_line_id,
            planned_date: plannedDate,
            quantity: value,
            priority,
          },
        });
        onSaved(`Dispatch plan created for ${context.item_name}.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the dispatch plan.");
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!plan) return;
    if (!window.confirm("Delete this dispatch plan? This cannot be undone.")) return;

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
      title={plan ? "Edit dispatch plan" : "New dispatch plan"}
      description={
        plan
          ? "Adjust the planned date, quantity or priority."
          : "Plan a quantity from a purchase order line."
      }
      size="lg"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            {plan && (
              <Button
                type="button"
                variant="ghost"
                className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                onClick={handleDelete}
                loading={deleting}
                disabled={saving}
              >
                <Trash2 className="h-4 w-4" />
                Delete plan
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" form="plan-form" loading={saving} disabled={deleting}>
              {plan ? "Save changes" : "Create plan"}
            </Button>
          </div>
        </div>
      }
    >
      <form id="plan-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}

        {!fixedLine && (
          <Field label="Purchase order line" required>
            <POLinePicker value={picked} onChange={setPicked} disabled={busy} />
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
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
              {contextStats.map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-lg bg-white px-2.5 py-2 ring-1 ring-slate-200 ring-inset"
                >
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="mt-0.5 text-sm font-semibold tabular-nums text-slate-900">
                    {formatQuantity(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Planned date" htmlFor="plan-date" required>
            <Input
              id="plan-date"
              type="date"
              value={plannedDate}
              onChange={(event) => setPlannedDate(event.target.value)}
              disabled={busy}
              required
            />
          </Field>
          <Field
            label="Quantity"
            htmlFor="plan-quantity"
            hint={
              context
                ? `Maximum ${formatQuantity(maxQuantity)}${
                    minQuantity > 0 ? ` · Minimum ${formatQuantity(minQuantity)}` : ""
                  }`
                : undefined
            }
            required
          >
            <Input
              id="plan-quantity"
              type="number"
              min={minQuantity > 0 ? minQuantity : 0.01}
              max={maxQuantity || undefined}
              step="0.01"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              placeholder="e.g. 25"
              disabled={busy}
              required
            />
          </Field>
          <Field label="Priority" htmlFor="plan-priority" required>
            <Select
              id="plan-priority"
              value={priority}
              onChange={(event) => setPriority(event.target.value as Priority)}
              disabled={busy}
            >
              {PRIORITIES.map((option) => (
                <option key={option} value={option}>
                  {PRIORITY_LABELS[option]}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        {settings && leadTime !== undefined && daysUntil !== null && (
          <div
            className={
              warning
                ? "flex items-start gap-2.5 rounded-lg bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800 ring-1 ring-amber-200 ring-inset"
                : "flex items-start gap-2.5 rounded-lg bg-slate-50 px-3.5 py-2.5 text-sm text-slate-600 ring-1 ring-slate-200 ring-inset"
            }
          >
            {warning ? (
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            ) : (
              <CalendarClock className="mt-0.5 h-4 w-4 shrink-0" />
            )}
            <span>
              {PRIORITY_LABELS[priority]} plans target <strong>{leadTime} days</strong>. This date
              is <strong>{daysUntil} days</strong> from today
              {warning ? " — inside the lead time." : "."}
            </span>
          </div>
        )}
      </form>
    </Modal>
  );
}
