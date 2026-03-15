/**
 * Map provider (OSM vs Google) and tile source configuration for OSM provider.
 * Provider: getMapProvider() / setMapProvider() with localStorage + VITE_MAP_PROVIDER.
 * Tile sources: built-in OSM + optional custom via env; getTileLayerProps() for react-leaflet.
 */

export type MapProvider = 'osm' | 'google';

const STORAGE_KEY_PROVIDER = 'radioshaq_mapProvider';
const ENV_MAP_PROVIDER = import.meta.env.VITE_MAP_PROVIDER as string | undefined;
const ENV_MAP_SOURCE = import.meta.env.VITE_MAP_SOURCE as string | undefined;
const ENV_DEFAULT_LAT = Number(import.meta.env.VITE_DEFAULT_MAP_CENTER_LAT);
const ENV_DEFAULT_LON = Number(import.meta.env.VITE_DEFAULT_MAP_CENTER_LON);
const ENV_DEFAULT_ZOOM = Number(import.meta.env.VITE_DEFAULT_MAP_ZOOM);
const ENV_DEFAULT_RADIUS = Number(import.meta.env.VITE_DEFAULT_MAP_RADIUS_METERS);

export interface MapSourceConfig {
  id: string;
  name: string;
  tileUrlTemplate: string;
  attribution: string;
  subdomains?: string;
  minZoom?: number;
  maxZoom?: number;
  apiKeyEnvVar?: string;
}

const BUILTIN_SOURCES: MapSourceConfig[] = [
  {
    id: 'osm',
    name: 'OpenStreetMap',
    tileUrlTemplate: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    subdomains: 'abc',
    minZoom: 0,
    maxZoom: 19,
  },
];

function parseCustomSources(): MapSourceConfig[] {
  const raw = import.meta.env.VITE_MAP_SOURCES as string | undefined;
  if (!raw || typeof raw !== 'string') {
    const url = import.meta.env.VITE_MAP_TILE_URL as string | undefined;
    const attribution = (import.meta.env.VITE_MAP_TILE_ATTRIBUTION as string) ?? 'Map tiles';
    const subdomains = import.meta.env.VITE_MAP_TILE_SUBDOMAINS as string | undefined;
    if (url) {
      return [
        {
          id: 'custom',
          name: 'Custom',
          tileUrlTemplate: url,
          attribution,
          subdomains: subdomains ?? 'abc',
          minZoom: 0,
          maxZoom: 19,
        },
      ];
    }
    return [];
  }
  try {
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return [];
    return arr.filter(
      (s): s is MapSourceConfig =>
        s != null &&
        typeof s === 'object' &&
        typeof (s as MapSourceConfig).id === 'string' &&
        typeof (s as MapSourceConfig).tileUrlTemplate === 'string'
    );
  } catch {
    console.warn('Invalid VITE_MAP_SOURCES JSON; using built-in tile sources only.');
    return [];
  }
}

/** Get current map provider: localStorage first, then env. Default 'osm'. */
export function getMapProvider(): MapProvider {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY_PROVIDER);
    if (stored === 'osm' || stored === 'google') return stored;
  } catch {
    /* ignore */
  }
  const env = (ENV_MAP_PROVIDER ?? 'osm').toLowerCase();
  return env === 'google' ? 'google' : 'osm';
}

/** Persist map provider choice (e.g. from Settings or Map page). */
export function setMapProvider(provider: MapProvider): void {
  try {
    window.localStorage.setItem(STORAGE_KEY_PROVIDER, provider);
  } catch {
    /* ignore */
  }
}

/** All tile sources (built-in + custom). OSM provider only. */
export function getMapSources(): MapSourceConfig[] {
  const custom = parseCustomSources();
  if (custom.length) return [...BUILTIN_SOURCES, ...custom];
  return [...BUILTIN_SOURCES];
}

/** Active tile source id when provider is OSM. Env VITE_MAP_SOURCE or 'osm'. */
export function getActiveMapSourceId(): string {
  const id = (ENV_MAP_SOURCE ?? 'osm').trim();
  const sources = getMapSources();
  if (sources.some((s) => s.id === id)) return id;
  return 'osm';
}

export interface TileLayerProps {
  url: string;
  attribution: string;
  subdomains?: string;
  minZoom?: number;
  maxZoom?: number;
}

/** Props for react-leaflet TileLayer. Use when provider is OSM. */
export function getTileLayerProps(sourceId?: string): TileLayerProps {
  const id = sourceId ?? getActiveMapSourceId();
  const sources = getMapSources();
  const source = sources.find((s) => s.id === id) ?? sources[0] ?? BUILTIN_SOURCES[0]!;
  return {
    url: source.tileUrlTemplate,
    attribution: source.attribution,
    subdomains: source.subdomains,
    minZoom: source.minZoom,
    maxZoom: source.maxZoom,
  };
}

const DEFAULT_CENTER = { lat: 39.8283, lng: -98.5795 };
const DEFAULT_ZOOM = 4;
const DEFAULT_RADIUS_METERS = 50_000;

/** Default map center (env or US center). */
export function getDefaultMapCenter(): { lat: number; lng: number } {
  if (Number.isFinite(ENV_DEFAULT_LAT) && Number.isFinite(ENV_DEFAULT_LON)) {
    return { lat: ENV_DEFAULT_LAT, lng: ENV_DEFAULT_LON };
  }
  return DEFAULT_CENTER;
}

/** Default zoom level. */
export function getDefaultMapZoom(): number {
  if (Number.isFinite(ENV_DEFAULT_ZOOM) && ENV_DEFAULT_ZOOM >= 0) return ENV_DEFAULT_ZOOM;
  return DEFAULT_ZOOM;
}

/** Default radius in meters for operators-nearby. */
export function getDefaultMapRadiusMeters(): number {
  if (Number.isFinite(ENV_DEFAULT_RADIUS) && ENV_DEFAULT_RADIUS > 0) return ENV_DEFAULT_RADIUS;
  return DEFAULT_RADIUS_METERS;
}
