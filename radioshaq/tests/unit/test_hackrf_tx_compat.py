from __future__ import annotations

import threading
import time
from typing import Any

from radioshaq.radio.hackrf_tx_compat import stream_hackrf_iq_bytes


class _FakeTransfer:
    def __init__(self, buf_len: int = 64) -> None:
        self.buffer = bytearray(buf_len)
        self.buffer_length = buf_len


class _AsyncFakeDevice:
    def __init__(self) -> None:
        self._stop_flag = False
        self.stops = 0

    def start_tx(self, cb) -> None:
        def _runner() -> None:
            t = _FakeTransfer()
            while not self._stop_flag:
                # Call the callback until it signals completion.
                done = cb(t)
                if done:
                    break
                time.sleep(0.005)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()

    def stop_tx(self) -> None:
        self._stop_flag = True
        self.stops += 1


def test_stream_hackrf_iq_bytes_respects_duration_and_stops_once() -> None:
    dev = _AsyncFakeDevice()
    payload = b"\x01\x02" * 512
    duration = 0.1
    start = time.monotonic()
    stream_hackrf_iq_bytes(dev, payload, duration)
    elapsed = time.monotonic() - start
    # Should run for at least roughly the requested duration (with small margin).
    assert elapsed >= duration
    # stop_tx should have been called exactly once.
    assert dev.stops == 1

