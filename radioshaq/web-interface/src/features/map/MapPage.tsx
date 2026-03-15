import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  getOperatorLocation,
  getOperatorsNearby,
  listEmergencyEventsWithLocation,
  type OperatorLocation,
  type EmergencyEventLocation,
} from '../../services/radioshaqApi';
import { OperatorMap, type OperatorMapMarker } from '../../components/maps/OperatorMap';
import {
  getMapProvider,
  setMapProvider,
  getDefaultMapCenter,
  getDefaultMapRadiusMeters,
  getMapSources,
  getActiveMapSourceId,
  type MapProvider,
} from '../../maps/mapSourceConfig';
import { isGoogleMapsConfigured } from '../../maps/googleMapsLoader';
import { escapeHtml } from '../../utils/escapeHtml';

const RADII_KM = [10, 50, 200, 1000] as const;

function radiusKmFromMeters(m: number): number {
  const km = m / 1000;
  return RADII_KM.find((r) => r >= km) ?? 50;
}

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

export function MapPage() {
  const { t } = useTranslation();
  const defaultCenter = getDefaultMapCenter();
  const defaultRadiusM = getDefaultMapRadiusMeters();
  const [provider, setProviderState] = useState<MapProvider>(getMapProvider);
  const [center, setCenter] = useState(defaultCenter);
  const [radiusKm, setRadiusKm] = useState(radiusKmFromMeters(defaultRadiusM));
  const [markers, setMarkers] = useState<OperatorMapMarker[]>([]);
  const [emergencyMarkers, setEmergencyMarkers] = useState<OperatorMapMarker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [callsignSearch, setCallsignSearch] = useState('');
  const [searching, setSearching] = useState(false);
  const [tileSourceId, setTileSourceId] = useState<string>(getActiveMapSourceId);

  const handleProviderChange = (p: MapProvider) => {
    setMapProvider(p);
    setProviderState(p);
  };

  const mapSources = getMapSources();
  const showTileSwitcher = provider === 'osm' && mapSources.length > 1;
  const googleConfigured = isGoogleMapsConfigured();
  const showGoogleWarning = provider === 'google' && !googleConfigured;

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

  useEffect(() => {
    listEmergencyEventsWithLocation({ limit: 50 })
      .then((r) => setEmergencyMarkers(r.events.map(emergencyToMarker)))
      .catch(() => setEmergencyMarkers([]));
  }, []);

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

  return (
    <div className="map-page">
      <h1>{t('map.title')}</h1>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.75rem',
          alignItems: 'center',
          marginBottom: '0.75rem',
        }}
      >
        <span style={{ fontSize: '0.9rem', color: '#666' }}>{t('map.provider')}:</span>
        <select
          value={provider}
          onChange={(e) => handleProviderChange(e.target.value as MapProvider)}
          style={{ padding: '0.35rem 0.5rem' }}
          aria-label={t('map.provider')}
        >
          <option value="osm">OpenStreetMap</option>
          <option value="google">Google Maps</option>
        </select>
        {showTileSwitcher && (
          <>
            <span style={{ fontSize: '0.9rem', color: '#666' }}>{t('map.tileSource')}:</span>
            <select
              value={tileSourceId}
              onChange={(e) => setTileSourceId(e.target.value)}
              style={{ padding: '0.35rem 0.5rem' }}
              aria-label={t('map.tileSource')}
            >
              {mapSources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </>
        )}
      </div>

      {showGoogleWarning && (
        <p role="alert" style={{ color: '#c62828', marginBottom: '1rem' }}>
          {t('map.notConfigured')} {t('map.switchToOsm')}
        </p>
      )}
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

      {!showGoogleWarning && (
        <OperatorMap
          center={center}
          zoom={radiusKm >= 200 ? 5 : radiusKm >= 50 ? 7 : 9}
          markers={[...markers, ...emergencyMarkers]}
          height={500}
          tileSourceId={provider === 'osm' ? tileSourceId : undefined}
        />
      )}
      <p style={{ marginTop: '0.75rem', fontSize: '0.9rem', color: '#666' }}>
        {t('map.operatorCount', { count: markers.length })}
        {emergencyMarkers.length > 0 && ` · ${emergencyMarkers.length} emergency events`}
      </p>
    </div>
  );
}
