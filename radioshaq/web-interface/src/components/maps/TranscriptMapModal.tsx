import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getOperatorLocation, type OperatorLocation } from '../../services/radioshaqApi';
import { escapeHtml } from '../../utils/escapeHtml';
import { OperatorMap, type OperatorMapMarker } from './OperatorMap';
import { getDefaultMapCenter } from '../../maps/mapSourceConfig';
import type { TranscriptItem } from '../../services/radioshaqApi';

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export interface TranscriptMapModalProps {
  transcript: TranscriptItem | null;
  onClose: () => void;
}

export function TranscriptMapModal({ transcript, onClose }: TranscriptMapModalProps) {
  const { t } = useTranslation();
  const [markers, setMarkers] = useState<OperatorMapMarker[]>([]);
  const [center, setCenter] = useState(getDefaultMapCenter);
  const [zoom, setZoom] = useState(4);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [distanceKm, setDistanceKm] = useState<number | null>(null);

  const fetchLocations = useCallback(async (src: string, dest: string | undefined) => {
    setLoading(true);
    setError(null);
    setMarkers([]);
    setDistanceKm(null);
    try {
      const callsigns = dest && dest !== src ? [src, dest] : [src];
      const locations: { callsign: string; loc: OperatorLocation }[] = [];
      for (const cs of callsigns) {
        try {
          const loc = await getOperatorLocation(cs);
          locations.push({ callsign: cs, loc });
        } catch {
          // skip if location not found for this callsign
        }
      }
      if (locations.length === 0) {
        setError(t('map.noLocationsForCallsigns'));
        return;
      }
      const ms: OperatorMapMarker[] = locations.map(({ callsign, loc }, i) => ({
        id: `tx-${callsign}-${i}`,
        position: { lat: loc.latitude, lng: loc.longitude },
        label: callsign,
        infoHtml: `<div style="padding:4px"><strong>${escapeHtml(callsign)}</strong></div>`,
      }));
      setMarkers(ms);

      const lat1 = locations[0].loc.latitude;
      const lon1 = locations[0].loc.longitude;
      if (locations.length === 2) {
        const lat2 = locations[1].loc.latitude;
        const lon2 = locations[1].loc.longitude;
        setDistanceKm(haversineKm(lat1, lon1, lat2, lon2));
        setCenter({
          lat: (lat1 + lat2) / 2,
          lng: (lon1 + lon2) / 2,
        });
        setZoom(5);
      } else {
        setCenter({ lat: lat1, lng: lon1 });
        setZoom(8);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.failedToLoad'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (!transcript) return;
    const src = (transcript.source_callsign ?? '').trim().toUpperCase();
    const dest = (transcript.destination_callsign ?? '').trim().toUpperCase() || undefined;
    if (!src) {
      setError(t('map.noSourceCallsign'));
      setLoading(false);
      return;
    }
    fetchLocations(src, dest);
  }, [transcript, fetchLocations]);

  if (!transcript) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('map.viewOnMap')}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 8,
          maxWidth: '90vw',
          maxHeight: '90vh',
          width: 640,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>{t('map.viewOnMap')}</h2>
          <button type="button" onClick={onClose} style={{ padding: '0.35rem 0.75rem' }}>
            {t('common.cancel')}
          </button>
        </div>
        {loading && <p style={{ padding: '1rem', margin: 0 }}>{t('common.loading')}</p>}
        {error && <p role="alert" style={{ padding: '0.75rem 1rem', margin: 0, color: 'crimson' }}>{error}</p>}
        {distanceKm != null && (
          <p style={{ padding: '0 1rem', margin: 0, fontSize: '0.9rem', color: '#666' }}>
            {t('map.distanceKm', { km: distanceKm.toFixed(1) })}
          </p>
        )}
        {!loading && markers.length > 0 && (
          <div style={{ flex: 1, minHeight: 320 }}>
            <OperatorMap center={center} zoom={zoom} markers={markers} height={320} />
          </div>
        )}
      </div>
    </div>
  );
}
