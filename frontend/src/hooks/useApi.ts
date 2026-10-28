import { useEffect, useState } from "react";
import type { Health } from "../types/api";
import { api } from "../services/api";

type Loader<T> = () => Promise<T>;

export function useApiState<T>(loader: Loader<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loader()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading };
}

export function useHealth(): { data: Health | null; error: string | null; loading: boolean } {
  return useApiState<Health>(api.health, []);
}
