import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import DOMPurify from 'dompurify';
import { getTileLayerProps } from '../../maps/mapSourceConfig';
import type { OperatorMapProps } from './OperatorMap';

const DEFAULT_HEIGHT = 480;

function ChangeView({ center, zoom }: { center: { lat: number; lng: number }; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([center.lat, center.lng], zoom);
  }, [map, center.lat, center.lng, zoom]);
  return null;
}

const defaultIcon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

/**
 * Leaflet-based OperatorMap for OSM provider. Uses tile layer from mapSourceConfig.
 */
export function OperatorMapLeaflet({
  center,
  zoom,
  markers,
  height = DEFAULT_HEIGHT,
  className = '',
  tileSourceId,
}: OperatorMapProps) {
  const tileProps = useMemo(() => getTileLayerProps(tileSourceId), [tileSourceId]);
  const heightStyle = typeof height === 'number' ? `${height}px` : height;

  return (
    <div
      className={className}
      style={{
        width: '100%',
        height: heightStyle,
        minHeight: 200,
        position: 'relative',
      }}
      aria-label="Operator locations map"
    >
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={zoom}
        style={{ width: '100%', height: '100%', minHeight: 200 }}
        scrollWheelZoom
      >
        <ChangeView center={center} zoom={zoom} />
        <TileLayer
          url={tileProps.url}
          attribution={tileProps.attribution}
          subdomains={tileProps.subdomains}
          minZoom={tileProps.minZoom}
          maxZoom={tileProps.maxZoom}
        />
        {markers.map((m) => (
          <Marker
            key={m.id}
            position={[m.position.lat, m.position.lng]}
            icon={defaultIcon}
          >
            <Popup>
              {m.infoHtml ? (
                <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.infoHtml) }} />
              ) : (
                <span>{m.label ?? m.id}</span>
              )}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
