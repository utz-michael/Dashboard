"""
Empfaengt NMEA2000-Daten im Yacht Devices RAW-Textformat per UDP
(z.B. von einem YDWG-02 WLAN-Gateway) und decodiert die benoetigten PGNs.

Zeilenformat: "hh:mm:ss.ddd D XXXXXXXX b0 b1 b2 b3 b4 b5 b6 b7"
  D          = R (empfangen) oder T (gesendet) - wir werten nur R aus
  XXXXXXXX   = 29-Bit CAN-ID als 8 Hex-Zeichen
  b0..b7     = bis zu 8 Datenbytes, hex, durch Leerzeichen getrennt
"""
import asyncio
import logging
import time

from n2k_decode import DECODERS, FAST_PACKET_PGNS

log = logging.getLogger("n2k_udp")

DEBUG_RAW = False  # auf True setzen, um jede empfangene Zeile zu loggen


def parse_can_id(can_id: int):
    """Zerlegt eine 29-Bit CAN-ID in Prioritaet, PGN und Quelladresse."""
    priority = (can_id >> 26) & 0x7
    dp = (can_id >> 24) & 0x1
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF
    sa = can_id & 0xFF
    if pf < 240:
        pgn = (dp << 16) | (pf << 8)
    else:
        pgn = (dp << 16) | (pf << 8) | ps
    return priority, pgn, sa


class FastPacketAssembler:
    """Setzt NMEA2000 Fast-Packet Frames (>8 Byte Nutzdaten) wieder zusammen."""

    def __init__(self):
        self._buffers = {}  # key: (pgn, sa) -> dict(seq, next_frame, total, data)

    def feed(self, pgn, sa, data: bytes):
        if not data:
            return None
        key = (pgn, sa)
        seq = data[0] >> 5
        frame = data[0] & 0x1F

        if frame == 0:
            total = data[1]
            self._buffers[key] = {
                "seq": seq,
                "next_frame": 1,
                "total": total,
                "data": bytearray(data[2:8]),
            }
        else:
            buf = self._buffers.get(key)
            if not buf or buf["seq"] != seq or buf["next_frame"] != frame:
                # Frame verloren oder ausserhalb der Reihenfolge -> verwerfen
                self._buffers.pop(key, None)
                return None
            buf["data"].extend(data[1:8])
            buf["next_frame"] += 1

        buf = self._buffers.get(key)
        if buf and len(buf["data"]) >= buf["total"]:
            complete = bytes(buf["data"][: buf["total"]])
            del self._buffers[key]
            return complete
        return None


class N2KProtocol(asyncio.DatagramProtocol):
    def __init__(self, state, on_update=None):
        self.state = state
        self.on_update = on_update
        self.fp = FastPacketAssembler()
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        log.info("UDP-Listener bereit")

    def datagram_received(self, data: bytes, addr):
        try:
            text = data.decode("ascii", errors="ignore")
        except Exception:
            return
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if DEBUG_RAW:
                log.debug("RAW: %s", line)
            self._handle_line(line)

    def _handle_line(self, line: str):
        parts = line.split()
        if len(parts) < 3:
            return
        direction = parts[1]
        if direction != "R":
            return
        try:
            can_id = int(parts[2], 16)
            payload = bytes(int(b, 16) for b in parts[3:])
        except ValueError:
            return

        _, pgn, sa = parse_can_id(can_id)
        if pgn not in DECODERS:
            return

        if pgn in FAST_PACKET_PGNS:
            complete = self.fp.feed(pgn, sa, payload)
            if complete is None:
                return
            payload = complete

        decoded = DECODERS[pgn](payload)
        if decoded is None:
            return

        self.state.apply(pgn, sa, decoded)
        if self.on_update:
            self.on_update(pgn, sa, decoded)

    def error_received(self, exc):
        log.warning("UDP-Fehler: %s", exc)


async def start_udp_listener(state, port: int, on_update=None):
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: N2KProtocol(state, on_update),
        local_addr=("0.0.0.0", port),
    )
    return transport
