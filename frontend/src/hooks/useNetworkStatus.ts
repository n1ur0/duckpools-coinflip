/**
 * useNetworkStatus - Detects network connectivity and API availability
 *
 * Returns online/offline status and a helper to check if the backend is reachable.
 * Provides a reactive hook for components to show "you're offline" messages.
 */

import { useState, useEffect, useCallback } from 'react';

interface NetworkStatus {
  /** true if navigator.onLine (browser thinks it has network) */
  isOnline: boolean;
  /** true if backend API is reachable (checked on mount and interval) */
  isApiReachable: boolean | null; // null = hasn't been checked yet
  /** Manually re-check API reachability */
  checkApi: () => Promise<boolean>;
  /** Timestamp of last successful API check */
  lastChecked: number | null;
}

/**
 * Hook to monitor network and API health.
 * @param apiUrl - URL to health-check (default: /api/health)
 * @param checkIntervalMs - how often to re-check (default: 30000, set 0 to disable)
 */
export function useNetworkStatus(
  apiUrl: string = '/api/health',
  checkIntervalMs: number = 30_000
): NetworkStatus {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isApiReachable, setIsApiReachable] = useState<boolean | null>(null);
  const [lastChecked, setLastChecked] = useState<number | null>(null);

  const checkApi = useCallback(async (): Promise<boolean> => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const res = await fetch(apiUrl, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const ok = res.ok;
      setIsApiReachable(ok);
      setLastChecked(Date.now());
      return ok;
    } catch {
      setIsApiReachable(false);
      setLastChecked(Date.now());
      return false;
    }
  }, [apiUrl]);

  // Listen for browser online/offline events
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      checkApi(); // Re-check API when coming back online
    };
    const handleOffline = () => {
      setIsOnline(false);
      setIsApiReachable(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [checkApi]);

  // Initial check + periodic polling
  useEffect(() => {
    checkApi();
    if (checkIntervalMs <= 0) return;

    const interval = setInterval(checkApi, checkIntervalMs);
    return () => clearInterval(interval);
  }, [checkApi, checkIntervalMs]);

  return { isOnline, isApiReachable, checkApi, lastChecked };
}

export default useNetworkStatus;
