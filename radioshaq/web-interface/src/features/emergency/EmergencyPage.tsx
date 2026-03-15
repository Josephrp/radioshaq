import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  getEmergencyPendingCount,
  listEmergencyEvents,
  listEmergencyEventsWithLocation,
  approveEmergencyEvent,
  rejectEmergencyEvent,
  type EmergencyEvent as EmergencyEventType,
  type EmergencyEventLocation,
} from '../../services/radioshaqApi';
import { OperatorMap, type OperatorMapMarker } from '../../components/maps/OperatorMap';
import { getDefaultMapCenter } from '../../maps/mapSourceConfig';
import { escapeHtml } from '../../utils/escapeHtml';

const POLL_INTERVAL_MS = 12_000;

function emergencyToMarker(ev: EmergencyEventLocation): OperatorMapMarker {
  return {
    id: `ev-${ev.id}`,
    position: { lat: ev.latitude, lng: ev.longitude },
    label: ev.initiator_callsign ?? `#${ev.id}`,
    color: ev.status === 'pending' ? '#c62828' : ev.status === 'approved' ? '#2e7d32' : '#666',
    infoHtml: `
      <div style="padding:4px;min-width:140px">
        <strong>${escapeHtml(ev.initiator_callsign ?? '')}</strong> → ${escapeHtml(ev.target_callsign ?? '—')}
        <br/><span style="font-size:11px;color:#888">${escapeHtml(ev.status ?? '')} · ${escapeHtml(ev.created_at ?? '')}</span>
      </div>
    `,
  };
}

export function EmergencyPage() {
  const { t } = useTranslation();
  const [events, setEvents] = useState<EmergencyEventType[]>([]);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoadingSet, setActionLoadingSet] = useState<Set<number>>(new Set());
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [emergencyMapMarkers, setEmergencyMapMarkers] = useState<OperatorMapMarker[]>([]);
  const [emergencyMapCenter, setEmergencyMapCenter] = useState(getDefaultMapCenter);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

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

  useEffect(() => {
    listEmergencyEventsWithLocation({ limit: 50 })
      .then((r) => setEmergencyMapMarkers(r.events.map(emergencyToMarker)))
      .catch(() => setEmergencyMapMarkers([]));
  }, []);

  const focusMapOnEvent = (eventId: number) => {
    const marker = emergencyMapMarkers.find((m) => m.id === `ev-${eventId}`);
    if (marker) {
      setSelectedEventId(eventId);
      setEmergencyMapCenter(marker.position);
    }
  };

  const handleApprove = async (eventId: number) => {
    setActionLoadingSet((prev) => {
      const next = new Set(prev);
      next.add(eventId);
      return next;
    });
    try {
      await approveEmergencyEvent(eventId, notes[eventId]);
      setNotes((prev) => ({ ...prev, [eventId]: '' }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToUpdate'));
    } finally {
      setActionLoadingSet((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }
  };

  const handleReject = async (eventId: number) => {
    setActionLoadingSet((prev) => {
      const next = new Set(prev);
      next.add(eventId);
      return next;
    });
    try {
      await rejectEmergencyEvent(eventId, notes[eventId]);
      setNotes((prev) => ({ ...prev, [eventId]: '' }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToUpdate'));
    } finally {
      setActionLoadingSet((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }
  };

  const requestNotificationPermission = async () => {
    if ('Notification' in window && Notification.permission === 'default') {
      void Notification.requestPermission();
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

      {emergencyMapMarkers.length > 0 && (
        <section style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid #ddd', borderRadius: 8 }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>{t('emergency.mapTitle') ?? 'Events on map'}</h2>
          <OperatorMap
            center={emergencyMapCenter}
            zoom={selectedEventId != null ? 10 : 4}
            markers={emergencyMapMarkers}
            height={320}
          />
        </section>
      )}

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
            const loadingEv = actionLoadingSet.has(id);

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
                <div style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <strong>#{id}</strong> {ev.initiator_callsign ?? '—'} → {ev.target_callsign ?? '—'}
                  {emergencyMapMarkers.some((m) => m.id === `ev-${id}`) && (
                    <button
                      type="button"
                      onClick={() => focusMapOnEvent(id)}
                      style={{ fontSize: '0.85rem', padding: '0.2rem 0.5rem' }}
                    >
                      {t('emergency.viewOnMap') ?? 'View on map'}
                    </button>
                  )}
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
