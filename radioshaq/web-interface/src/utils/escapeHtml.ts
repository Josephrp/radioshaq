/**
 * Escapes a string for safe interpolation into HTML to prevent XSS.
 * Use for any API- or user-supplied values that are embedded in raw HTML
 * (e.g. google.maps.InfoWindow.setContent()).
 */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
