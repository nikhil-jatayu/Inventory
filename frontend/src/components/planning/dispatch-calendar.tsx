"use client";
import { useEffect, useState } from "react";
import type { DispatchPlan } from "@/lib/types";
import { formatQuantity } from "@/lib/utils";
import { timelineRange } from "@/lib/planning";
import { ContinuousTimeline, type TimelineRange } from "./continuous-timeline";

export type GanttPlan = DispatchPlan & { actual_dispatches: { id: number; dispatch_date: string; quantity: number }[] };
interface Props {
  plans: GanttPlan[];
  range?: TimelineRange;
  loading?: boolean;
  onSelectPlan?: (plan: DispatchPlan) => void;
  onRangeChange?: (from: string, to: string) => void;
  onSelectDate?: (date: string) => void;
}
export function DispatchCalendar({plans,range,loading,onSelectPlan,onRangeChange,onSelectDate}:Props) {
  const [initialRange] = useState(() => timelineRange());
  const activeRange = range ?? initialRange;
  const {from,to} = activeRange;
  useEffect(()=>{onRangeChange?.(from,to);},[from,to,onRangeChange]);
  return <ContinuousTimeline mode="dispatch" range={activeRange} loading={loading} onSelectDate={onSelectDate} onSelectPlan={onSelectPlan ? id=>{const plan=plans.find(p=>p.id===id);if(plan)onSelectPlan(plan);} : undefined} rows={plans.map(p=>({
    id:p.id,item_name:p.item_name,project:p.project,planned_date:p.planned_date,planned_end_date:p.planned_end_date,quantity:p.quantity,category:p.priority,closed:p.status==="DONE",actuals:p.actual_dispatches,
    detail:`${p.unit_name??p.unit_number??"Unit not set"} · ${p.status}`,
    totals:`${formatQuantity(p.quantity)} / ${formatQuantity(p.fulfilled_quantity)} / ${formatQuantity(p.outstanding_quantity)}${p.status!=="DONE"&&p.days_until_end<0?" · Overdue":p.warning?" · Short duration":""}`,
  }))}/>;
}
