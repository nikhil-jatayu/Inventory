export type Role = "ADMIN" | "STORE" | "QUALITY" | "VIEWER";

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Item {
  id: number;
  name: string;
  family: string;
  reorder_level: number;
  critical_level: number;
  is_active: boolean;
  created_at: string;
}

export type StockTxnType = "OPENING" | "RECEIPT" | "ADJUSTMENT" | "DISPATCH";
export type StockStatus = "OK" | "BELOW_REORDER" | "CRITICAL";

export interface StockRow {
  item_id: number;
  name: string;
  family: string;
  available: number;
  reorder_level: number;
  critical_level: number;
  status: StockStatus;
}

export interface StockSummary {
  total_items: number;
  critical: number;
  below_reorder: number;
  ok: number;
}

export interface StockTransaction {
  id: number;
  item_id: number;
  item_name: string;
  type: StockTxnType;
  quantity: number;
  date: string;
  ref: string | null;
  remarks: string | null;
  created_at: string;
}

export const ROLE_LABELS: Record<Role, string> = {
  ADMIN: "Administrator",
  STORE: "Store",
  QUALITY: "Quality",
  VIEWER: "Viewer",
};

export type WriteResource =
  | "stock"
  | "items"
  | "users"
  | "purchase_orders"
  | "planning"
  | "dispatches"
  | "rejections";

export function canWrite(role: Role | undefined, resource: WriteResource): boolean {
  if (!role) return false;
  if (resource === "users") return role === "ADMIN";
  if (resource === "rejections") return role === "ADMIN" || role === "QUALITY";
  return role === "ADMIN" || role === "STORE";
}

export type BadgeTone = "slate" | "indigo" | "emerald" | "amber" | "rose" | "sky";

export function roleTone(role: Role): BadgeTone {
  switch (role) {
    case "ADMIN":
      return "indigo";
    case "STORE":
      return "sky";
    case "QUALITY":
      return "amber";
    default:
      return "slate";
  }
}

export type POStatus = "OPEN" | "PARTIAL" | "COMPLETED" | "CANCELLED";
export type Priority = "NORMAL" | "URGENT" | "EMERGENCY";
export type PlanStatus = "PLANNED" | "PARTIAL" | "DONE";
export type ScheduleFilter = "ALL" | "CRITICAL" | "BELOW_REORDER" | "SHORTFALL" | "REPLENISH" | "OK";

export interface POLine {
  id: number;
  item_id: number;
  item_name: string;
  item_family: string;
  quantity: number;
  planned_quantity: number;
  dispatched_quantity: number;
  balance_quantity: number;
  available_to_plan: number;
}

export interface PurchaseOrderSummary {
  id: number;
  po_number: string;
  customer_name: string;
  unit_number: string;
  po_date: string;
  status: POStatus;
  line_count: number;
  total_quantity: number;
  total_planned: number;
  total_dispatched: number;
  total_balance: number;
}

export interface PurchaseOrder extends PurchaseOrderSummary {
  lines: POLine[];
}

export interface POLineOption {
  po_line_id: number;
  po_id: number;
  po_number: string;
  customer_name: string;
  unit_number: string;
  po_date: string;
  item_id: number;
  item_name: string;
  item_family: string;
  quantity: number;
  planned_quantity: number;
  dispatched_quantity: number;
  balance_quantity: number;
  available_to_plan: number;
}

export interface DispatchPlan {
  id: number;
  po_line_id: number;
  po_id: number;
  po_number: string;
  customer_name: string;
  unit_number: string;
  item_id: number;
  item_name: string;
  item_family: string;
  planned_date: string;
  quantity: number;
  fulfilled_quantity: number;
  outstanding_quantity: number;
  priority: Priority;
  status: PlanStatus;
  lead_time_days: number;
  days_until: number;
  warning: boolean;
  po_quantity: number;
  po_planned: number;
  po_dispatched: number;
  po_balance: number;
  po_available_to_plan: number;
}

export interface PlanningSettings {
  today: string;
  fy_start_month: number;
  lead_times: Record<Priority, number>;
}

export interface DispatchRecord {
  id: number;
  po_line_id: number;
  po_id: number;
  po_number: string;
  customer_name: string;
  unit_number: string;
  item_id: number;
  item_name: string;
  item_family: string;
  dispatch_date: string;
  quantity: number;
  remarks: string | null;
}

