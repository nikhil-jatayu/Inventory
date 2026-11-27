"use client";

import { useState } from "react";
import { MapPin, Plus, Power, PowerOff } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { PageHeader, TableShell } from "@/components/ui/page";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiQuery } from "@/lib/hooks";
import { canWrite, type Unit } from "@/lib/types";

export default function UnitsPage() {
  const { user } = useAuth();
  const writable = canWrite(user?.role, "units");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const query = useApiQuery<Unit[]>("/units?include_inactive=true", refresh);
  const units = query.data ?? [];

  async function createUnit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!name.trim()) return setError("Enter a unit/location name.");
    setSaving(true);
    try {
      const created = await api<Unit>("/units", { method: "POST", body: { name: name.trim() } });
      setName("");
      setNotice(`${created.name} added to the unit list.`);
      setRefresh((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add the unit.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleUnit(unit: Unit) {
    setError(null);
    try {
      await api(`/units/${unit.id}`, { method: "PATCH", body: { is_active: !unit.is_active } });
      setNotice(`${unit.name} ${unit.is_active ? "deactivated" : "activated"}. Existing transaction history is retained.`);
      setRefresh((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update the unit.");
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Units / Locations" description="Manage dispatch destinations used by dispatch plans, actual dispatches and rejection forms." />
      {notice && <Alert tone="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      {query.error && <Alert tone="error">{query.error}</Alert>}
      {writable && (
        <form onSubmit={createUnit} className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-end">
          <div className="flex-1"><Field label="New unit / location" htmlFor="unit-name" hint="Initial locations Unit-1 through Unit-4 are already seeded."><Input id="unit-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Unit-5" maxLength={80} /></Field></div>
          <Button type="submit" loading={saving}><Plus className="h-4 w-4" /> Add unit</Button>
        </form>
      )}
      <TableShell>
        <table className="min-w-full divide-y divide-slate-100 text-sm">
          <thead className="bg-slate-50/70"><tr><th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">Location</th><th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">Status</th><th className="px-4 py-3 text-right text-xs font-semibold uppercase text-slate-500">Action</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {units.length === 0 && <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-500">No units found.</td></tr>}
            {units.map((unit) => <tr key={unit.id}><td className="px-4 py-3"><div className="flex items-center gap-2 font-medium text-slate-800"><MapPin className="h-4 w-4 text-slate-400" />{unit.name}</div></td><td className="px-4 py-3"><Badge tone={unit.is_active ? "emerald" : "slate"}>{unit.is_active ? "Active" : "Inactive"}</Badge></td><td className="px-4 py-3 text-right">{writable && <Button variant="ghost" size="sm" onClick={() => toggleUnit(unit)}>{unit.is_active ? <><PowerOff className="h-3.5 w-3.5" /> Deactivate</> : <><Power className="h-3.5 w-3.5" /> Activate</>}</Button>}</td></tr>)}
          </tbody>
        </table>
      </TableShell>
      <p className="text-xs text-slate-500">Deactivating a unit removes it from new-entry dropdowns without deleting records that already reference it.</p>
    </div>
  );
}
