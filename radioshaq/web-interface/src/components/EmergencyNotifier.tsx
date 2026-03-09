import { useCallback, useEffect, useRef, useState } from 'react';
import { getEmergencyPendingCount } from '../services/radioshaqApi';
import {
  initAudioContext,
  playEmergencyAlertSound,
  requestNotificationPermission,
  showEmergencyBrowserNotification,
} from '../features/emergency/emergencyAlerts';

const GLOBAL_POLL_INTERVAL_MS = 15_000;

/** Polls pending emergency count globally; when it goes from 0 to >0, plays alert sound and shows browser notification. */
export function EmergencyNotifier() {
  const prevCountRef = useRef<number | null>(null);
  const [alertsEnabled, setAlertsEnabled] = useState(false);

  const enableAlerts = useCallback(async () => {
    initAudioContext();
    await requestNotificationPermission();
    setAlertsEnabled(true);
  }, []);

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

  if (alertsEnabled) return null;
  return (
    <div style={{ position: 'fixed', bottom: 8, right: 8, zIndex: 9999 }}>
      <button
        type="button"
        onClick={enableAlerts}
        className="enable-alerts-btn"
        style={{
          padding: '6px 12px',
          fontSize: '12px',
          backgroundColor: '#c53030',
          color: '#fff',
          border: 'none',
          borderRadius: 4,
          cursor: 'pointer',
        }}
      >
        Enable emergency alerts
      </button>
    </div>
  );
}
