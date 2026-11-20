import { useEffect, useState } from "react";

import { api } from "./api";

interface QueryState<T> {
  key: string;
  data?: T;
  error?: string;
}

/**
 * Small client-side query hook: keyed results keep stale responses from
 * overwriting newer filters, and loading is derived instead of set in effects.
 */
export function useApiQuery<T>(path: string | null, refreshKey = 0) {
  const key = path === null ? null : `${refreshKey}|${path}`;
  const [state, setState] = useState<QueryState<T>>({ key: "" });

  useEffect(() => {
    if (path === null || key === null) return;
    let active = true;
    api<T>(path)
      .then((data) => {
        if (active) setState({ key, data });
      })
      .catch((error: unknown) => {
        if (active) {
          setState({
            key,
            error: error instanceof Error ? error.message : "Unable to load data.",
          });
        }
      });
    return () => {
      active = false;
    };
  }, [key, path]);

  const current = key !== null && state.key === key;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : null,
    loading: key !== null && !current,
  };
}

export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
