import { createContext, useCallback, useContext, useEffect, useMemo } from 'react';
import type { ReactNode } from 'react';

import { getHealth, getMeta } from '../api/endpoints';
import type { HealthResponse, MetaResponse } from '../api/types';
import type { ApiError } from '../api/client';
import { useApi } from '../hooks/useApi';

/** How often the header re-checks the backend. Real polling, not fake telemetry. */
const HEALTH_POLL_MS = 60_000;

export type ConnectionState = 'ok' | 'degraded' | 'offline' | 'checking';

export interface SystemValue {
  health: HealthResponse | null;
  meta: MetaResponse | null;
  healthError: ApiError | null;
  metaError: ApiError | null;
  connection: ConnectionState;
  loading: boolean;
  lastCheckedAt: Date | null;
  refresh: () => void;
}

const SystemContext = createContext<SystemValue | null>(null);

export function SystemProvider({ children }: { children: ReactNode }) {
  const health = useApi<HealthResponse>((signal) => getHealth(signal));
  const meta = useApi<MetaResponse>((signal) => getMeta(signal));

  const { reload: reloadHealth } = health;
  const { reload: reloadMeta } = meta;

  // Both reload callbacks are stable (`useCallback` with no deps), so this
  // interval is created once and never restarted.
  useEffect(() => {
    const handle = window.setInterval(() => {
      reloadHealth();
      reloadMeta();
    }, HEALTH_POLL_MS);
    return () => window.clearInterval(handle);
  }, [reloadHealth, reloadMeta]);

  const refresh = useCallback(() => {
    reloadHealth();
    reloadMeta();
  }, [reloadHealth, reloadMeta]);

  const connection: ConnectionState = useMemo(() => {
    if (health.error && !health.data) return 'offline';
    if (!health.data) return 'checking';
    return health.data.status === 'ok' ? 'ok' : 'degraded';
  }, [health.data, health.error]);

  const value = useMemo<SystemValue>(
    () => ({
      health: health.data,
      meta: meta.data,
      healthError: health.error,
      metaError: meta.error,
      connection,
      loading: health.loading,
      lastCheckedAt: health.updatedAt,
      refresh,
    }),
    [
      health.data,
      health.error,
      health.loading,
      health.updatedAt,
      meta.data,
      meta.error,
      connection,
      refresh,
    ],
  );

  return <SystemContext.Provider value={value}>{children}</SystemContext.Provider>;
}

export function useSystem(): SystemValue {
  const value = useContext(SystemContext);
  if (!value) {
    throw new Error('useSystem must be used inside <SystemProvider>');
  }
  return value;
}
