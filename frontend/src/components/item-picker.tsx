"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronsUpDown, Search, X } from "lucide-react";

import { qs } from "@/lib/api";
import { useApiQuery, useDebouncedValue } from "@/lib/hooks";
import type { Item, Page } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface ItemOption {
  id: number;
  name: string;
  family: string;
}

interface ItemPickerProps {
  value: ItemOption | null;
  onChange: (value: ItemOption | null) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function ItemPicker({ value, onChange, placeholder = "Search items…", disabled }: ItemPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const debouncedQuery = useDebouncedValue(query, 250);
  const itemsQuery = useApiQuery<Page<Item>>(
    open
      ? `/items${qs({ search: debouncedQuery, is_active: true, sort: "name", page_size: 20 })}`
      : null,
  );
  const options = (itemsQuery.data?.items ?? []).map(({ id, name, family }) => ({
    id,
    name,
    family,
  }));

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (value) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-800">{value.name}</p>
          <p className="text-xs text-slate-500">{value.family}</p>
        </div>
        {!disabled && (
          <button
            type="button"
            onClick={() => {
              onChange(null);
              setQuery("");
              setOpen(true);
            }}
            className="rounded p-1 text-slate-400 hover:bg-white hover:text-slate-600"
            aria-label="Change item"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          value={query}
          disabled={disabled}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="h-9.5 w-full rounded-lg border-0 bg-white py-2 pr-9 pl-9 text-sm text-slate-900 shadow-sm ring-1 ring-slate-300 ring-inset placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:ring-inset disabled:bg-slate-50"
        />
        <ChevronsUpDown className="pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
      </div>

      {open && (
        <div className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {itemsQuery.loading ? (
            <p className="px-3 py-3 text-sm text-slate-500">Searching…</p>
          ) : options.length === 0 ? (
            <p className="px-3 py-3 text-sm text-slate-500">No active items found.</p>
          ) : (
            options.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => {
                  onChange(option);
                  setQuery("");
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left transition-colors hover:bg-indigo-50",
                )}
              >
                <span className="text-sm font-medium text-slate-800">{option.name}</span>
                <span className="text-xs text-slate-500">{option.family}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
