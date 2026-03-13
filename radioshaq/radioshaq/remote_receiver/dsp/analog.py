"""Analog demodulators for the remote SDR receiver (AM/SSB/CW-audio).

These are pragmatic, dependency-light implementations intended for demos and
field utility rather than lab-grade performance.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
try:
    from scipy import signal  # type: ignore
except Exception:  # pragma: no cover
    signal = None  # type: ignore


def _require_scipy() -> None:
    if signal is None:
        raise RuntimeError("Analog demod requires SciPy. Install project deps (scipy).")


@dataclass
class AnalogConfig:
    audio_rate_hz: int = 48_000
    audio_lpf_hz: float = 3_000.0
    audio_gain: float = 2.0
    bfo_hz: float = 1_500.0  # SSB/CW beat frequency oscillator


def _resample_to_audio(x: np.ndarray, rf_rate_hz: int, audio_rate_hz: int) -> np.ndarray:
    _require_scipy()
    if x.size == 0:
        return np.zeros(0, dtype=np.float32)
    return signal.resample_poly(x, up=int(audio_rate_hz), down=int(rf_rate_hz)).astype(np.float32)


def _lpf_audio(audio: np.ndarray, fs: int, cutoff_hz: float) -> np.ndarray:
    _require_scipy()
    if audio.size == 0:
        return audio.astype(np.float32)
    nyq = 0.5 * fs
    cutoff = min(max(200.0, float(cutoff_hz)), nyq * 0.95)
    b, a = signal.butter(4, cutoff / nyq, btype="low")
    # For block-based processing, prefer zero-phase filtering to avoid large group delay
    # that breaks simple correlation-based sanity checks.
    try:
        if audio.size > max(len(a), len(b)) * 9:
            return signal.filtfilt(b, a, audio).astype(np.float32)
    except Exception:
        pass
    return signal.lfilter(b, a, audio).astype(np.float32)


class AmDemodulator:
    """AM envelope demod (magnitude) with DC removal and audio LPF."""

    def __init__(self, cfg: AnalogConfig, rf_rate_hz: int):
        self.cfg = cfg
        self.rf_rate_hz = int(rf_rate_hz)
        self._dc: float = 0.0

    def demod(self, iq: np.ndarray) -> np.ndarray:
        x = np.asarray(iq)
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)
        if not np.iscomplexobj(x):
            x = x.astype(np.complex64)
        env = np.abs(x).astype(np.float32)
        # For AM DSB-LC, envelope is proportional to (1 + m*x). Normalize by the carrier level
        # so gain changes don't dominate and the recovered audio is centered near 0.
        self._dc = float(np.mean(env))
        dc = float(self._dc) if self._dc != 0.0 else 1e-9
        baseband = (env / dc) - 1.0
        audio = _resample_to_audio(baseband.astype(np.float32), self.rf_rate_hz, self.cfg.audio_rate_hz)
        audio = _lpf_audio(audio, self.cfg.audio_rate_hz, self.cfg.audio_lpf_hz)
        audio *= float(self.cfg.audio_gain)
        return np.clip(audio, -1.0, 1.0)


class SsbDemodulator:
    """SSB demod (baseband) with resample + audio low-pass.

    This expects complex baseband SSB IQ (analytic), matching `radioshaq.radio.analog_mod.ssb_modulate`.
    """

    def __init__(self, cfg: AnalogConfig, rf_rate_hz: int, sideband: str = "USB"):
        self.cfg = cfg
        self.rf_rate_hz = int(rf_rate_hz)
        self.sideband = sideband.upper()

    def demod(self, iq: np.ndarray) -> np.ndarray:
        x = np.asarray(iq)
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)
        if not np.iscomplexobj(x):
            x = x.astype(np.complex64)
        if self.sideband == "LSB":
            x = np.conj(x)
        # Resample complex baseband to audio rate and take the in-phase component.
        _require_scipy()
        x_audio = signal.resample_poly(x, up=int(self.cfg.audio_rate_hz), down=int(self.rf_rate_hz)).astype(np.complex64)
        audio = np.real(x_audio).astype(np.float32)
        audio = _lpf_audio(audio, self.cfg.audio_rate_hz, self.cfg.audio_lpf_hz)
        audio *= float(self.cfg.audio_gain)
        return np.clip(audio, -1.0, 1.0)


class CwAudioDemodulator:
    """CW as audible tone: narrow LPF around BFO after mixing."""

    def __init__(self, cfg: AnalogConfig, rf_rate_hz: int):
        self.cfg = cfg
        self.rf_rate_hz = int(rf_rate_hz)
        self._phase: float = 0.0

    def demod(self, iq: np.ndarray) -> np.ndarray:
        x = np.asarray(iq)
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)
        if not np.iscomplexobj(x):
            x = x.astype(np.complex64)
        n = np.arange(x.size, dtype=np.float64)
        w = 2.0 * np.pi * float(self.cfg.bfo_hz) / float(self.rf_rate_hz)
        phase = self._phase + w * n
        osc = np.exp(1j * phase).astype(np.complex64)
        self._phase = float((self._phase + w * x.size) % (2.0 * np.pi))
        mixed = x * osc
        tone = np.real(mixed).astype(np.float32)
        audio = _resample_to_audio(tone, self.rf_rate_hz, self.cfg.audio_rate_hz)
        # CW: narrower filter than voice
        audio = _lpf_audio(audio, self.cfg.audio_rate_hz, min(800.0, self.cfg.audio_lpf_hz))
        audio *= float(self.cfg.audio_gain)
        return np.clip(audio, -1.0, 1.0)

