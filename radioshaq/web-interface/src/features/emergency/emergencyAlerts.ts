/** Module-level AudioContext created on user gesture; kept alive for alert sounds. */
let _ctx: AudioContext | null = null;

/**
 * Create (and resume) the AudioContext during a user gesture (e.g. "Enable alerts" click).
 * Must be called before playEmergencyAlertSound() or the sound will not play (browser autoplay policy).
 */
export function initAudioContext(): void {
  if (_ctx) return;
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    _ctx = new Ctx();
  } catch {
    /* ignore */
  }
}

/**
 * Request browser notification permission. Call during a user gesture (e.g. "Enable alerts" click).
 * Until permission is granted, showEmergencyBrowserNotification is a no-op.
 */
export async function requestNotificationPermission(): Promise<void> {
  if (typeof window === 'undefined' || !('Notification' in window)) return;
  if (Notification.permission === 'default') {
    await Notification.requestPermission();
  }
}

/**
 * Play the emergency alert tone. Uses the AudioContext from initAudioContext().
 * If initAudioContext() was never called (no user gesture), the sound is silently skipped.
 */
export async function playEmergencyAlertSound(): Promise<void> {
  const ctx = _ctx;
  if (!ctx) return;
  try {
    if (ctx.state === 'suspended') {
      await ctx.resume();
    }
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    osc.type = 'sine';
    gain.gain.setValueAtTime(0.2, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.frequency.value = 880;
    osc2.type = 'sine';
    gain2.gain.setValueAtTime(0.2, ctx.currentTime + 0.4);
    gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.7);
    osc2.start(ctx.currentTime + 0.4);
    osc2.stop(ctx.currentTime + 0.7);
  } catch {
    /* ignore */
  }
}

export function showEmergencyBrowserNotification(count: number): void {
  if (typeof window === 'undefined' || !('Notification' in window)) return;
  if (Notification.permission === 'granted') {
    new Notification('RadioShaq – Emergency', {
      body: count === 1 ? '1 pending emergency message requires your action.' : `${count} pending emergency messages require your action.`,
      tag: 'radioshaq-emergency',
      requireInteraction: true,
    });
  }
}
