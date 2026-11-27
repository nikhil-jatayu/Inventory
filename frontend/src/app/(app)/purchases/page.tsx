"use client";

import { useState } from "react";
import { Plus } from "lucide-react";

import { LinkedEntryModal } from "@/components/workflows/linked-entry-modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { PageHeader, TableShell } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { useApiQuery } from "@/lib/hooks";
import { canWrite } from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";

interface PurchaseLine { plan_id: number | null; id: number; item_id: number; item_name: string; project: string; family: string; quantity: number; }
interface Purchase { id: number; purchase_date: string; recorded_by: number; lines: PurchaseLine[]; }
export default function PurchasesPage() {
  const { user } = useAuth();
  const writable = canWrite(user?.role, "purchases");
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [search,setSearch]=useState("");const [from,setFrom]=useState("");const [to,setTo]=useState("");const [selected,setSelected]=useState<Purchase|null>(null);const [page,setPage]=useState(1);
  const query = useApiQuery<Purchase[]>("/purchases?limit=500", refresh);
  const rows=(query.data??[]).filter(p=>(!from||p.purchase_date>=from)&&(!to||p.purchase_date<=to)&&`PURCHASE-${p.id} ${p.lines.map(l=>`${l.item_name} ${l.project}`).join(" ")}`.toLowerCase().includes(search.toLowerCase()));
  const currentPage=Math.min(page,Math.max(1,Math.ceil(rows.length/25)));

  return <div className="space-y-5">
    <PageHeader title="Purchases" description="Receive against outstanding purchase plans. Each saved purchase adds stock exactly once." actions={writable && <Button onClick={() => { setOpen(true); }}><Plus className="h-4 w-4" /> Add purchase</Button>} />
    {notice && <Alert tone="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}
    {query.error && <Alert tone="error">{query.error}</Alert>}
    <div className="grid gap-3 sm:grid-cols-3"><Field label="Search"><Input value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}} placeholder="Reference, item or project"/></Field><Field label="From"><Input type="date" value={from} onChange={e=>{setFrom(e.target.value);setPage(1);}}/></Field><Field label="To"><Input type="date" value={to} onChange={e=>{setTo(e.target.value);setPage(1);}}/></Field></div>
    {query.data?.length===500&&<p className="text-xs text-amber-700">Showing the latest 500 purchase records. Filters apply to loaded records.</p>}
    <TableShell>
      <table className="min-w-full divide-y divide-slate-100 text-sm"><thead className="bg-slate-50/70"><tr>{["Date", "Items", "Total quantity", "Reference", "Action"].map((x) => <th key={x} className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">{x}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">
        {rows.slice((currentPage-1)*25,currentPage*25).map((purchase) => <tr key={purchase.id}><td className="px-4 py-3 whitespace-nowrap">{formatDate(purchase.purchase_date)}</td><td className="px-4 py-3">{purchase.lines.map((line) => `${line.item_name} · ${line.project} (${formatQuantity(line.quantity)})`).join(", ")}</td><td className="px-4 py-3 tabular-nums">{formatQuantity(purchase.lines.reduce((sum, line) => sum + line.quantity, 0))}</td><td className="px-4 py-3 text-slate-500">PURCHASE-{purchase.id}</td><td className="p-3"><Button variant="ghost" size="sm" onClick={()=>setSelected(purchase)}>View</Button></td></tr>)}
        {!query.loading && rows.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-500">No purchase entries recorded.</td></tr>}
      </tbody></table>
    </TableShell>
    <div className="flex items-center justify-between text-sm"><span>{rows.length} matching records · Page {currentPage}</span><div className="flex gap-2"><Button variant="secondary" size="sm" disabled={currentPage<=1} onClick={()=>setPage(currentPage-1)}>Previous</Button><Button variant="secondary" size="sm" disabled={currentPage*25>=rows.length} onClick={()=>setPage(currentPage+1)}>Next</Button></div></div>
    {selected&&<Modal open onClose={()=>setSelected(null)} title={`PURCHASE-${selected.id}`} description={formatDate(selected.purchase_date)}><table className="w-full text-sm"><thead><tr>{["Sr. No.","Item / Project","Purchase plan","Quantity"].map(x=><th className="p-2 text-left" key={x}>{x}</th>)}</tr></thead><tbody>{selected.lines.map((l,i)=><tr className="border-t" key={l.id}><td className="p-2">{i+1}</td><td className="p-2">{l.item_name} · {l.project}</td><td className="p-2">{l.plan_id?`#${l.plan_id}`:"Legacy unlinked"}</td><td className="p-2">{formatQuantity(l.quantity)}</td></tr>)}</tbody></table><p className="mt-3 font-semibold">Total: {formatQuantity(selected.lines.reduce((s,l)=>s+l.quantity,0))}</p></Modal>}
    {open&&<LinkedEntryModal mode="receipt" onClose={()=>setOpen(false)} onSaved={m=>{setOpen(false);setNotice(m);setRefresh(v=>v+1);}}/>}
  </div>;
}
