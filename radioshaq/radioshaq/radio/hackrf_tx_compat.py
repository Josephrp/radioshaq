"""HackRF TX compatibility helpers for pyhackrf2 and test fakes."""

from __future__ import annotations

import inspect
import time
from ctypes import CFUNCTYPE, POINTER, c_int, memmove
from typing import Any

try:
    from pyhackrf2.cinterface import lib_hackrf_transfer, libhackrf
except ImportError:  # pragma: no cover - optional dependency
    lib_hackrf_transfer = None
    libhackrf = None


def _stream_via_direct_libhackrf(dev: Any, payload: bytes, duration_sec: float) -> None:
    """Use libhackrf directly with a safe TX callback."""
    if lib_hackrf_transfer is None or libhackrf is None:
        raise RuntimeError(
            "Direct libhackrf TX path requires pyhackrf2.cinterface. "
            "Install with: uv sync --extra hackrf (or pip install pyhackrf2)"
        )

    sent = 0

    @CFUNCTYPE(c_int, POINTER(lib_hackrf_transfer))
    def _tx_cb(transfer_ptr: Any) -> int:
        nonlocal sent
        transfer = transfer_ptr.contents
        remaining = len(payload) - sent
        if remaining <= 0:
            transfer.valid_length = 0
            return 1
        chunk_len = min(int(transfer.buffer_length), remaining)
        chunk = payload[sent : sent + chunk_len]
        memmove(transfer.buffer, chunk, chunk_len)
        transfer.valid_length = chunk_len
        sent += chunk_len
        return 1 if sent >= len(payload) else 0

    dev._check_error(libhackrf.hackrf_start_tx(dev._device_pointer, _tx_cb, None))
    try:
        deadline = time.monotonic() + max(duration_sec + 0.5, 0.5)
        while time.monotonic() < deadline and sent < len(payload):
            time.sleep(0.01)
        time.sleep(0.05)
    finally:
        dev._check_error(libhackrf.hackrf_stop_tx(dev._device_pointer))


def _stream_via_start_tx_buffer(dev: Any, payload: bytes, duration_sec: float) -> None:
    """Use pyhackrf2's public start_tx()/buffer API when direct access is unavailable."""
    dev.buffer = bytearray(payload)
    dev.start_tx()
    try:
        time.sleep(duration_sec + 0.5)
    finally:
        dev.stop_tx()


def _stream_via_callback(dev: Any, payload: bytes, duration_sec: float) -> None:
    """Legacy callback-driven TX path used by tests and older shims."""
    sent = [0]
    start_time = time.monotonic()

    def _tx_cb(transfer: Any) -> int:
        blen = getattr(transfer, "buffer_length", None)
        if blen is None:
            blen = len(transfer.buffer)
        start = sent[0]
        if start >= len(payload):
            return 1
        end = min(start + int(blen), len(payload))
        data = payload[start:end]
        target = transfer.buffer
        if isinstance(target, (bytearray, memoryview)):
            target[: len(data)] = data
        else:
            memmove(target, data, len(data))
        sent[0] = end
        return 1 if end >= len(payload) else 0

    dev.start_tx(_tx_cb)
    deadline = start_time + max(duration_sec + 0.5, 0.5)
    try:
        while time.monotonic() < deadline and sent[0] < len(payload):
            time.sleep(0.01)
    finally:
        dev.stop_tx()
        # Ensure we do not return significantly earlier than the requested duration
        elapsed = time.monotonic() - start_time
        if duration_sec > 0 and elapsed < duration_sec:
            time.sleep(duration_sec - elapsed)


def stream_hackrf_iq_bytes(dev: Any, payload: bytes, duration_sec: float) -> None:
    """Transmit interleaved int8 IQ bytes through a HackRF-compatible device."""
    if libhackrf is not None and hasattr(dev, "_device_pointer") and hasattr(dev, "_check_error"):
        _stream_via_direct_libhackrf(dev, payload, duration_sec)
        return

    start_tx = getattr(dev, "start_tx", None)
    if start_tx is None:
        raise AttributeError("HackRF device does not expose start_tx")

    param_count = len(inspect.signature(start_tx).parameters)
    if param_count == 0:
        _stream_via_start_tx_buffer(dev, payload, duration_sec)
        return
    _stream_via_callback(dev, payload, duration_sec)
