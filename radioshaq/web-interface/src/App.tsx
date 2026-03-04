import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AudioConfigPage } from './features/audio/AudioConfigPage';
import { CallsignsPage } from './features/callsigns/CallsignsPage';
import { MessagesPage } from './features/messages/MessagesPage';
import { TranscriptsPage } from './features/transcripts/TranscriptsPage';
import { RadioPage } from './features/radio/RadioPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<AudioConfigPage />} />
          <Route path="callsigns" element={<CallsignsPage />} />
          <Route path="messages" element={<MessagesPage />} />
          <Route path="transcripts" element={<TranscriptsPage />} />
          <Route path="radio" element={<RadioPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
