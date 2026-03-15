import './i18n';
import 'leaflet/dist/leaflet.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

if (import.meta.env.VITE_SHAKODS_API != null || import.meta.env.VITE_SHAKODS_TOKEN != null) {
  console.warn(
    'Deprecated: VITE_SHAKODS_API and VITE_SHAKODS_TOKEN are no longer used. Use VITE_RADIOSHAQ_API and runtime token login (/auth/token) instead.'
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
