export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

const quantityFormatter = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export function formatQuantity(value: number): string {
  return quantityFormatter.format(value);
}

export function formatDate(value: string): string {
  const normalized = value.length === 10 ? `${value}T00:00:00` : value;
  return new Date(normalized).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function todayISO(): string {
  return isoDate(new Date());
}

export function isoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function currentMonth(): string {
  return todayISO().slice(0, 7);
}

export function monthRange(month: string): { from: string; to: string } {
  const [year, monthNumber] = month.split("-").map(Number);
  const start = new Date(year, (monthNumber || 1) - 1, 1);
  const end = new Date(year, monthNumber || 1, 0);
  return { from: isoDate(start), to: isoDate(end) };
}

export function daysBetween(fromISO: string, toISOValue: string): number {
  const from = new Date(`${fromISO}T00:00:00`);
  const to = new Date(`${toISOValue}T00:00:00`);
  return Math.round((to.getTime() - from.getTime()) / 86_400_000);
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
