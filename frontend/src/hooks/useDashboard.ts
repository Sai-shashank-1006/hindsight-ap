import { useCallback, useEffect, useState } from 'react';
import { dashboardAPI, systemAPI } from '../api/endpoints';
import { errorMessage, isCancelled } from '../api/client';
import { DASHBOARD_POLL_MS, HEALTH_POLL_MS } from '../utils/constants';
import type { DashboardData, DashboardStats, HealthStatus } from '../types';

/** Loads now, then every `intervalMs` while the tab is visible. Cancels in-flight requests on unmount. */
function usePolling(load: (signal: AbortSignal) => Promise<void>, intervalMs: number): void {
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load(controller.signal);
    }, intervalMs);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [load, intervalMs]);
}

/**
 * Dashboard numbers, refreshed every 10 s. The backend serves these from its local decision log,
 * so polling spends no Groq or Hindsight credits. Only the first load shows a spinner; a failed
 * refresh keeps the last good data and reports the error alongside it.
 */
export const useDashboard = (pollMs: number = DASHBOARD_POLL_MS) => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [board, numbers] = await Promise.all([dashboardAPI.getDashboard(signal), dashboardAPI.getStats(signal)]);
      setData(board);
      setStats(numbers);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      if (!isCancelled(err)) setError(errorMessage(err, 'Failed to load the dashboard'));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  usePolling(load, pollMs);
  const refresh = useCallback(() => load(), [load]);

  return { data, stats, loading, error, lastUpdated, refresh };
};

/** Which services the backend can use. /health pings Hindsight, so it is polled once a minute. */
export const useHealth = (pollMs: number = HEALTH_POLL_MS) => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setHealth(await systemAPI.getHealth(signal));
      setError(null);
    } catch (err) {
      if (!isCancelled(err)) {
        setHealth(null);
        setError(errorMessage(err, 'The API is unreachable'));
      }
    } finally {
      if (!signal?.aborted) setChecking(false);
    }
  }, []);

  usePolling(load, pollMs);
  const refresh = useCallback(() => {
    setChecking(true);
    void load();
  }, [load]);

  return { health, error, checking, refresh };
};
