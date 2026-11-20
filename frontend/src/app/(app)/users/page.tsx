"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LockKeyhole, Pencil, Plus, Search, ShieldAlert } from "lucide-react";

import { UserModal } from "@/components/users/user-modal";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { EmptyRow, LoadingRow, PageHeader, TableShell } from "@/components/ui/page";
import { Pagination } from "@/components/ui/pagination";
import { qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useDebouncedValue } from "@/lib/hooks";
import { ROLE_LABELS, roleTone, type Page, type User } from "@/lib/types";

const PAGE_SIZE = 20;

export default function UsersPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);

  const isAdmin = user?.role === "ADMIN";
  const usersQuery = useApiQuery<Page<User>>(
    isAdmin ? `/users${qs({ search: debouncedSearch, page, page_size: PAGE_SIZE })}` : null,
    refresh,
  );
  const data = usersQuery.data;
  const loading = usersQuery.loading;

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timer);
  }, [notice]);

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-600 ring-1 ring-rose-100">
          <ShieldAlert className="h-6 w-6" />
        </span>
        <h1 className="mt-4 text-lg font-semibold text-slate-900">Administrator access required</h1>
        <p className="mt-1 text-sm text-slate-500">
          Your role does not allow user management. Ask an administrator if you need access.
        </p>
        <Link
          href="/stock"
          className="mt-5 inline-flex h-9 items-center rounded-lg bg-indigo-600 px-3.5 text-sm font-medium text-white hover:bg-indigo-500"
        >
          Back to stock
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Users"
        description="Create accounts and control what each role can do."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setModalOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            New user
          </Button>
        }
      />

      {notice && (
        <Alert tone="success" onDismiss={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {usersQuery.error && <Alert tone="error">{usersQuery.error}</Alert>}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Search by name or username"
            className="pl-9"
            aria-label="Search users"
          />
        </div>
      </section>

      <TableShell
        footer={
          data && data.total > 0 ? (
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              pageSize={data.page_size}
              onPageChange={setPage}
            />
          ) : null
        }
      >
        <table className="min-w-full divide-y divide-slate-100 text-sm">
          <thead className="bg-slate-50/70">
            <tr>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Name
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Username
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Role
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Status
              </th>
              <th scope="col" className="px-4 py-3 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <LoadingRow colSpan={5} />
            ) : !data || data.items.length === 0 ? (
              <EmptyRow colSpan={5} message="No users match this search." />
            ) : (
              data.items.map((row) => (
                <tr key={row.id} className="transition-colors hover:bg-slate-50/60">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">
                      {row.full_name}
                      {row.id === user?.id && (
                        <span className="ml-2 text-xs font-normal text-slate-400">(you)</span>
                      )}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{row.username}</td>
                  <td className="px-4 py-3">
                    <Badge tone={roleTone(row.role)}>
                      <LockKeyhole className="h-3 w-3" />
                      {ROLE_LABELS[row.role]}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={row.is_active ? "emerald" : "slate"}>
                      {row.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setEditing(row);
                        setModalOpen(true);
                      }}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </TableShell>

      <UserModal
        key={`${modalOpen}-${editing?.id ?? "new"}`}
        open={modalOpen}
        user={editing}
        currentUserId={user?.id ?? 0}
        onClose={() => setModalOpen(false)}
        onSaved={(message) => {
          setModalOpen(false);
          setNotice(message);
          setRefresh((value) => value + 1);
        }}
      />
    </div>
  );
}
