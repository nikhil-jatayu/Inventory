"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { useApiQuery } from "@/lib/hooks";
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
  const projects = useApiQuery<string[]>(open ? "/items/projects" : null);
  const [name, setName] = useState(item?.name ?? "");
  const [project, setProject] = useState(item?.project ?? "");
  const [family, setFamily] = useState(item?.family ?? "");
  const [modelNo, setModelNo] = useState(item?.model_no ?? "");
  const [openingInventory, setOpeningInventory] = useState("0");
  const [reorderLevel, setReorderLevel] = useState(item ? String(item.reorder_level) : "0");
  const [criticalLevel, setCriticalLevel] = useState(item ? String(item.critical_level) : "0");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const reorder = Number(reorderLevel);
    const critical = Number(criticalLevel);
    const opening = Number(openingInventory);
    if (!name.trim() || !project.trim() || !family.trim()) {
      setError("Item, project and family are required.");
      return;
    }
    if (!Number.isFinite(reorder) || !Number.isFinite(critical) || !Number.isFinite(opening) || reorder < 0 || critical < 0 || opening < 0) {
      setError("Inventory and stock levels must be zero or greater.");
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
        project: project.trim(),
        family: family.trim(),
        model_no: modelNo.trim() || null,
        reorder_level: reorder,
        critical_level: critical,
        ...(!item ? { opening_inventory: opening } : {}),
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
      size="lg"
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
        <Field label="Item" htmlFor="item-name" required>
          <Input
            id="item-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. 12U New"
            autoFocus
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Project" htmlFor="item-project" required>
          <Input
            id="item-project"
            value={project}
            onChange={(event) => setProject(event.target.value)}
            placeholder="Select or enter project"
            list="item-projects"
            required
          />
          <datalist id="item-projects">{(projects.data??[]).map(p=><option key={p} value={p}/>)}</datalist>
        </Field>
        <Field label="Family" htmlFor="item-family" required>
          <Input
            id="item-family"
            value={family}
            onChange={(event) => setFamily(event.target.value)}
            placeholder="e.g. FCT"
            list="item-families"
          />
          <datalist id="item-families">
            {families.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
        </Field>
        </div><Field label="Model No." htmlFor="item-model-no">
          <Input
            id="item-model-no"
            value={modelNo}
            onChange={(event) => setModelNo(event.target.value)}
            placeholder="Optional model number"
          />
        </Field>
        {!item && (
          <Field label="Inventory / opening stock" htmlFor="item-opening-inventory" hint="Posted to the stock ledger as opening inventory.">
            <Input
              id="item-opening-inventory"
              type="number"
              min="0"
              step="0.01"
              value={openingInventory}
              onChange={(event) => setOpeningInventory(event.target.value)}
            />
          </Field>
        )}
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
