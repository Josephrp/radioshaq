import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  getOperatorLocation,
  getOperatorsNearby,
  setOperatorLocation,
  type OperatorLocation,
} from '../../services/radioshaqApi';
import { escapeHtml } from '../../utils/escapeHtml';
import { OperatorMap, type OperatorMapMarker } from './OperatorMap';
import { getDefaultMapCenter } from '../../maps/mapSourceConfig';

const DEFAULT_CENTER = getDefaultMapCenter();
const FIELD_RADIUS_METERS = 100000;

function operatorToMarker(op: OperatorLocation, index: number): OperatorMapMarker {
  const dist =
    op.distance_meters != null
      ? `${(op.distance_meters / 1000).toFixed(1)} km`
      : '';
  const lastSeen = op.last_seen_at ?? op.timestamp ?? '—';
  return {
    id: `op-${op.id ?? index}-${op.callsign}`,
    position: { lat: op.latitude, lng: op.longitude },
    label: op.callsign,
    infoHtml: `
      <div style="padding:4px;min-width:140px">
        <strong>${escapeHtml(op.callsign)}</strong>
        ${dist ? `<br/><span style="font-size:12px;color:#666">${escapeHtml(dist)}</span>` : ''}
        <br/><span style="font-size:11px;color:#888">Last seen: ${escapeHtml(String(lastSeen))}</span>
      </div>
    `,
  };
}

export interface FieldMapPanelProps {
  /** Station callsign to center on and to update location for. If not set, user can type it. */
  stationCallsign?: string | null;
  /** Height of the map area */
  height?: number | string;
}

export function FieldMapPanel({ stationCallsign: propCallsign, height = 360 }: FieldMapPanelProps) {
  const { t } = useTranslation();
  const [stationCallsign, setStationCallsign] = useState(propCallsign ?? '');
  const [center, setCenter] = useState(DEFAULT_CENTER);
  const [markers, setMarkers] = useState<OperatorMapMarker[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updateLat, setUpdateLat] = useState('');
  const [updateLng, setUpdateLng] = useState('');
  const [updating, setUpdating] = useState(false);
  const [updateSuccess, setUpdateSuccess] = useState(false);

  const effectiveCallsign = (propCallsign ?? stationCallsign).trim().toUpperCase() || null;

  const fetchForCallsign = useCallback(
    async (callsign: string) => {
      if (!callsign) return;
      setLoading(true);
      setError(null);
      try {
        const loc = await getOperatorLocation(callsign);
        setCenter({ lat: loc.latitude, lng: loc.longitude });
        const res = await getOperatorsNearby({
          latitude: loc.latitude,
          longitude: loc.longitude,
          radius_meters: FIELD_RADIUS_METERS,
          recent_hours: 168,
          max_results: 100,
        });
        const stationMarker: OperatorMapMarker = {
          id: `station-${loc.callsign}`,
          position: { lat: loc.latitude, lng: loc.longitude },
          label: loc.callsign,
          infoHtml: `<div style="padding:4px"><strong>${escapeHtml(loc.callsign)}</strong> (this station)</div>`,
        };
        const others = res.operators
          .filter((o) => (o as OperatorLocation).callsign !== callsign && o.latitude != null && o.longitude != null)
          .map((o, i) => operatorToMarker(o as OperatorLocation, i));
        setMarkers([stationMarker, ...others]);
      } catch (e) {
        setError(e instanceof Error ? e.message : t('common.failedToLoad'));
        setMarkers([]);
      } finally {
        setLoading(false);
      }
    },
    [t]
  );

  useEffect(() => {
    if (effectiveCallsign) fetchForCallsign(effectiveCallsign);
    else setMarkers([]);
  }, [effectiveCallsign, fetchForCallsign]);

  const handleUpdateLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    const cs = effectiveCallsign ?? (propCallsign ?? stationCallsign).trim().toUpperCase();
    if (!cs) {
      setError('Enter a callsign to update location.');
      return;
    }
    const lat = parseFloat(updateLat);
    const lng = parseFloat(updateLng);
    if (Number.isNaN(lat) || lat < -90 || lat > 90) {
      setError('Latitude must be between -90 and 90.');
      return;
    }
    if (Number.isNaN(lng) || lng < -180 || lng > 180) {
      setError('Longitude must be between -180 and 180.');
      return;
    }
    setUpdating(true);
    setError(null);
    setUpdateSuccess(false);
    try {
      await setOperatorLocation({ callsign: cs, latitude: lat, longitude: lng });
      setUpdateSuccess(true);
      setCenter({ lat, lng });
      await fetchForCallsign(cs);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failed'));
    } finally {
      setUpdating(false);
    }
  };

  return (
    <section style={{ marginTop: '1.5rem', padding: '1rem', border: '1px solid #ddd', borderRadius: 8 }}>
      <h2 style={{ marginTop: 0 }}>{t('map.fieldMapTitle')}</h2>
      {error && (
        <p role="alert" style={{ color: 'crimson', fontSize: '0.9rem' }}>
          {error}
        </p>
      )}
      {updateSuccess && (
        <p style={{ color: '#2e7d32', fontSize: '0.9rem' }}>{t('map.locationUpdated')}</p>
      )}

      {!propCallsign && (
        <div style={{ marginBottom: '0.75rem' }}>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>
            {t('map.stationCallsign')}
          </label>
          <input
            type="text"
            value={stationCallsign}
            onChange={(e) => setStationCallsign(e.target.value)}
            placeholder="e.g. K5ABC"
            maxLength={10}
            style={{ padding: '0.4rem', width: 120 }}
          />
        </div>
      )}

      <OperatorMap center={center} zoom={8} markers={markers} height={height} />
      {loading && <p style={{ fontSize: '0.85rem', color: '#666' }}>{t('common.loading')}</p>}

      <form
        onSubmit={handleUpdateLocation}
        style={{
          marginTop: '0.75rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.5rem',
          alignItems: 'flex-end',
        }}
      >
        <label style={{ fontSize: '0.9rem' }}>
          {t('map.lat')}
          <input
            type="text"
            value={updateLat}
            onChange={(e) => setUpdateLat(e.target.value)}
            placeholder="e.g. 40.71"
            style={{ display: 'block', marginTop: 2, padding: '0.35rem', width: 100 }}
          />
        </label>
        <label style={{ fontSize: '0.9rem' }}>
          {t('map.lng')}
          <input
            type="text"
            value={updateLng}
            onChange={(e) => setUpdateLng(e.target.value)}
            placeholder="e.g. -74.00"
            style={{ display: 'block', marginTop: 2, padding: '0.35rem', width: 100 }}
          />
        </label>
        <button type="submit" disabled={updating || !effectiveCallsign}>
          {updating ? t('common.loading') : t('map.updateLocation')}
        </button>
      </form>
    </section>
  );
}
