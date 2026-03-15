/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RADIOSHAQ_API: string;
  readonly VITE_GOOGLE_MAPS_API_KEY: string;
  readonly VITE_MAP_PROVIDER?: string;
  readonly VITE_MAP_SOURCE?: string;
  readonly VITE_DEFAULT_MAP_CENTER_LAT?: string;
  readonly VITE_DEFAULT_MAP_CENTER_LON?: string;
  readonly VITE_DEFAULT_MAP_ZOOM?: string;
  readonly VITE_DEFAULT_MAP_RADIUS_METERS?: string;
  readonly VITE_MAP_SOURCES?: string;
  readonly VITE_MAP_TILE_URL?: string;
  readonly VITE_MAP_TILE_ATTRIBUTION?: string;
  readonly VITE_MAP_TILE_SUBDOMAINS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
