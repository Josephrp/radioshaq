import React, { useEffect, useState } from 'react';
import { connectMetricsWebSocket } from '../../services/shakodsApi';
import type { AudioMetrics } from '../../types/audio';

interface VADVisualizerProps {
  sessionId: string;
  websocketUrl?: string;
}

export function VADVisualizer({ sessionId }: VADVisualizerProps) {
  const [metrics, setMetrics] = useState<AudioMetrics | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = connectMetricsWebSocket(sessionId);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AudioMetrics;
        setMetrics(data);
      } catch {
        // ignore
      }
    };
    return () => ws.close();
  }, [sessionId]);

  return (
    <div className="vad-visualizer" aria-live="polite">
      <div className="vad-status">
        WebSocket: {connected ? 'connected' : 'disconnected'}
      </div>
      {metrics && (
        <div className="vad-metrics">
          <span>VAD: {metrics.vad_active ? 'active' : 'idle'}</span>
          {metrics.snr_db != null && <span>SNR: {metrics.snr_db.toFixed(1)} dB</span>}
          {metrics.state && <span>State: {metrics.state}</span>}
        </div>
      )}
    </div>
  );
}
