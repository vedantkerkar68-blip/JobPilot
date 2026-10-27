import { useCallback, useEffect, useRef, useState } from 'react';
import type { DependencyList } from 'react';

import type { ApiError } from '../api/client';
import { toApiError } from '../api/client';

export interface ApiState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  /** True only for the first load, so panels can show a skeleton once. */
  initialLoading: boolean;
  /** Bumped to force a refetch; call from a "refresh" control. */
  reload: () => void;
  /** Timestamp of the last successful response, if any. */
  updatedAt: Date | null;
}

/**
 * Minimal data-fetching hook: no cache library, no global store.
 *
 * Stale responses are discarded (guarded by an `active` flag plus an AbortController),
 * which keeps the tracker's filter/pagination interactions race-free.
 */
export function useApi<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: DependencyList = [],
): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const loadedOnce = useRef(false);

  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    setLoading(true);
    setError(null);

    loaderRef
      .current(controller.signal)
      .then((result) => {
        if (!active) return;
        setData(result);
        setUpdatedAt(new Date());
        loadedOnce.current = true;
      })
      .catch((cause: unknown) => {
        if (!active) return;
        // An aborted request is not a user-visible failure.
        if (controller.signal.aborted) return;
        setError(toApiError(cause));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  return { data, error, loading, initialLoading: loading && !loadedOnce.current, reload, updatedAt };
}
