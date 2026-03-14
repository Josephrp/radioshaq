/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RADIOSHAQ_API: string;
  readonly VITE_RADIOSHAQ_TOKEN: string;
  readonly VITE_GOOGLE_MAPS_API_KEY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
