import { useCallback, useEffect, useState } from 'react';
import {
  getOperatorLocation,
  getOperatorsNearby,
  type OperatorLocation,
  type OperatorsNearbyResponse,
} from '../services/radioshaqApi';

const locationCache = new Map<string, { data: OperatorLocation; at: number }>();
const CACHE_TTL_MS = 60_000;

function getCachedLocation(callsign: string): OperatorLocation | null {
  const key = callsign.trim().toUpperCase();
  const entry = locationCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.at > CACHE_TTL_MS) {
    locationCache.delete(key);
    return null;
  }
  return entry.data;
}

function setCachedLocation(callsign: string, data: OperatorLocation): void {
  locationCache.set(callsign.trim().toUpperCase(), { data, at: Date.now() });
}

export interface UseOperatorLocationResult {
  location: OperatorLocation | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useOperatorLocation(callsign: string | null | undefined): UseOperatorLocationResult {
  const [location, setLocation] = useState<OperatorLocation | null>(() =>
    callsign ? getCachedLocation(callsign) : null
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    const cs = callsign?.trim().toUpperCase();
    if (!cs) {
      setLocation(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getOperatorLocation(cs);
      setCachedLocation(cs, data);
      setLocation(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load location');
      setLocation(getCachedLocation(cs));
    } finally {
      setLoading(false);
    }
  }, [callsign]);

  useEffect(() => {
    const cs = callsign?.trim().toUpperCase();
    if (!cs) {
      setLocation(null);
      setError(null);
      return;
    }
    const cached = getCachedLocation(cs);
    if (cached) {
      setLocation(cached);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getOperatorLocation(cs)
      .then((data) => {
        if (!cancelled) {
          setCachedLocation(cs, data);
          setLocation(data);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load location');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [callsign]);

  return { location, loading, error, refetch };
}

export interface UseOperatorsNearbyParams {
  center: { lat: number; lng: number } | null;
  radius_meters?: number;
  recent_hours?: number;
  max_results?: number;
  enabled?: boolean;
}

export interface UseOperatorsNearbyResult {
  data: OperatorsNearbyResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useOperatorsNearby(params: UseOperatorsNearbyParams): UseOperatorsNearbyResult {
  const {
    center,
    radius_meters = 50_000,
    recent_hours = 24,
    max_results = 100,
    enabled = true,
  } = params;
  const [data, setData] = useState<OperatorsNearbyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!center || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getOperatorsNearby({
        latitude: center.lat,
        longitude: center.lng,
        radius_meters,
        recent_hours,
        max_results,
      });
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load operators nearby');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [center?.lat, center?.lng, radius_meters, recent_hours, max_results, enabled]);

  useEffect(() => {
    if (!center || !enabled) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getOperatorsNearby({
      latitude: center.lat,
      longitude: center.lng,
      radius_meters,
      recent_hours,
      max_results,
    })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load operators nearby');
          setData(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [center?.lat, center?.lng, radius_meters, recent_hours, max_results, enabled]);

  return { data, loading, error, refetch };
}
