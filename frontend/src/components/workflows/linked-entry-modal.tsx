"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api, qs } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks";
import type { Unit } from "@/lib/types";
import { formatDate, formatQuantity, todayISO } from "@/lib/utils";

type Mode = "receipt" | "purchase-rejection" | "unit-rejection";
type Option = {id:number;item_id:number;item_name:string;project:string;outstanding_quantity:number;planned_date?:string;planned_end_date?:string;dispatch_date?:string;invoice_number?:string};
type Draft = {key:number;reference:string;quantity:string};
const TITLES = {receipt:"Add Purchase", "purchase-rejection":"Add Purchase Rejection", "unit-rejection":"Add Unit Rejection"};
const DESCRIPTIONS = {receipt:"Receive quantities against existing purchase plans. Accepted pieces increase inventory.", "purchase-rejection":"Cancel all or part of outstanding purchase plans. This does not change stock.", "unit-rejection":"Record rejected pieces against actual deliveries. Net sales decrease; stock does not change."};

export function LinkedEntryModal({mode,onClose,onSaved,initialPlanId}:{mode:Mode;onClose:()=>void;onSaved:(message:string)=>void;initialPlanId?:number}) {
  const isUnit = mode === "unit-rejection", isReceipt = mode === "receipt";
  const [unit,setUnit] = useState("");
  const [rgp,setRgp] = useState("");
  const [rows,setRows] = useState<Draft[]>([{key:1,reference:initialPlanId?String(initialPlanId):"",quantity:""}]);
  const [nextKey,setNextKey] = useState(2);
  const [search,setSearch] = useState("");
  const [saving,setSaving] = useState(false);
  const [error,setError] = useState("");
  const units = useApiQuery<Unit[]>(isUnit ? "/units" : null);
  const query = useApiQuery<Option[]>(isUnit ? (unit ? `/rejections/eligible-dispatches${qs({unit_id:unit})}` : null) : "/purchase-plans");
  const options = (query.data ?? []).filter(o=>o.outstanding_quantity>0);
  const byId = new Map(options.map(o=>[String(o.id),o]));
  const optionLabel = (o:Option) => `${o.item_name} · ${o.project} | ${isUnit ? `${o.invoice_number} / #${o.id} · ${formatDate(o.dispatch_date!)}` : `Plan #${o.id} · ${formatDate(o.planned_date!)}`} | Remaining ${formatQuantity(o.outstanding_quantity)}`;
  function update(key:number, change:Partial<Draft>) {setRows(old=>old.map(row=>row.key===key?{...row,...change}:row));}
  async function submit(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault();setError("");
    if(isUnit&&!unit)return setError("Select a unit.");
    if(!isReceipt&&!/^[A-Z0-9/-]{1,80}$/i.test(rgp.trim()))return setError("Enter an RGP number using letters, digits, hyphens or slashes.");
    if(rows.some(row=>!byId.has(row.reference)))return setError("Select an eligible reference for every item.");
    if(new Set(rows.map(row=>row.reference)).size!==rows.length)return setError("Each dispatch or purchase plan can appear only once per entry.");
    if(rows.some(row=>!Number.isFinite(Number(row.quantity))||Number(row.quantity)<=0||Number(row.quantity)>byId.get(row.reference)!.outstanding_quantity))return setError("Enter a positive quantity no greater than the remaining balance for each row.");
    const lines=rows.map(row=>({item_id:byId.get(row.reference)!.item_id,quantity:Number(row.quantity),...(isUnit?{dispatch_id:Number(row.reference)}:{plan_id:Number(row.reference)})}));
    setSaving(true);
    try {
      if(isReceipt)await api("/purchases",{method:"POST",body:{purchase_date:todayISO(),lines}});
      else await api(isUnit?"/rejections/batch":"/purchase-rejections/batch",{method:"POST",body:{rgp_number:rgp.trim(),rejection_date:todayISO(),...(isUnit?{unit_id:Number(unit)}:{}),lines}});
      onSaved(isReceipt?"Purchase recorded and inventory updated.":isUnit?"Unit rejection recorded and net sales updated.":"Purchase cancellation recorded and outstanding balance updated.");
    }catch(e){setError(e instanceof Error?e.message:"Unable to save entry. Refresh before retrying.");}
    finally{setSaving(false);}
  }
  return <Modal open onClose={()=>{if(!saving)onClose();}} title={TITLES[mode]} description={DESCRIPTIONS[mode]} size="xl" footer={<div className="flex justify-end gap-2"><Button variant="secondary" disabled={saving} onClick={onClose}>Cancel</Button><Button type="submit" form="linked-entry" loading={saving} disabled={query.loading||options.length===0}>Save {isReceipt?"purchase":"rejection"}</Button></div>}>
    <form id="linked-entry" onSubmit={submit} className="space-y-4">
      {(error||query.error||units.error)&&<Alert tone="error">{error||query.error||units.error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        {isReceipt?<Field label="Sr. No. (automatic)"><Input value="Generated on save" disabled/></Field>:<Field label="RGP No." required><Input required value={rgp} maxLength={80} onChange={e=>setRgp(e.target.value.toUpperCase())} disabled={saving}/></Field>}
        <Field label="Date (automatic)"><Input type="date" value={todayISO()} readOnly disabled/></Field>
        {isUnit&&<Field label="Unit / Location" required><Select required value={unit} disabled={saving} onChange={e=>{setUnit(e.target.value);setRows([{key:1,reference:"",quantity:""}]);setNextKey(2);}}><option value="">Select unit</option>{(units.data??[]).filter(u=>u.is_active).map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</Select></Field>}
      </div>
      <Field label="Find item or reference"><Input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Item, project, plan or invoice number" disabled={saving}/></Field>
      {isUnit&&!unit?<p className="text-sm text-slate-500">Select a unit to see its eligible dispatches.</p>:query.loading?<p className="text-sm text-slate-500">Loading eligible records…</p>:options.length===0?<Alert tone="info">No eligible {isUnit?"dispatches":"purchase plans"} with an outstanding quantity.</Alert>:null}
      <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full min-w-[640px] text-sm"><thead className="bg-slate-50 text-left text-xs text-slate-600"><tr>{["Sr. No.",isUnit?"Item / Actual dispatch":"Item / Purchase plan","Remaining","Quantity",""].map((h,i)=><th key={i} className="p-2">{h}</th>)}</tr></thead><tbody>{rows.map((r,i)=>{const option=byId.get(r.reference);return <tr key={r.key} className="border-t"><td className="p-2">{i+1}</td><td className="p-2 min-w-[320px]"><Select aria-label={`Reference ${i+1}`} required value={r.reference} disabled={saving||query.loading} onChange={e=>update(r.key,{reference:e.target.value,quantity:""})}><option value="">Select item and reference</option>{options.filter(o=>String(o.id)===r.reference||(!rows.some(other=>other.key!==r.key&&other.reference===String(o.id))&&optionLabel(o).toLowerCase().includes(search.toLowerCase()))).map(o=><option key={o.id} value={o.id}>{optionLabel(o)}</option>)}</Select>{option&&<p className="mt-1 text-xs text-slate-500">{option.item_name} · {option.project} · {isUnit?option.invoice_number:`Plan #${option.id}`}</p>}</td><td className="p-2 whitespace-nowrap">{option?formatQuantity(option.outstanding_quantity):"—"}</td><td className="p-2 w-28"><Input aria-label={`Quantity ${i+1}`} type="number" min="0.01" max={option?.outstanding_quantity} step="0.01" required value={r.quantity} disabled={saving||!option} onChange={e=>update(r.key,{quantity:e.target.value})}/></td><td className="p-2"><Button variant="ghost" size="icon" type="button" aria-label={`Remove row ${i+1}`} disabled={saving||rows.length===1} onClick={()=>setRows(old=>old.filter(x=>x.key!==r.key))}><Trash2 className="h-4 w-4"/></Button></td></tr>;})}</tbody></table></div>
      <div className="flex items-center justify-between"><Button variant="secondary" type="button" disabled={saving||rows.length>=100} onClick={()=>{setRows(old=>[...old,{key:nextKey,reference:"",quantity:""}]);setNextKey(n=>n+1);}}><Plus className="h-4 w-4"/> Add Item</Button><strong>Total: {formatQuantity(rows.reduce((s,r)=>s+(Number(r.quantity)||0),0))}</strong></div>
    </form>
  </Modal>;
}
