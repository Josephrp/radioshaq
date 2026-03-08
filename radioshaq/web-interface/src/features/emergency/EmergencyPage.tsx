import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  getEmergencyPendingCount,
  listEmergencyEvents,
  approveEmergencyEvent,
  rejectEmergencyEvent,
  type EmergencyEvent as EmergencyEventType,
} from '../../services/radioshaqApi';

const POLL_INTERVAL_MS = 12_000;

export function EmergencyPage() {
  const { t } = useTranslation();
  const [events, setEvents] = useState<EmergencyEventType[]>([]);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const load = useCallback(async () => {
    try {
      const [countRes, listRes] = await Promise.all([
        getEmergencyPendingCount(),
        listEmergencyEvents('pending'),
      ]);
      const count = countRes.count;
      setPendingCount(count);
      setEvents(listRes.events ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToLoad'));
      setEvents([]);
      setPendingCount(0);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const handleApprove = async (eventId: number) => {
    setActionLoading(eventId);
    try {
      await approveEmergencyEvent(eventId, notes[eventId]);
      setNotes((prev) => ({ ...prev, [eventId]: '' }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToUpdate'));
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (eventId: number) => {
    setActionLoading(eventId);
    try {
      await rejectEmergencyEvent(eventId, notes[eventId]);
      setNotes((prev) => ({ ...prev, [eventId]: '' }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToUpdate'));
    } finally {
      setActionLoading(null);
    }
  };

  const requestNotificationPermission = () => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  };

  if (loading && events.length === 0) {
    return <p>{t('common.loading')}</p>;
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0 }}>{t('emergency.title')}</h1>
        <span style={{ fontSize: '0.95rem', color: '#666' }}>
          {t('emergency.pendingCount', { count: pendingCount })}
        </span>
        <button type="button" onClick={load} disabled={loading} style={{ padding: '0.35rem 0.75rem' }}>
          {t('common.refresh')}
        </button>
        <button type="button" onClick={requestNotificationPermission} style={{ padding: '0.35rem 0.75rem', fontSize: '0.9rem' }}>
          {t('emergency.allowNotifications')}
        </button>
      </div>

      {error && (
        <div style={{ padding: '0.5rem 0.75rem', background: '#ffebee', color: '#c62828', borderRadius: 4, marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <p style={{ color: '#555', marginBottom: '1rem' }}>{t('emergency.intro')}</p>

      {events.length === 0 ? (
        <p style={{ color: '#666' }}>{t('emergency.noPending')}</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {events.map((ev) => {
            const id = ev.id ?? 0;
            const extra = ev.extra_data ?? {};
            const phone = extra.emergency_contact_phone ?? '—';
            const channel = extra.emergency_contact_channel ?? '—';
            const message = extra.message ?? ev.notes ?? '—';
            const loadingEv = actionLoading === id;

            return (
              <li
                key={id}
                style={{
                  border: '1px solid #ccc',
                  borderRadius: 8,
                  padding: '1rem',
                  marginBottom: '1rem',
                  background: '#fafafa',
                }}
              >
                <div style={{ marginBottom: '0.5rem' }}>
                  <strong>#{id}</strong> {ev.initiator_callsign ?? '—'} → {ev.target_callsign ?? '—'}
                </div>
                <div style={{ marginBottom: '0.5rem', fontSize: '0.95rem' }}>
                  {t('emergency.contact')}: {phone} ({channel})
                </div>
                <div style={{ marginBottom: '0.75rem', whiteSpace: 'pre-wrap', background: '#fff', padding: '0.5rem', borderRadius: 4 }}>
                  {message}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'flex-end' }}>
                  <input
                    type="text"
                    placeholder={t('emergency.notesPlaceholder')}
                    value={notes[id] ?? ''}
                    onChange={(e) => setNotes((p) => ({ ...p, [id]: e.target.value }))}
                    style={{ padding: '0.35rem 0.5rem', width: 200, maxWidth: '100%' }}
                  />
                  <button
                    type="button"
                    onClick={() => handleApprove(id)}
                    disabled={loadingEv}
                    style={{ padding: '0.35rem 0.75rem', background: '#2e7d32', color: '#fff', border: 'none', borderRadius: 4 }}
                  >
                    {loadingEv ? t('common.loading') : t('emergency.approve')}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleReject(id)}
                    disabled={loadingEv}
                    style={{ padding: '0.35rem 0.75rem', background: '#c62828', color: '#fff', border: 'none', borderRadius: 4 }}
                  >
                    {loadingEv ? t('common.loading') : t('emergency.reject')}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p style={{ marginTop: '1.5rem', fontSize: '0.9rem', color: '#666' }}>
        {t('emergency.autoRefresh')}
      </p>
    </div>
  );
}
