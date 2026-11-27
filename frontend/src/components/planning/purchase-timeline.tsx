"use client";
import { useState } from "react";
import type { Priority } from "@/lib/types";
import { formatQuantity } from "@/lib/utils";
import { timelineRange } from "@/lib/planning";
import { ContinuousTimeline } from "./continuous-timeline";
interface Row {id:number;item_name:string;project:string;quantity:number;planned_date:string;planned_end_date:string;category:Priority;received_quantity:number;cancelled_quantity:number;outstanding_quantity:number;status:string}
export function PurchaseTimeline({plans,loading}:{plans:Row[];loading?:boolean}) {
  const [range] = useState(()=>timelineRange());
  return <ContinuousTimeline mode="purchase" range={range} loading={loading} rows={plans.map(p=>({
    ...p,closed:p.outstanding_quantity<=0,detail:p.status,totals:`${formatQuantity(p.quantity)} / ${formatQuantity(p.received_quantity)} / ${formatQuantity(p.cancelled_quantity)} / ${formatQuantity(p.outstanding_quantity)}${p.outstanding_quantity>0&&p.planned_end_date<range.today?" · Overdue":""}`,
  }))}/>;
}
