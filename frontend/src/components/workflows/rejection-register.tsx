"use client";
import { useState } from "react";
import { Plus } from "lucide-react";
import { LinkedEntryModal } from "@/components/workflows/linked-entry-modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { PageHeader, TableShell } from "@/components/ui/page";
import { Pagination } from "@/components/ui/pagination";
import { useAuth } from "@/lib/auth";
import { qs } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import { canWrite, type Unit } from "@/lib/types";
import { currentMonth, monthRange, formatDate, formatQuantity, isoDate } from "@/lib/utils";

type Row={id:number;batch_id:string|null;rgp_number:string|null;rejection_date:string;unit_id:number|null;unit_name:string|null;item_name:string;project:string;quantity:number;dispatch_id?:number|null;invoice_number?:string|null;plan_id?:number|null};
export function RejectionRegister({kind}:{kind:"unit"|"purchase"}) {
  const isUnit=kind==="unit";
  const {user}=useAuth();const [month,setMonth]=useState(currentMonth());const [unit,setUnit]=useState("");const [search,setSearch]=useState("");const [page,setPage]=useState(1);const [refresh,setRefresh]=useState(0);const [open,setOpen]=useState(false);const [notice,setNotice]=useState("");const [selected,setSelected]=useState<Row[]|null>(null);
  const range=monthRange(month);
  const [year,monthNumber]=month.split("-").map(Number);
  const trendMonths=Array.from({length:6},(_,i)=>isoDate(new Date(year,monthNumber-6+i,1)).slice(0,7));
  const query=useApiQuery<Row[]>(isUnit?`/rejections/register${qs({date_from:trendMonths[0]+"-01",date_to:range.to,unit_id:unit})}`:`/purchase-rejections${qs({date_from:range.from,date_to:range.to})}`,refresh);
  const units=useApiQuery<Unit[]>(isUnit?"/units?include_inactive=true":null);
  const periodRows=(query.data??[]).filter(r=>r.rejection_date>=range.from&&r.rejection_date<=range.to);
  const trend=trendMonths.map(m=>({month:m,quantity:(query.data??[]).filter(r=>r.rejection_date.startsWith(m)).reduce((n,r)=>n+r.quantity,0)}));
  const grouped=new Map<string,Row[]>();for(const r of periodRows){const key=r.batch_id??`legacy-${r.id}`;grouped.set(key,[...(grouped.get(key)??[]),r]);}
  const allGroups=Array.from(grouped.values());
  const groups=allGroups.filter(g=>g.some(r=>`${r.rgp_number??""} ${r.item_name} ${r.project} ${r.invoice_number??""} ${r.plan_id??""}`.toLowerCase().includes(search.toLowerCase())));
  const total=(rows:Row[])=>rows.reduce((n,r)=>n+r.quantity,0);
  const linked=(r:Row)=>Boolean(isUnit?r.dispatch_id:r.plan_id);
  const unlinked=periodRows.filter(r=>!linked(r));const unitTotals=new Map<string,number>();for(const r of periodRows){const name=r.unit_name??"Unassigned";unitTotals.set(name,(unitTotals.get(name)??0)+r.quantity);}
  const pages=Math.max(1,Math.ceil(groups.length/20)),currentPage=Math.min(page,pages);
  return <div className="space-y-5">
    <PageHeader title={isUnit?"Unit Rejections":"Purchase Rejections"} description={isUnit?"Post-dispatch rejections from receiving units. Linked rejections reduce net sales, not available stock.":"Cancel outstanding purchase plan quantities before receipt. Cancellations do not increase or reduce stock."} actions={canWrite(user?.role,isUnit?"rejections":"purchase_rejections")&&<Button onClick={()=>setOpen(true)}><Plus className="h-4 w-4"/> {isUnit?"Add Rejection":"Add Purchase Rejection"}</Button>}/>
    {notice&&<Alert tone="success" onDismiss={()=>setNotice("")}>{notice}</Alert>}{(query.error||units.error)&&<Alert tone="error">{query.error||units.error}</Alert>}
    <div className="grid gap-3 sm:grid-cols-3"><Field label="Month"><Input type="month" value={month} onChange={e=>{setMonth(e.target.value||currentMonth());setPage(1);}}/></Field>{isUnit&&<Field label="Unit / Location"><Select value={unit} onChange={e=>{setUnit(e.target.value);setPage(1);}}><option value="">All units</option>{(units.data??[]).map(u=><option key={u.id} value={u.id}>{u.name}{!u.is_active?" (inactive)":""}</option>)}</Select></Field>}<Field label="Search register"><Input value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}} placeholder="RGP, item, project or reference"/></Field></div>
    <div className="grid gap-3 sm:grid-cols-3">{[["Rejected quantity",total(periodRows)],[isUnit?"Linked sales adjustments":"Linked plan cancellations",total(periodRows.filter(linked))],["Historical unlinked quantity",total(unlinked)]].map(([label,value])=><div key={label} className="rounded-xl border bg-white p-4"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-2xl font-semibold">{query.loading?"—":formatQuantity(Number(value))}</p></div>)}</div>
    {unlinked.length>0&&<Alert>Historical entries have no reliable transaction link. They remain in the register, but do not adjust sales or purchase plans.</Alert>}
    {isUnit&&<section className="rounded-xl border bg-white p-4"><h2 className="font-semibold">Rejections by unit · selected month</h2><div className="mt-3 space-y-2">{Array.from(unitTotals).sort((a,b)=>b[1]-a[1]).map(([name,qty])=><div key={name} className="flex items-center gap-3 text-sm"><span className="w-24 shrink-0">{name}</span><div className="h-3 flex-1 rounded bg-slate-100"><div className="h-3 rounded bg-indigo-500" style={{width:`${total(periodRows)?qty/total(periodRows)*100:0}%`}}/></div><strong>{formatQuantity(qty)}</strong></div>)}{!unitTotals.size&&<p className="text-sm text-slate-500">No unit rejections for this period.</p>}</div></section>}
    {isUnit&&<section className="rounded-xl border bg-white p-4"><h2 className="font-semibold">Monthly rejection trend</h2><p className="text-xs text-slate-500">Six months ending in the selected month; recorded rejection dates.</p><div className="mt-4 flex h-36 items-end gap-2">{trend.map(t=><div key={t.month} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1 text-xs"><span>{formatQuantity(t.quantity)}</span><div className="w-full max-w-12 rounded-t bg-indigo-500" style={{height:`${Math.max(2,100*t.quantity/Math.max(1,...trend.map(x=>x.quantity)))}px`}}/><span className="truncate text-slate-500">{t.month}</span></div>)}</div></section>}
    <TableShell footer={<Pagination page={currentPage} pages={pages} total={groups.length} pageSize={20} onPageChange={setPage}/>}><table className="min-w-full text-sm"><thead className="bg-slate-50"><tr>{["RGP No.","Date",...(isUnit?["Unit"]:[]),"Items","Quantity","Link status","Action"].map(h=><th key={h} className="p-3 text-left text-xs font-semibold uppercase text-slate-500">{h}</th>)}</tr></thead><tbody>{groups.slice((currentPage-1)*20,currentPage*20).map(g=><tr key={g[0].batch_id??`legacy-${g[0].id}`} className="border-t"><td className="p-3 font-medium">{g[0].rgp_number??"—"}</td><td className="p-3 whitespace-nowrap">{formatDate(g[0].rejection_date)}</td>{isUnit&&<td className="p-3">{g[0].unit_name??"—"}</td>}<td className="p-3">{g.map(r=>`${r.item_name} · ${r.project}`).join(", ")}</td><td className="p-3">{formatQuantity(total(g))}</td><td className="p-3"><span className={g.every(linked)?"text-emerald-700":"text-amber-700"}>{g.every(linked)?"Linked":"Legacy unlinked"}</span></td><td className="p-3"><Button size="sm" variant="ghost" onClick={()=>setSelected(g)}>View</Button></td></tr>)}{groups.length===0&&<tr><td colSpan={isUnit?7:6} className="p-8 text-center text-slate-500">{query.loading?"Loading…":"No matching records"}</td></tr>}</tbody></table></TableShell>
    {selected&&<Modal open title={selected[0].rgp_number??"Historical rejection"} description={`${formatDate(selected[0].rejection_date)}${isUnit?` · ${selected[0].unit_name??"Unassigned"}`:""}`} onClose={()=>setSelected(null)} size="lg"><table className="w-full text-sm"><thead><tr>{["Item / Project",isUnit?"Invoice / Dispatch":"Purchase plan","Rejected quantity"].map(h=><th key={h} className="p-2 text-left">{h}</th>)}</tr></thead><tbody>{selected.map(r=><tr key={r.id} className="border-t"><td className="p-2">{r.item_name} · {r.project}</td><td className="p-2">{linked(r)?(isUnit?`${r.invoice_number??""} / #${r.dispatch_id}`:`#${r.plan_id}`):"Legacy unlinked"}</td><td className="p-2">{formatQuantity(r.quantity)}</td></tr>)}</tbody></table><p className="mt-3 font-semibold">Total: {formatQuantity(total(selected))}</p></Modal>}
    {open&&<LinkedEntryModal mode={isUnit?"unit-rejection":"purchase-rejection"} onClose={()=>setOpen(false)} onSaved={m=>{setOpen(false);setNotice(m);setRefresh(n=>n+1);setMonth(currentMonth());}}/>}
  </div>;
}