export interface DispatchMonth {
  month: string;
  label: string;
  planned: number;
  dispatched: number;
  cumulative: number;
}

export interface DispatchFYTotal {
  fy: string;
  start_year: number;
  dispatched: number;
  planned: number;
}

export interface DispatchReport {
  fy: string;
  fy_start: string;
  fy_end: string;
  fy_options: string[];
  months: DispatchMonth[];
  fy_totals: DispatchFYTotal[];
  total_dispatched: number;
  total_planned: number;
  cumulative_dispatched: number;
  dispatch_count: number;
}

export interface RejectionIssue {
  id: number;
  name: string;
  is_active: boolean;
  rejection_count: number;
}

export interface RejectionRecord {
  id: number;
  item_id: number;
  item_name: string;
  item_family: string;
  rejection_date: string;
  quantity: number;
  issue_id: number;
  issue_name: string;
  remarks: string | null;
  recorded_by: number;
  recorded_by_name: string;
}

export interface RejectionMonth {
  month: string;
  label: string;
  quantity: number;
}

export interface RejectionIssueStat {
  issue_id: number;
  name: string;
  quantity: number;
  count: number;
  share: number;
  cumulative_share: number;
}

export interface RejectionReport {
  fy: string;
  fy_start: string;
  fy_end: string;
  fy_options: string[];
  months: RejectionMonth[];
  issues: RejectionIssueStat[];
  total_quantity: number;
  rejection_count: number;
  top_issue: string | null;
}

export interface DashboardKPIs {
  critical_items: number;
  below_reorder_items: number;
  total_shortfall: number;
  month_planned: number;
  month_dispatched: number;
  month_rejected: number;
}

export interface DashboardMonth {
  month: string;
  label: string;
  planned: number;
  dispatched: number;
  rejected: number;
}

export interface DashboardCalendarDay {
  date: string;
  planned: number;
  count: number;
  normal: number;
  urgent: number;
  emergency: number;
}

export interface DashboardIssue {
  issue_id: number;
  name: string;
  quantity: number;
  count: number;
}

export interface DashboardSummary {
  month: string;
  month_label: string;
  month_start: string;
  month_end: string;
  fy: string;
  fy_start: string;
  fy_end: string;
  fy_options: string[];
  kpis: DashboardKPIs;
  months: DashboardMonth[];
  calendar: DashboardCalendarDay[];
  issues: DashboardIssue[];
}

export interface StockScheduleRow {
  item_id: number;
  name: string;
  family: string;
  available: number;
  planned_quantity: number;
  shortfall: number;
  reorder_level: number;
  critical_level: number;
  stock_status: StockStatus;
  needs_replenishment: boolean;
  flags: string[];
}

export interface ScheduleSummary {
  total_items: number;
  shortfall_items: number;
  total_shortfall: number;
  critical: number;
  below_reorder: number;
  needs_replenishment: number;
}

export interface SchedulePage extends Page<StockScheduleRow> {
  date_from: string;
  date_to: string;
  summary: ScheduleSummary;
}

export function poStatusTone(status: POStatus): BadgeTone {
  if (status === "COMPLETED") return "emerald";
  if (status === "PARTIAL") return "amber";
  if (status === "CANCELLED") return "slate";
  return "sky";
}

export function planStatusTone(status: PlanStatus): BadgeTone {
  if (status === "DONE") return "emerald";
  if (status === "PARTIAL") return "amber";
  return "indigo";
}

export function priorityTone(priority: Priority): BadgeTone {
  if (priority === "EMERGENCY") return "rose";
  if (priority === "URGENT") return "amber";
  return "emerald";
}

export const PRIORITY_LABELS: Record<Priority, string> = {
  NORMAL: "Normal",
  URGENT: "Urgent",
  EMERGENCY: "Emergency",
};

export const PRIORITY_COLORS: Record<Priority, { background: string; border: string }> = {
  NORMAL: { background: "#059669", border: "#047857" },
  URGENT: { background: "#d97706", border: "#b45309" },
  EMERGENCY: { background: "#e11d48", border: "#be123c" },
};
