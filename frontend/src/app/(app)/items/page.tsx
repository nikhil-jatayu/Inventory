"use client";

import { useEffect, useState } from "react";
import { Pencil, Plus, RotateCcw, Search, SlidersHorizontal } from "lucide-react";

import { ItemModal } from "@/components/items/item-modal";
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
import { api, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useDebouncedValue } from "@/lib/hooks";
import { canWrite, type Item, type Page } from "@/lib/types";
import { formatDate, formatQuantity } from "@/lib/utils";

const PAGE_SIZE = 20;

export default function ItemsPage() {
  const { user } = useAuth();
  const writable = canWrite(user?.role, "items");

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [family, setFamily] = useState("");
  const [active, setActive] = useState("true");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("name");
  const [order, setOrder] = useState<"asc" | "desc">("asc");

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Item | null>(null);

  const itemsQuery = useApiQuery<Page<Item>>(
    `/items${qs({
      search: debouncedSearch,
      family,
      is_active: active === "all" ? undefined : active === "true",
      sort,
      order,
      page,
      page_size: PAGE_SIZE,
    })}`,
    refresh,
  );
  const familiesQuery = useApiQuery<{ families: string[] }>("/items/families", refresh);

  const data = itemsQuery.data;
  const families = familiesQuery.data?.families ?? [];
  const loading = itemsQuery.loading;

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
      setOrder("asc");
    }
    setPage(1);
  }

  function openCreate() {
    setEditing(null);
    setModalOpen(true);
  }

  function openEdit(item: Item) {
    setEditing(item);
    setModalOpen(true);
  }

  async function handleDeactivate(item: Item) {
    if (!window.confirm(`Deactivate ${item.name}? History is kept and it can be reactivated later.`)) {
      return;
    }
    setError(null);
    try {
      await api(`/items/${item.id}`, { method: "DELETE" });
      setNotice(`${item.name} deactivated.`);
      setRefresh((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to deactivate the item.");
    }
  }

  async function handleReactivate(item: Item) {
    setError(null);
    try {
      await api(`/items/${item.id}`, { method: "PATCH", body: { is_active: true } });
      setNotice(`${item.name} reactivated.`);
      setRefresh((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reactivate the item.");
    }
  }

  const columnCount = writable ? 6 : 5;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Item Master"
        description="Maintain items, families and the stock levels that drive status alerts."
        actions={
          writable && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New item
            </Button>
          )
        }
      />

      {notice && (
        <Alert tone="success" onDismiss={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {itemsQuery.error && <Alert tone="error">{itemsQuery.error}</Alert>}
      {error && (
        <Alert tone="error" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Search by item name or family"
              className="pl-9"
              aria-label="Search items"
            />
          </div>
          <div className="grid grid-cols-2 gap-3 sm:w-auto">
            <Field label="Family" htmlFor="items-family">
              <Select
                id="items-family"
                value={family}
                onChange={(event) => {
                  setFamily(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All families</option>
                {families.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status" htmlFor="items-active">
              <Select
                id="items-active"
                value={active}
                onChange={(event) => {
                  setActive(event.target.value);
                  setPage(1);
                }}
              >
                <option value="true">Active</option>
                <option value="false">Inactive</option>
                <option value="all">All items</option>
              </Select>
            </Field>
          </div>
          {(search || family || active !== "true") && (
            <Button
              variant="ghost"
              size="md"
              onClick={() => {
                setSearch("");
                setFamily("");
                setActive("true");
                setPage(1);
              }}
            >
              <SlidersHorizontal className="h-4 w-4" />
              Reset
            </Button>
          )}
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
              <SortHeader label="Item" column="name" sort={sort} order={order} onSort={handleSort} />
              <SortHeader label="Family" column="family" sort={sort} order={order} onSort={handleSort} />
              <SortHeader
                label="Reorder"
                column="reorder_level"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <SortHeader
                label="Critical"
                column="critical_level"
                sort={sort}
                order={order}
                onSort={handleSort}
              />
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Status
              </th>
              {writable && (
                <th scope="col" className="px-4 py-3 text-right text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <LoadingRow colSpan={columnCount} />
            ) : !data || data.items.length === 0 ? (
              <EmptyRow colSpan={columnCount} message="No items match these filters." />
            ) : (
              data.items.map((item) => (
                <tr key={item.id} className="transition-colors hover:bg-slate-50/60">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{item.name}</p>
                    <p className="text-xs text-slate-400">Added {formatDate(item.created_at)}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{item.family}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">
                    {formatQuantity(item.reorder_level)}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">
                    {formatQuantity(item.critical_level)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={item.is_active ? "emerald" : "slate"}>
                      {item.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  {writable && (
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => openEdit(item)}>
                          <Pencil className="h-3.5 w-3.5" />
                          Edit
                        </Button>
                        {item.is_active ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                            onClick={() => handleDeactivate(item)}
                          >
                            Deactivate
                          </Button>
                        ) : (
                          <Button variant="ghost" size="sm" onClick={() => handleReactivate(item)}>
                            <RotateCcw className="h-3.5 w-3.5" />
                            Reactivate
                          </Button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </TableShell>

      <ItemModal
        key={`${modalOpen}-${editing?.id ?? "new"}`}
        open={modalOpen}
        item={editing}
        families={families}
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
