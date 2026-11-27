import type { Priority } from "./types";
import { daysBetween, isoDate } from "./utils";

export function categoryForRange(start: string, end: string, limits?: Record<Priority, number>) {
  const duration = daysBetween(start, end);
  if (!start || !end || !Number.isFinite(duration) || duration < 0) return null;
  const category: Priority = duration > (limits?.NORMAL ?? 15) ? "NORMAL" : duration > (limits?.URGENT ?? 7) ? "URGENT" : "EMERGENCY";
  return { category, duration, warning: duration <= (limits?.EMERGENCY ?? 4) };
}

export function timelineRange(today = isoDate(new Date())) {
  const anchor = new Date(`${today}T00:00:00`);
  const shift = (days: number) => isoDate(new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate() + days));
  return { from: shift(-182), to: shift(182), today };
}

export function timelineDates(from: string, to: string): string[] {
  const start = new Date(`${from}T00:00:00`);
  return Array.from({ length: daysBetween(from, to) + 1 }, (_, i) => isoDate(new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)));
}
