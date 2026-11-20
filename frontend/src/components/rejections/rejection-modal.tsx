"use client";

import { useState } from "react";
import { BadgeAlert } from "lucide-react";

import { ItemPicker, type ItemOption } from "@/components/item-picker";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import type { RejectionIssue } from "@/lib/types";
import { todayISO } from "@/lib/utils";

interface RejectionModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function RejectionModal({ open, onClose, onSaved }: RejectionModalProps) {
  const [item, setItem] = useState<ItemOption | null>(null);
  const [rejectionDate, setRejectionDate] = useState(todayISO());
  const [quantity, setQuantity] = useState("");
  const [issueId, setIssueId] = useState("");
  const [newIssue, setNewIssue] = useState("");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const issuesQuery = useApiQuery<{ issues: RejectionIssue[] }>(
    open ? "/rejection-issues" : null,
  );
  const issues = (issuesQuery.data?.issues ?? []).filter((issue) => issue.is_active);
  const addingIssue = issueId === "__new__";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!item) {
      setError("Select the item that was rejected.");
      return;
    }
    const value = Number(quantity);
    if (!quantity.trim() || !Number.isFinite(value) || value <= 0) {
      setError("Enter a rejection quantity greater than zero.");
      return;
    }
    if (!addingIssue && !issueId) {
      setError("Select a rejection issue.");
      return;
    }
    if (addingIssue && !newIssue.trim()) {
      setError("Enter the name of the new rejection issue.");
      return;
    }

    setSaving(true);
    try {
      await api("/rejections", {
        method: "POST",
        body: {
          item_id: item.id,
          rejection_date: rejectionDate,
          quantity: value,
          issue_id: addingIssue ? null : Number(issueId),
          issue_name: addingIssue ? newIssue.trim() : null,
          remarks: remarks.trim() || null,
        },
      });
      onSaved(
        `Rejection of ${value} ${item.name} recorded. Stock is unchanged.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to record the rejection.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Record rejection"
      description="Record a customer rejection against an item and its issue."
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="rejection-form" loading={saving}>
            <BadgeAlert className="h-4 w-4" />
            Record rejection
          </Button>
        </div>
      }
    >
      <form id="rejection-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {issuesQuery.error && <Alert tone="error">{issuesQuery.error}</Alert>}

        <Field label="Item" required>
          <ItemPicker value={item} onChange={setItem} disabled={saving} />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Rejection date" htmlFor="rejection-date" required>
            <Input
              id="rejection-date"
              type="date"
              value={rejectionDate}
              onChange={(event) => setRejectionDate(event.target.value)}
              disabled={saving}
              required
            />
          </Field>
          <Field label="Quantity" htmlFor="rejection-quantity" required>
            <Input
              id="rejection-quantity"
              type="number"
              min="0.01"
              step="0.01"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              placeholder="e.g. 5"
              disabled={saving}
              required
            />
          </Field>
        </div>

        <Field label="Issue" htmlFor="rejection-issue" required>
          <Select
            id="rejection-issue"
            value={issueId}
            onChange={(event) => {
              setIssueId(event.target.value);
              if (event.target.value !== "__new__") setNewIssue("");
            }}
            disabled={saving || issuesQuery.loading}
          >
            <option value="">Select an issue</option>
            {issues.map((issue) => (
              <option key={issue.id} value={issue.id}>
                {issue.name}
              </option>
            ))}
            <option value="__new__">＋ Add a new issue…</option>
          </Select>
        </Field>

        {addingIssue && (
          <Field
            label="New issue"
            htmlFor="rejection-new-issue"
            hint="Added to the maintained issue list for future rejections."
            required
          >
            <Input
              id="rejection-new-issue"
              value={newIssue}
              onChange={(event) => setNewIssue(event.target.value)}
              placeholder="e.g. Paint peel"
              maxLength={160}
              disabled={saving}
              autoFocus
              required
            />
          </Field>
        )}

        <Field label="Remarks" htmlFor="rejection-remarks">
          <Textarea
            id="rejection-remarks"
            value={remarks}
            onChange={(event) => setRemarks(event.target.value)}
            placeholder="Inspection note or customer reference (optional)"
            maxLength={2000}
            disabled={saving}
          />
        </Field>

        <p className="rounded-lg bg-indigo-50/70 px-3.5 py-2.5 text-xs leading-relaxed text-indigo-800 ring-1 ring-indigo-100 ring-inset">
          Rejections are customer rejections of already dispatched material. Recording one does not
          change the stock ledger automatically.
        </p>
      </form>
    </Modal>
  );
}
