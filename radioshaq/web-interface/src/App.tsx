import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useMemo, useState } from 'react';
import { Layout } from './components/Layout';
import { LicenseGate } from './components/LicenseGate';
import { AudioConfigPage } from './features/audio/AudioConfigPage';
import { CallsignsPage } from './features/callsigns/CallsignsPage';
import { MessagesPage } from './features/messages/MessagesPage';
import { TranscriptsPage } from './features/transcripts/TranscriptsPage';
import { RadioPage } from './features/radio/RadioPage';
import { SettingsPage } from './features/settings/SettingsPage';

const LICENSE_ACCEPTANCE_KEY = 'radioshaq_license_acceptance_v1';

function App() {
  const defaultAccepted = useMemo(
    () => window.localStorage.getItem(LICENSE_ACCEPTANCE_KEY) === 'accepted',
    [],
  );
  const [accepted, setAccepted] = useState(defaultAccepted);

  if (!accepted) {
    return (
      <LicenseGate
        onAccept={() => {
          window.localStorage.setItem(LICENSE_ACCEPTANCE_KEY, 'accepted');
          setAccepted(true);
        }}
      />
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<AudioConfigPage />} />
          <Route path="callsigns" element={<CallsignsPage />} />
          <Route path="messages" element={<MessagesPage />} />
          <Route path="transcripts" element={<TranscriptsPage />} />
          <Route path="radio" element={<RadioPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
