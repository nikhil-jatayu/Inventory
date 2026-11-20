"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import type { Item } from "@/lib/types";

interface ItemModalProps {
  open: boolean;
  item: Item | null;
  families: string[];
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function ItemModal({ open, item, families, onClose, onSaved }: ItemModalProps) {
  const [name, setName] = useState(item?.name ?? "");
  const [family, setFamily] = useState(item?.family ?? "");
  const [reorderLevel, setReorderLevel] = useState(item ? String(item.reorder_level) : "0");
  const [criticalLevel, setCriticalLevel] = useState(item ? String(item.critical_level) : "0");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const reorder = Number(reorderLevel);
    const critical = Number(criticalLevel);
    if (!name.trim() || !family.trim()) {
      setError("Name and family are required.");
      return;
    }
    if (!Number.isFinite(reorder) || !Number.isFinite(critical) || reorder < 0 || critical < 0) {
      setError("Stock levels must be zero or greater.");
      return;
    }
    if (critical > reorder) {
      setError("Critical level cannot be higher than the reorder level.");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        family: family.trim(),
        reorder_level: reorder,
        critical_level: critical,
      };
      if (item) {
        await api(`/items/${item.id}`, { method: "PATCH", body: payload });
        onSaved(`${payload.name} updated.`);
      } else {
        await api("/items", { method: "POST", body: payload });
        onSaved(`${payload.name} added to the item master.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the item.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={item ? "Edit item" : "New item"}
      description={item ? "Update item details and stock levels." : "Add a new item to the master list."}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="item-form" loading={saving}>
            {item ? "Save changes" : "Create item"}
          </Button>
        </div>
      }
    >
      <form id="item-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        <Field label="Item name" htmlFor="item-name" required>
          <Input
            id="item-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Bearing 6205"
            autoFocus
          />
        </Field>
        <Field label="Family / group" htmlFor="item-family" required>
          <Input
            id="item-family"
            value={family}
            onChange={(event) => setFamily(event.target.value)}
            placeholder="e.g. Bearings"
            list="item-families"
          />
          <datalist id="item-families">
            {families.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Reorder level"
            htmlFor="item-reorder"
            hint="Stock below this shows as below reorder."
          >
            <Input
              id="item-reorder"
              type="number"
              min="0"
              step="0.01"
              value={reorderLevel}
              onChange={(event) => setReorderLevel(event.target.value)}
            />
          </Field>
          <Field
            label="Critical level"
            htmlFor="item-critical"
            hint="Stock below this shows as critical."
          >
            <Input
              id="item-critical"
              type="number"
              min="0"
              step="0.01"
              value={criticalLevel}
              onChange={(event) => setCriticalLevel(event.target.value)}
            />
          </Field>
        </div>
      </form>
    </Modal>
  );
}
