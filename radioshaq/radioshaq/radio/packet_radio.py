"""AX.25 packet radio interface via KISS TNC (Direwolf, SoundModem)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger

# KISS protocol constants
KISS_FEND = 0xC0
KISS_FESC = 0xDB
KISS_TFEND = 0xDC
KISS_TFESC = 0xDD
KISS_CMD_DATA = 0x00
AX25_PID_NO_LAYER3 = 0xF0


@dataclass
class AX25Frame:
    """AX.25 frame structure."""

    destination: str
    source: str
    digipeaters: list[str]
    payload: bytes
    pid: int = AX25_PID_NO_LAYER3


def _encode_callsign_ssid(callsign: str, ssid: int = 0) -> bytes:
    """Encode callsign-SSID to AX.25 address field (7 bytes)."""
    base = callsign.split("-")[0].upper()[:6].ljust(6)
    raw = bytes(base, "ascii")
    result = bytes(b << 1 for b in raw)
    result += bytes([(ssid << 1) | 0x61])
    return result


def _encode_ax25_frame(frame: AX25Frame) -> bytes:
    """Encode AX.25 frame to bytes (minimal implementation)."""
    dest_base = frame.destination.split("-")[0]
    dest_ssid = int(frame.destination.split("-")[-1]) if "-" in frame.destination else 0
    dest = _encode_callsign_ssid(dest_base, dest_ssid)
    dest_last = dest[-1] | 0x01 if not frame.digipeaters else dest[-1] & 0xFE
    dest = dest[:-1] + bytes([dest_last])

    src_base = frame.source.split("-")[0]
    src_ssid = int(frame.source.split("-")[-1]) if "-" in frame.source else 0
    src = _encode_callsign_ssid(src_base, src_ssid)
    src = src[:-1] + bytes([src[-1] | 0x01])

    digi_bytes = b""
    for i, d in enumerate(frame.digipeaters):
        d_base = d.split("-")[0]
        d_ssid = int(d.split("-")[-1]) if "-" in d else 0
        d_enc = _encode_callsign_ssid(d_base, d_ssid)
        d_last = d_enc[-1] | 0x01 if i == len(frame.digipeaters) - 1 else d_enc[-1] & 0xFE
        digi_bytes += d_enc[:-1] + bytes([d_last])

    ctrl = bytes([0x03])
    pid = bytes([frame.pid])
    return dest + src + digi_bytes + ctrl + pid + frame.payload


def _escape_kiss(data: bytes) -> bytes:
    """Escape KISS special bytes in data."""
    return data.replace(bytes([KISS_FESC]), bytes([KISS_FESC, KISS_TFESC])).replace(
        bytes([KISS_FEND]), bytes([KISS_FESC, KISS_TFEND])
    )


def _unescape_kiss(data: bytes) -> bytes:
    """Unescape KISS special bytes."""
    result = bytearray()
    i = 0
    while i < len(data):
        if data[i] == KISS_FESC and i + 1 < len(data):
            if data[i + 1] == KISS_TFEND:
                result.append(KISS_FEND)
            elif data[i + 1] == KISS_TFESC:
                result.append(KISS_FESC)
            i += 2
        else:
            result.append(data[i])
            i += 1
    return bytes(result)


class PacketRadioInterface:
    """
    AX.25 packet radio interface via KISS TNC.

    Connects to Direwolf, SoundModem, or other KISS-compatible TNC via TCP.
    """

    def __init__(
        self,
        callsign: str = "N0CALL",
        ssid: int = 0,
        kiss_host: str = "localhost",
        kiss_port: int = 8001,
    ):
        self.callsign = callsign.upper()
        self.ssid = ssid
        self.kiss_host = kiss_host
        self.kiss_port = kiss_port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._frame_handlers: list[Callable[[AX25Frame], None]] = []
        self._reader_task: asyncio.Task | None = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to KISS TNC via TCP."""
        self._reader, self._writer = await asyncio.open_connection(
            self.kiss_host, self.kiss_port
        )
        self._connected = True
        self._reader_task = asyncio.create_task(self._frame_reader())
        logger.info("Connected to KISS TNC at %s:%d", self.kiss_host, self.kiss_port)

    async def disconnect(self) -> None:
        """Disconnect from KISS TNC."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
        self._connected = False

    async def send_packet(
        self,
        destination: str,
        message: str | bytes,
        digipeaters: list[str] | None = None,
    ) -> None:
        """Send an AX.25 packet."""
        if not self._writer:
            raise RuntimeError("Not connected to KISS TNC")
        payload = message.encode("utf-8") if isinstance(message, str) else message
        frame = AX25Frame(
            destination=destination,
            source=f"{self.callsign}-{self.ssid}",
            digipeaters=digipeaters or [],
            payload=payload,
        )
        kiss_frame = self._encode_kiss(frame)
        self._writer.write(kiss_frame)
        await self._writer.drain()

    def on_frame(self, handler: Callable[[AX25Frame], None]) -> None:
        """Register a handler for received frames."""
        self._frame_handlers.append(handler)

    def _encode_kiss(self, frame: AX25Frame) -> bytes:
        """Encode AX.25 frame to KISS format."""
        ax25 = _encode_ax25_frame(frame)
        escaped = _escape_kiss(ax25)
        return bytes([KISS_FEND, KISS_CMD_DATA]) + escaped + bytes([KISS_FEND])

    def _decode_kiss(self, data: bytes) -> AX25Frame | None:
        """Decode KISS frame to AX25Frame (minimal - extracts payload)."""
        if len(data) < 2 or data[0] != KISS_FEND:
            return None
        payload_start = 2
        unescaped = _unescape_kiss(data[2:])
        if len(unescaped) < 16:
            return None
        dest = unescaped[:7]
        src = unescaped[7:14]
        idx = 14
        while idx < len(unescaped) and unescaped[idx] & 0x01 == 0:
            idx += 7
        idx += 7
        if idx + 2 > len(unescaped):
            return None
        pid = unescaped[idx + 1]
        payload = unescaped[idx + 2:]
        dest_cs = "".join(chr(b >> 1) for b in dest[:6]).strip()
        src_cs = "".join(chr(b >> 1) for b in src[:6]).strip()
        return AX25Frame(
            destination=dest_cs,
            source=src_cs,
            digipeaters=[],
            payload=payload,
            pid=pid,
        )

    async def _read_kiss_frame(self) -> bytes | None:
        """Read one KISS frame from TNC."""
        if not self._reader:
            return None
        buf = bytearray()
        while True:
            b = await self._reader.read(1)
            if not b:
                return None
            buf.append(b[0])
            if b[0] == KISS_FEND and len(buf) > 2:
                return bytes(buf)
            if len(buf) > 4096:
                return None

    async def _frame_reader(self) -> None:
        """Background task to read frames from TNC."""
        while self._reader:
            try:
                frame_data = await self._read_kiss_frame()
                if frame_data:
                    frame = self._decode_kiss(frame_data)
                    if frame:
                        for handler in self._frame_handlers:
                            try:
                                handler(frame)
                            except Exception as e:
                                logger.warning("Frame handler error: %s", e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("KISS frame reader error: %s", e)
                await asyncio.sleep(1)
