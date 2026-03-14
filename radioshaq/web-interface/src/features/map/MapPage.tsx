import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  getOperatorLocation,
  getOperatorsNearby,
  type OperatorLocation,
} from '../../services/radioshaqApi';
import { OperatorMap, type OperatorMapMarker } from '../../components/maps/OperatorMap';
import { isGoogleMapsConfigured } from '../../maps/googleMapsLoader';

const DEFAULT_CENTER = { lat: 39.8283, lng: -98.5795 };
const RADII_KM = [10, 50, 200, 1000] as const;
const DEFAULT_RADIUS_KM = 50;

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
        <strong>${op.callsign}</strong>
        ${dist ? `<br/><span style="font-size:12px;color:#666">${dist}</span>` : ''}
        <br/><span style="font-size:11px;color:#888">Last seen: ${lastSeen}</span>
      </div>
    `,
  };
}

export function MapPage() {
  const { t } = useTranslation();
  const [center, setCenter] = useState(DEFAULT_CENTER);
  const [radiusKm, setRadiusKm] = useState(DEFAULT_RADIUS_KM);
  const [markers, setMarkers] = useState<OperatorMapMarker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [callsignSearch, setCallsignSearch] = useState('');
  const [searching, setSearching] = useState(false);

  const fetchNearby = useCallback(async (lat: number, lng: number, radiusMeters: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getOperatorsNearby({
        latitude: lat,
        longitude: lng,
        radius_meters: radiusMeters,
        recent_hours: 168,
        max_results: 200,
      });
      setCenter({ lat: res.latitude, lng: res.longitude });
      setMarkers(
        res.operators
          .filter((o) => o.latitude != null && o.longitude != null)
          .map((o, i) => operatorToMarker(o as OperatorLocation, i))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToLoad'));
      setMarkers([]);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchNearby(center.lat, center.lng, radiusKm * 1000);
  }, [radiusKm]);

  const handleCenterOnCallsign = async (e: React.FormEvent) => {
    e.preventDefault();
    const cs = callsignSearch.trim().toUpperCase();
    if (!cs) return;
    setSearching(true);
    setError(null);
    try {
      const loc = await getOperatorLocation(cs);
      setCenter({ lat: loc.latitude, lng: loc.longitude });
      await fetchNearby(loc.latitude, loc.longitude, radiusKm * 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToLoad'));
    } finally {
      setSearching(false);
    }
  };

  const handleRadiusChange = (km: number) => {
    setRadiusKm(km);
  };

  if (!isGoogleMapsConfigured()) {
    return (
      <div>
        <h1>{t('map.title')}</h1>
        <p style={{ color: '#666' }}>{t('map.notConfigured')}</p>
      </div>
    );
  }

  return (
    <div className="map-page">
      <h1>{t('map.title')}</h1>
      {error && (
        <p role="alert" style={{ color: 'crimson' }}>
          {error}
        </p>
      )}

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.75rem',
          alignItems: 'center',
          marginBottom: '1rem',
        }}
      >
        <form
          onSubmit={handleCenterOnCallsign}
          style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}
        >
          <input
            type="text"
            value={callsignSearch}
            onChange={(e) => setCallsignSearch(e.target.value)}
            placeholder={t('map.callsignPlaceholder')}
            maxLength={10}
            style={{ padding: '0.4rem', width: 100 }}
            aria-label={t('map.centerOnCallsign')}
          />
          <button type="submit" disabled={searching}>
            {searching ? t('common.loading') : t('map.centerOnCallsign')}
          </button>
        </form>
        <span style={{ fontSize: '0.9rem', color: '#666' }}>{t('map.radius')}:</span>
        <select
          value={radiusKm}
          onChange={(e) => handleRadiusChange(Number(e.target.value))}
          style={{ padding: '0.35rem 0.5rem' }}
          aria-label={t('map.radius')}
        >
          {RADII_KM.map((km) => (
            <option key={km} value={km}>
              {km === 1000 ? t('map.radiusWorld') : `${km} km`}
            </option>
          ))}
        </select>
        {loading && <span style={{ fontSize: '0.9rem', color: '#666' }}>{t('common.loading')}</span>}
      </div>

      <OperatorMap
        center={center}
        zoom={radiusKm >= 200 ? 5 : radiusKm >= 50 ? 7 : 9}
        markers={markers}
        height={500}
      />
      <p style={{ marginTop: '0.75rem', fontSize: '0.9rem', color: '#666' }}>
        {t('map.operatorCount', { count: markers.length })}
      </p>
    </div>
  );
}
