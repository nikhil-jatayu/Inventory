"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronsUpDown, Search, X } from "lucide-react";

import { qs } from "@/lib/api";
import { useApiQuery, useDebouncedValue } from "@/lib/hooks";
import type { POLineOption } from "@/lib/types";
import { formatQuantity } from "@/lib/utils";

interface POLinePickerProps {
  value: POLineOption | null;
  onChange: (value: POLineOption | null) => void;
  disabled?: boolean;
  mode?: "plan" | "dispatch";
}

export function POLinePicker({
  value,
  onChange,
  disabled,
  mode = "plan",
}: POLinePickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const debouncedQuery = useDebouncedValue(query, 250);
  const dispatchMode = mode === "dispatch";
  const amountLabel = dispatchMode ? "Balance to dispatch" : "Available to plan";
  const amount = (option: POLineOption) =>
    dispatchMode ? option.balance_quantity : option.available_to_plan;

  const linesQuery = useApiQuery<POLineOption[]>(
    open
      ? `/purchase-orders/lines${qs({
          search: debouncedQuery,
          available_only: !dispatchMode,
          balance_only: dispatchMode,
          limit: 50,
        })}`
      : null,
  );
  const options = linesQuery.data ?? [];

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
      <div className="flex items-start justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-800">
            {value.po_number} · {value.item_name}
          </p>
          <p className="truncate text-xs text-slate-500">
            {value.customer_name} · {value.unit_number}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {amountLabel}:{" "}
            <span className="font-semibold text-slate-700">
              {formatQuantity(amount(value))}
            </span>
          </p>
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
            aria-label={
              dispatchMode ? "Change dispatch purchase order line" : "Change purchase order line"
            }
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
          placeholder="Search open PO lines by PO, customer or item…"
          className="h-9.5 w-full rounded-lg border-0 bg-white py-2 pr-9 pl-9 text-sm text-slate-900 shadow-sm ring-1 ring-slate-300 ring-inset placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:ring-inset disabled:bg-slate-50"
        />
        <ChevronsUpDown className="pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
      </div>

      {open && (
        <div className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {linesQuery.loading ? (
            <p className="px-3 py-3 text-sm text-slate-500">Searching…</p>
          ) : options.length === 0 ? (
            <p className="px-3 py-3 text-sm text-slate-500">
              No PO lines with a remaining {dispatchMode ? "balance" : "planning capacity"}.
            </p>
          ) : (
            options.map((option) => (
              <button
                key={option.po_line_id}
                type="button"
                onClick={() => {
                  onChange(option);
                  setQuery("");
                  setOpen(false);
                }}
                className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left transition-colors hover:bg-indigo-50"
              >
                <span className="text-sm font-medium text-slate-800">
                  {option.po_number} · {option.item_name}
                </span>
                <span className="text-xs text-slate-500">
                  {option.customer_name} · {option.unit_number}
                </span>
                <span className="text-xs text-slate-400">
                  {amountLabel} {formatQuantity(amount(option))}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
