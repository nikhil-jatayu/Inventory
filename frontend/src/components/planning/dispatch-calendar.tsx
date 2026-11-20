"use client";

import FullCalendar from "@fullcalendar/react";
import type {
  DateClickInfo,
  DatesSetInfo,
  EventClickInfo,
  EventDisplayInfo,
  MountInfo,
} from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/react/daygrid";
import interactionPlugin from "@fullcalendar/react/interaction";
import classicThemePlugin from "@fullcalendar/react/themes/classic";

import "@fullcalendar/react/skeleton.css";
import "@fullcalendar/react/themes/classic/theme.css";
import "@fullcalendar/react/themes/classic/palette.css";

import { PRIORITY_COLORS, type DispatchPlan } from "@/lib/types";
import { cn, formatQuantity, isoDate } from "@/lib/utils";

interface DispatchCalendarProps {
  plans: DispatchPlan[];
  onSelectPlan: (plan: DispatchPlan) => void;
  onSelectDate?: (date: string) => void;
  onRangeChange: (from: string, to: string) => void;
}

export function DispatchCalendar({
  plans,
  onSelectPlan,
  onSelectDate,
  onRangeChange,
}: DispatchCalendarProps) {
  const events = plans.map((plan) => ({
    id: String(plan.id),
    title: `${plan.item_name} · ${formatQuantity(plan.quantity)}`,
    start: plan.planned_date,
    allDay: true,
    className: cn(
      "fc-plan-event",
      plan.warning && "fc-plan-warning",
      plan.status === "DONE" && "fc-plan-done",
    ),
    extendedProps: { plan },
  }));

  function handleEventMount(info: MountInfo<EventDisplayInfo>) {
    const plan = info.event.extendedProps.plan as DispatchPlan | undefined;
    if (!plan) return;
    info.el.style.setProperty("--fc-event-color", PRIORITY_COLORS[plan.priority].background);
    info.el.style.setProperty("--fc-event-contrast-color", "#ffffff");
    info.el.title = `${plan.po_number} · ${plan.customer_name} · ${plan.item_name} · ${formatQuantity(plan.quantity)} (${plan.priority.toLowerCase()})`;
  }

  function handleDatesSet(info: DatesSetInfo) {
    const lastDay = new Date(info.end.getFullYear(), info.end.getMonth(), info.end.getDate() - 1);
    onRangeChange(isoDate(info.start), isoDate(lastDay));
  }

  function handleEventClick(info: EventClickInfo) {
    const plan = info.event.extendedProps.plan as DispatchPlan | undefined;
    if (plan) onSelectPlan(plan);
  }

  function handleDateClick(info: DateClickInfo) {
    onSelectDate?.(info.dateStr);
  }

  return (
    <div className="dispatch-calendar">
      <FullCalendar
        plugins={[dayGridPlugin, interactionPlugin, classicThemePlugin]}
        initialView="dayGridMonth"
        headerToolbar={{ left: "prev,next today", center: "title", right: "" }}
        firstDay={1}
        fixedWeekCount={false}
        dayMaxEvents={3}
        height="auto"
        events={events}
        eventDidMount={handleEventMount}
        datesSet={handleDatesSet}
        eventClick={handleEventClick}
        dateClick={onSelectDate ? handleDateClick : undefined}
      />
    </div>
  );
}
