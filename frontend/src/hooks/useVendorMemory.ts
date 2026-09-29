import { useCallback, useEffect, useState } from 'react';
import { vendorAPI } from '../api/endpoints';
import { errorMessage, isCancelled } from '../api/client';
import type { ApiError, TimelineEvent, VendorProfile } from '../types';

/** Every vendor with its decision history. Served from the backend's local log: no credits spent. */
export const useVendors = () => {
  const [state, setState] = useState<{ vendors: VendorProfile[]; loading: boolean; error: string | null }>({
    vendors: [],
    loading: true,
    error: null,
  });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    vendorAPI.getAllVendors(controller.signal).then(
      (vendors) => setState({ vendors, loading: false, error: null }),
      (err: unknown) => {
        if (!isCancelled(err)) {
          setState((current) => ({ ...current, loading: false, error: errorMessage(err, 'Failed to load vendors') }));
        }
      },
    );
    return () => controller.abort();
  }, [version]);

  const refresh = useCallback(() => setVersion((current) => current + 1), []);

  return { ...state, refresh };
};

interface VendorState {
  profile: VendorProfile | null;
  timeline: TimelineEvent[];
  loading: boolean;
  error: string | null;
  notFound: boolean;
}

/** One vendor's profile and its timeline of reviews and human decisions. */
export const useVendorMemory = (vendorName: string) => {
  const [state, setState] = useState<VendorState>({ profile: null, timeline: [], loading: true, error: null, notFound: false });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      vendorAPI.getVendorProfile(vendorName, controller.signal),
      vendorAPI.getVendorTimeline(vendorName, controller.signal),
    ]).then(
      ([profile, timeline]) => setState({ profile, timeline, loading: false, error: null, notFound: false }),
      (err: unknown) => {
        if (isCancelled(err)) return;
        setState((current) => ({
          ...current,
          loading: false,
          notFound: (err as ApiError).status === 404,
          error: errorMessage(err, 'Failed to load this vendor'),
        }));
      },
    );
    return () => controller.abort();
  }, [vendorName, version]);

  const refresh = useCallback(() => setVersion((current) => current + 1), []);

  return { ...state, refresh };
};
