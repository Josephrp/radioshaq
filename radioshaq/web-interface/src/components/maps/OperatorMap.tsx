import { useEffect, useRef, useCallback, useState } from 'react';

import { getMapProvider } from '../../maps/mapSourceConfig';
import { loadGoogleMaps } from '../../maps/googleMapsLoader';
import { OperatorMapLeaflet } from './OperatorMapLeaflet';

export interface OperatorMapMarker {
  id: string;
  position: { lat: number; lng: number };
  label?: string;
  subtitle?: string;
  infoHtml?: string;
  iconUrl?: string;
  color?: string;
}

export interface OperatorMapProps {
  center: { lat: number; lng: number };
  zoom: number;
  markers: OperatorMapMarker[];
  height?: number | string;
  className?: string;
  /** When provider is OSM, optional tile source id. */
  tileSourceId?: string;
}

const DEFAULT_HEIGHT = 480;

function getGoogleMarkerIcon(
  google: typeof globalThis.google,
  marker: OperatorMapMarker
): string | google.maps.Symbol | undefined {
  if (marker.iconUrl) {
    return marker.iconUrl;
  }
  if (!marker.color) {
    return undefined;
  }
  return {
    path: google.maps.SymbolPath.CIRCLE,
    scale: 8,
    fillColor: marker.color,
    fillOpacity: 0.9,
    strokeColor: '#fff',
    strokeWeight: 1.5,
  };
}

/**
 * Unified map: branches on getMapProvider(). Renders Google or Leaflet (OSM) implementation.
 */
export function OperatorMap(props: OperatorMapProps) {
  const provider = getMapProvider();
  if (provider === 'osm') {
    return <OperatorMapLeaflet {...props} />;
  }
  return <OperatorMapGoogle {...props} />;
}

/**
 * Google Maps implementation. Requires VITE_GOOGLE_MAPS_API_KEY.
 */
function OperatorMapGoogle({
  center,
  zoom,
  markers,
  height = DEFAULT_HEIGHT,
  className = '',
}: OperatorMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const infoWindowRef = useRef<google.maps.InfoWindow | null>(null);
  const centerRef = useRef(center);
  const zoomRef = useRef(zoom);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const clearMarkers = useCallback(() => {
    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];
    if (infoWindowRef.current) {
      infoWindowRef.current.close();
    }
  }, []);

  useEffect(() => {
    centerRef.current = center;
    zoomRef.current = zoom;
  }, [center, zoom]);

  useEffect(() => {
    if (!containerRef.current) return;
    setMapError(null);
    setMapReady(false);
    let cancelled = false;
    loadGoogleMaps()
      .then((google) => {
        if (cancelled || !containerRef.current) return;
        try {
          const latestCenter = centerRef.current;
          const latestZoom = zoomRef.current;
          const map = new google.maps.Map(containerRef.current, {
            center: { lat: latestCenter.lat, lng: latestCenter.lng },
            zoom: latestZoom,
            mapTypeControl: true,
            fullscreenControl: true,
            streetViewControl: true,
            zoomControl: true,
          });
          mapRef.current = map;
          infoWindowRef.current = new google.maps.InfoWindow();
          if (!cancelled) setMapReady(true);
        } catch (err) {
          if (!cancelled) {
            const message = err instanceof Error ? err.message : String(err);
            setMapError(message || 'Map failed to load.');
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const message = err?.message ?? String(err);
          setMapError(message || 'Map failed to load.');
        }
      });
    return () => {
      cancelled = true;
      clearMarkers();
      mapRef.current = null;
      infoWindowRef.current = null;
    };
  }, [clearMarkers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.setCenter({ lat: center.lat, lng: center.lng });
    map.setZoom(zoom);
  }, [center.lat, center.lng, zoom, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    clearMarkers();
    loadGoogleMaps().then((google) => {
      if (!mapRef.current || !infoWindowRef.current) return;
      markers.forEach((m) => {
        const marker = new google.maps.Marker({
          position: { lat: m.position.lat, lng: m.position.lng },
          map: mapRef.current!,
          title: m.label ?? m.id,
          label: m.label ? { text: m.label, color: '#000' } : undefined,
          icon: getGoogleMarkerIcon(google, m),
        });
        if (m.infoHtml) {
          marker.addListener('click', () => {
            infoWindowRef.current?.setContent(m.infoHtml!);
            infoWindowRef.current?.open(mapRef.current!, marker);
          });
        }
        markersRef.current.push(marker);
      });
    });
  }, [markers, clearMarkers, mapReady]);

  const heightStyle = typeof height === 'number' ? `${height}px` : height;

  return (
    <div
      className={className}
      style={{
        width: '100%',
        height: heightStyle,
        minHeight: 200,
        background: '#e8e8e8',
        position: 'relative',
      }}
      aria-label="Operator locations map"
    >
      {!mapReady && !mapError && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#666',
            fontSize: '0.95rem',
          }}
        >
          Loading map…
        </div>
      )}
      {mapError && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            padding: '1rem',
            color: '#c62828',
            fontSize: '0.9rem',
            overflow: 'auto',
            background: '#fff',
          }}
        >
          <strong>Map unavailable</strong>
          <p style={{ margin: '0.5rem 0 0 0' }}>{mapError}</p>
          <p style={{ margin: '0.5rem 0 0 0', color: '#666', fontSize: '0.85rem' }}>
            Set <code>VITE_GOOGLE_MAPS_API_KEY</code> in <code>web-interface/.env</code> and restart the dev server (<code>npm run dev</code>).
          </p>
        </div>
      )}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          display: mapError ? 'none' : 'block',
        }}
      />
    </div>
  );
}
