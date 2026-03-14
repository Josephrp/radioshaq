/**
 * Load Google Maps JavaScript API for use in React components.
 * Requires VITE_GOOGLE_MAPS_API_KEY to be set in the environment.
 */

import { setOptions, importLibrary } from '@googlemaps/js-api-loader';

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

let loadPromise: Promise<typeof google> | null = null;

/**
 * Load the Google Maps JavaScript API once. Resolves with the global `google` namespace.
 */
export function loadGoogleMaps(): Promise<typeof google> {
  if (loadPromise) return loadPromise;
  if (!API_KEY || API_KEY.trim() === '') {
    return Promise.reject(new Error('VITE_GOOGLE_MAPS_API_KEY is not set. Set it in .env or .env.local for map features.'));
  }
  setOptions({ key: API_KEY, v: 'weekly' });
  loadPromise = importLibrary('maps').then(() => (globalThis as unknown as { google: typeof google }).google);
  return loadPromise;
}

/**
 * Return whether the Maps API key is configured (does not load the script).
 */
export function isGoogleMapsConfigured(): boolean {
  return Boolean(API_KEY && API_KEY.trim() !== '');
}
