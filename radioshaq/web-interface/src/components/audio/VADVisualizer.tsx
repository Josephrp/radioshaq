import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { connectMetricsWebSocket } from '../../services/radioshaqApi';
import type { AudioMetrics } from '../../types/audio';

const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_DELAY_MS = 15000;

interface VADVisualizerProps {
  sessionId: string;
  websocketUrl?: string;
}

export function VADVisualizer({ sessionId }: VADVisualizerProps) {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<AudioMetrics | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectDelay = useRef(RECONNECT_DELAY_MS);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let mounted = true;

    const connect = () => {
      ws = connectMetricsWebSocket(sessionId);
      ws.onopen = () => {
        if (mounted) {
          setConnected(true);
          reconnectDelay.current = RECONNECT_DELAY_MS;
        }
      };
      ws.onclose = () => {
        if (mounted) setConnected(false);
        if (!mounted) return;
        timeoutRef.current = setTimeout(() => {
          reconnectDelay.current = Math.min(
            reconnectDelay.current * 1.5,
            MAX_RECONNECT_DELAY_MS
          );
          connect();
        }, reconnectDelay.current);
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as AudioMetrics;
          if (mounted) setMetrics(data);
        } catch {
          // ignore
        }
      };
    };

    connect();
    return () => {
      mounted = false;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      ws.close();
    };
  }, [sessionId]);

  const isPlaceholder = metrics?.placeholder === true || (metrics?.type === 'heartbeat' && metrics?.state === 'idle' && metrics?.snr_db == null);

  return (
    <div className="vad-visualizer" aria-live="polite">
      <div className="vad-status">
        {t('audio.vadStatusWebSocket')}: {connected ? t('audio.vadConnected') : t('audio.vadDisconnected')}
      </div>
      {metrics && !isPlaceholder && (
        <div className="vad-metrics">
          <span>{t('audio.vadLabel')}: {metrics.vad_active ? t('audio.vadActive') : t('audio.vadIdle')}</span>
          {metrics.snr_db != null && <span>{t('audio.snrLabel')}: {metrics.snr_db.toFixed(1)} dB</span>}
          {metrics.state && <span>{t('audio.stateLabel')}: {metrics.state}</span>}
        </div>
      )}
      {metrics && isPlaceholder && (
        <div className="vad-metrics" style={{ color: '#666', fontSize: '0.9rem' }}>
          {t('audio.vadPlaceholder')}
        </div>
      )}
    </div>
  );
}
