import { useEffect, useRef } from 'react';
import { getEmergencyPendingCount } from '../services/radioshaqApi';
import { playEmergencyAlertSound, showEmergencyBrowserNotification } from '../features/emergency/emergencyAlerts';

const GLOBAL_POLL_INTERVAL_MS = 15_000;

/** Polls pending emergency count globally; when it goes from 0 to >0, plays alert sound and shows browser notification. */
export function EmergencyNotifier() {
  const prevCountRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const { count } = await getEmergencyPendingCount();
        if (cancelled) return;
        const prev = prevCountRef.current;
        prevCountRef.current = count;
        if (prev !== null && count > 0 && prev === 0) {
          playEmergencyAlertSound();
          showEmergencyBrowserNotification(count);
        }
      } catch {
        /* ignore (e.g. no auth) */
      }
    };

    const t = setTimeout(() => {
      poll();
    }, 2000);
    const interval = setInterval(poll, GLOBAL_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearTimeout(t);
      clearInterval(interval);
    };
  }, []);

  return null;
}
