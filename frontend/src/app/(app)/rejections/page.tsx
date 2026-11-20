"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  BadgeAlert,
  ClipboardList,
  Layers,
  Plus,
  Search,
  SlidersHorizontal,
  TrendingDown,
} from "lucide-react";

import { RejectionModal } from "@/components/rejections/rejection-modal";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import {
  EmptyRow,
  LoadingRow,
  PageHeader,
  SortHeader,
  TableShell,
} from "@/components/ui/page";
import { Pagination } from "@/components/ui/pagination";
import { StatCard } from "@/components/ui/stat-card";
import { api, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useDebouncedValue } from "@/lib/hooks";
import {
  canWrite,
  type Page,
  type RejectionIssue,
  type RejectionRecord,
  type RejectionReport,
} from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";

const RejectionCharts = dynamic(
  () =>
    import("@/components/rejections/rejection-charts").then(
      (module) => module.RejectionCharts,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-72 items-center justify-center rounded-xl border border-slate-200 bg-white text-sm text-slate-500 shadow-sm">
        Loading charts…
      </div>
    ),
  },
);

const PAGE_SIZE = 20;

export default function RejectionsPage() {
  const { user } = useAuth();
  const writable = canWrite(user?.role, "rejections");

  const [fy, setFy] = useState("");
  const [family, setFamily] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [issueFilter, setIssueFilter] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("rejection_date");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const [newIssue, setNewIssue] = useState("");
  const [issueError, setIssueError] = useState<string | null>(null);
  const [issueSaving, setIssueSaving] = useState(false);

  const reportQuery = useApiQuery<RejectionReport>(
    `/reports/rejections${qs({ fy, family })}`,
    refresh,
  );
  const familiesQuery = useApiQuery<{ families: string[] }>("/items/families", refresh);
  const issuesQuery = useApiQuery<{ issues: RejectionIssue[] }>(
    `/rejection-issues${qs({ include_inactive: true })}`,
    refresh,
  );
  const listQuery = useApiQuery<Page<RejectionRecord>>(
    `/rejections${qs({
      search: debouncedSearch,
      date_from: dateFrom,
      date_to: dateTo,
      family,
      issue_id: issueFilter,
      sort,
      order,
      page,
      page_size: PAGE_SIZE,
    })}`,
    refresh,
  );

  const report = reportQuery.data;
  const families = familiesQuery.data?.families ?? [];
  const issues = issuesQuery.data?.issues ?? [];
  const records = listQuery.data;
  const activeFy = fy || report?.fy || "";

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timer);
  }, [notice]);

  function handleSort(column: string) {
    if (sort === column) {
      setOrder((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSort(column);
      setOrder(column === "rejection_date" ? "desc" : "asc");
    }
    setPage(1);
  }

  function resetReportFilters() {
    setFy("");
    setFamily("");
  }

  function resetRecordFilters() {
    setSearch("");
    setDateFrom("");
    setDateTo("");
    setIssueFilter("");
    setPage(1);
  }

  function handleSaved(message: string) {
    setModalOpen(false);
    setNotice(message);
    setRefresh((value) => value + 1);
  }

  async function addIssue(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIssueError(null);
    const name = newIssue.trim();
    if (!name) {
      setIssueError("Enter an issue name.");
      return;
    }

    setIssueSaving(true);
    try {
      await api("/rejection-issues", { method: "POST", body: { name } });
      setNewIssue("");
      setNotice(`Issue "${name}" added to the maintained list.`);
      setRefresh((value) => value + 1);
    } catch (err) {
      setIssueError(err instanceof Error ? err.message : "Unable to add the issue.");
    } finally {
      setIssueSaving(false);
    }
  }

  async function toggleIssue(issue: RejectionIssue) {
    setIssueError(null);
    try {
      await api(`/rejection-issues/${issue.id}`, {
        method: "PATCH",
        body: { is_active: !issue.is_active },
      });
      setNotice(`${issue.name} ${issue.is_active ? "deactivated" : "reactivated"}.`);
      if (issueFilter === String(issue.id) && issue.is_active) setIssueFilter("");
      setRefresh((value) => value + 1);
    } catch (err) {
      setIssueError(err instanceof Error ? err.message : "Unable to update the issue.");
    }
  }

  const reportSummary = report
    ? [
        {
          label: "Rejected (FY)",
          value: formatQuantity(report.total_quantity),
          hint: activeFy ? `Financial year ${activeFy}` : "Selected financial year",
          icon: BadgeAlert,
          tone: "rose" as const,
        },
        {
          label: "Rejection records",
          value: String(report.rejection_count),
          hint: "Recorded in the selected year",
          icon: ClipboardList,
          tone: "indigo" as const,
        },
        {
          label: "Issues seen",
          value: String(report.issues.length),
          hint: "Distinct issues with rejections",
          icon: Layers,
          tone: "sky" as const,
        },
        {
          label: "Top issue",
          value: report.top_issue ?? "—",
          hint: "Largest rejected quantity",
          icon: TrendingDown,
          tone: "amber" as const,
        },
      ]
    : [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Quality Rejections"
        description="Record customer rejections, maintain the issue list, and review rejection trends and recurring issues."
        actions={
          writable && (
            <Button onClick={() => setModalOpen(true)}>
              <Plus className="h-4 w-4" />
              Record rejection
            </Button>
          )
        }
      />

      {notice && (
        <Alert tone="success" onDismiss={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {reportQuery.error && <Alert tone="error">{reportQuery.error}</Alert>}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid grid-cols-2 gap-3 sm:w-[24rem]">
            <Field label="Financial year" htmlFor="rejection-fy">
              <Select
                id="rejection-fy"
                value={activeFy}
                onChange={(event) => setFy(event.target.value)}
                disabled={!report}
              >
                {!report && <option value="">Current year</option>}
                {report?.fy_options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Family" htmlFor="rejection-family">
              <Select
                id="rejection-family"
                value={family}
                onChange={(event) => setFamily(event.target.value)}
              >
                <option value="">All families</option>
                {families.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {(fy || family) && (
            <Button variant="ghost" onClick={resetReportFilters}>
              <SlidersHorizontal className="h-4 w-4" />
              Reset
            </Button>
          )}
          {report && (
            <p className="text-xs text-slate-500 sm:ml-auto">
              {formatDate(report.fy_start)} – {formatDate(report.fy_end)} · April–March
            </p>
          )}
        </div>
      </section>

      {report && (
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {reportSummary.map((card) => (
            <StatCard key={card.label} {...card} />
          ))}
        </section>
      )}

      {report && <RejectionCharts report={report} />}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Rejection issues</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Maintain the shared issue list. Issues with history are deactivated, never deleted.
            </p>
          </div>
        </div>

        <div className="space-y-3 px-4 py-3">
          {writable && (
            <form onSubmit={addIssue} className="flex flex-col gap-2 sm:flex-row">
              <Input
                value={newIssue}
                onChange={(event) => setNewIssue(event.target.value)}
                placeholder="Add a rejection issue, e.g. Paint peel"
                maxLength={160}
                aria-label="New rejection issue"
                disabled={issueSaving}
              />
              <Button type="submit" variant="secondary" loading={issueSaving}>
                <Plus className="h-4 w-4" />
                Add issue
              </Button>
            </form>
          )}
          {issueError && <Alert tone="error">{issueError}</Alert>}

          {issuesQuery.loading ? (
            <p className="py-4 text-center text-sm text-slate-500">Loading issues…</p>
          ) : issues.length === 0 ? (
            <p className="py-4 text-center text-sm text-slate-500">
              No rejection issues yet. Add one or enter a new issue while recording a rejection.
            </p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {issues.map((issue) => (
                <li
                  key={issue.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">{issue.name}</p>
                    <p className="text-xs text-slate-500">
                      {issue.rejection_count} rejection{issue.rejection_count === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Badge tone={issue.is_active ? "emerald" : "slate"}>
                      {issue.is_active ? "Active" : "Inactive"}
                    </Badge>
                    {writable && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleIssue(issue)}
                      >
                        {issue.is_active ? "Deactivate" : "Reactivate"}
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Search by item, issue or remarks"
              className="pl-9"
              aria-label="Search rejections"
            />
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:w-[42rem]">
            <Field label="From" htmlFor="rejection-from">
              <Input
                id="rejection-from"
                type="date"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(event) => {
                  setDateFrom(event.target.value);
                  setPage(1);
                }}
              />
            </Field>
            <Field label="To" htmlFor="rejection-to">
              <Input
                id="rejection-to"
                type="date"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(event) => {
                  setDateTo(event.target.value);
                  setPage(1);
                }}
              />
            </Field>
            <Field label="Issue" htmlFor="rejection-issue-filter">
              <Select
                id="rejection-issue-filter"
                value={issueFilter}
                onChange={(event) => {
                  setIssueFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All issues</option>
                {issues.map((issue) => (
                  <option key={issue.id} value={issue.id}>
                    {issue.name}
                    {issue.is_active ? "" : " (inactive)"}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex items-end">
              <Button
                variant="ghost"
                className="w-full"
                onClick={resetRecordFilters}
                disabled={!search && !dateFrom && !dateTo && !issueFilter}
              >
                <SlidersHorizontal className="h-4 w-4" />
                Reset
              </Button>
            </div>
          </div>
        </div>
      </section>

      {listQuery.error && <Alert tone="error">{listQuery.error}</Alert>}

      <TableShell
        footer={
          records && records.total > 0 ? (
            <Pagination
              page={records.page}
              pages={records.pages}
              total={records.total}
              pageSize={records.page_size}
              onPageChange={setPage}
            />
          ) : null
        }
      >
        <table className="min-w-full divide-y divide-slate-100 text-sm">
          <thead className="bg-slate-50/70">
            <tr>
              <SortHeader
                label="Date"
                column="rejection_date"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <SortHeader
                label="Item"
                column="item"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <SortHeader
                label="Issue"
                column="issue"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <SortHeader
                label="Quantity"
                column="quantity"
                sort={sort}
                order={order}
                onSort={handleSort}
                align="right"
              />
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase"
              >
                Recorded by
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase"
              >
                Remarks
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {listQuery.loading ? (
              <LoadingRow colSpan={6} />
            ) : !records || records.items.length === 0 ? (
              <EmptyRow
                colSpan={6}
                message={
                  writable
                    ? "No rejections match these filters. Record one to start the log."
                    : "No rejections match these filters."
                }
              />
            ) : (
              records.items.map((record) => (
                <tr key={record.id} className="transition-colors hover:bg-slate-50/60">
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                    {formatDate(record.rejection_date)}
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{record.item_name}</p>
                    <p className="text-xs text-slate-500">{record.item_family}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{record.issue_name}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-rose-700">
                    {formatQuantity(record.quantity)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                    {record.recorded_by_name}
                  </td>
                  <td
                    className="max-w-64 truncate px-4 py-3 text-slate-500"
                    title={record.remarks ?? ""}
                  >
                    {record.remarks ?? "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </TableShell>

      {modalOpen && (
        <RejectionModal
          key="new-rejection"
          open
          onClose={() => setModalOpen(false)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
