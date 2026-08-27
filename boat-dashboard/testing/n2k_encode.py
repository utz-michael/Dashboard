"""
Encoder fuer NMEA2000 PGNs im Yacht Devices RAW-Textformat.
Kehrfunktion zu backend/n2k_decode.py - aus Klartextwerten (RPM, Grad, bar, ...)
werden CAN-ID + Datenbytes gebaut, wie sie ein YDWG-02 senden wuerde.
"""
import math
import struct
import time

NA16 = 0xFFFF
NA16S = -32768  # "nicht verfuegbar" fuer signed 16-bit Felder


def build_can_id(pgn: int, priority: int, sa: int) -> int:
    dp = (pgn >> 16) & 0x1
    pf = (pgn >> 8) & 0xFF
    ps = (pgn & 0xFF) if pf >= 240 else 0xFF
    return (priority << 26) | (dp << 24) | (pf << 16) | (ps << 8) | sa


def yd_line(pgn: int, sa: int, data: bytes, priority: int = 6, ts: str = None) -> str:
    if ts is None:
        ts = time.strftime("%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
    can_id = build_can_id(pgn, priority, sa)
    hexbytes = " ".join(f"{b:02X}" for b in data)
    return f"{ts} R {can_id:08X} {hexbytes}"


def split_fast_packet(pgn, sa, payload: bytes, seq: int, priority: int = 6, ts: str = None):
    """Zerlegt eine Fast-Packet-Nutzlast (>8 Byte) in mehrere YD-RAW-Zeilen."""
    total = len(payload)
    lines = []
    frame = 0
    idx = 0
    while idx < total or frame == 0:
        if frame == 0:
            chunk = payload[0:6]
            data = bytes([(seq << 5) | 0, total]) + chunk.ljust(6, b"\xff")
            idx = 6
        else:
            chunk = payload[idx:idx + 7]
            data = bytes([(seq << 5) | frame]) + chunk.ljust(7, b"\xff")
            idx += 7
        lines.append(yd_line(pgn, sa, data, priority, ts))
        frame += 1
        if idx >= total:
            break
    return lines


# ---------- Einzelne PGN-Encoder (Kehrfunktion zu n2k_decode.py) ----------

def enc_127488(rpm: float, instance: int = 0, sa: int = 23):
    raw = int(round(rpm / 0.25)) & 0xFFFF
    data = bytes([instance]) + raw.to_bytes(2, "little") + (NA16).to_bytes(2, "little") + bytes([0xFF, 0xFF, 0xFF])
    return yd_line(127488, sa, data)


def enc_127489(oil_bar: float, coolant_c: float, alt_v: float, instance: int = 0, sa: int = 23, seq: int = 0):
    oil_raw = int(round(oil_bar / 0.001)) & 0xFFFF
    coolant_raw = int(round((coolant_c + 273.15) / 0.01)) & 0xFFFF
    alt_raw = struct.pack("<h", int(round(alt_v / 0.01)))
    payload = bytes([instance]) + oil_raw.to_bytes(2, "little") + (NA16).to_bytes(2, "little") \
        + coolant_raw.to_bytes(2, "little") + alt_raw
    payload += b"\xff" * (26 - len(payload))  # auf realistische Fast-Packet-Laenge auffuellen
    return split_fast_packet(127489, sa, payload, seq)


def enc_128259(speed_water_ms: float, sid: int = 0, sa: int = 42):
    raw = int(round(speed_water_ms / 0.01)) & 0xFFFF
    data = bytes([sid]) + raw.to_bytes(2, "little") + (NA16).to_bytes(2, "little") + bytes([0xFF, 0xFF, 0xFF])
    return yd_line(128259, sa, data)


def enc_129026(sog_ms: float, cog_deg: float = 0.0, sid: int = 0, sa: int = 42):
    cog_raw = int(round(math.radians(cog_deg % 360) / 0.0001)) & 0xFFFF
    sog_raw = int(round(sog_ms / 0.01)) & 0xFFFF
    data = bytes([sid, 0xFC]) + cog_raw.to_bytes(2, "little") + sog_raw.to_bytes(2, "little") + bytes([0xFF, 0xFF])
    return yd_line(129026, sa, data)


def enc_127505(fluid_type: int, level_pct: float, instance: int = 0, capacity_l: float = 200.0, sa: int = 63):
    b0 = ((fluid_type & 0x0F) << 4) | (instance & 0x0F)
    level_raw = int(round(level_pct / 0.004)) & 0xFFFF
    cap_raw = int(round(capacity_l / 0.1)) & 0xFFFFFFFF
    data = bytes([b0]) + level_raw.to_bytes(2, "little") + cap_raw.to_bytes(4, "little") + bytes([0xFF])
    return yd_line(127505, sa, data)


def enc_127245(position_deg: float, instance: int = 0, sa: int = 30):
    pos_raw = struct.pack("<h", int(round(math.radians(position_deg) / 0.0001)))
    angle_order = struct.pack("<h", NA16S)
    data = bytes([instance, 0xFF]) + angle_order + pos_raw + bytes([0xFF, 0xFF])
    return yd_line(127245, sa, data)


def enc_127508(voltage: float, instance: int = 0, sa: int = 1):
    v_raw = struct.pack("<h", int(round(voltage / 0.01)))
    na = struct.pack("<h", NA16S)
    data = bytes([instance]) + v_raw + na + na + bytes([0xFF])
    return yd_line(127508, sa, data)


REF_BITS = {"true": 0, "magnetic": 1, "error": 2, "null": 3}


def enc_127250(heading_deg: float, ref: str = "magnetic", sid: int = 0, sa: int = 60):
    raw = int(round(math.radians(heading_deg % 360) / 0.0001)) & 0xFFFF
    byte7 = 0xFC | (REF_BITS.get(ref, 1) & 0x03)
    data = bytes([sid]) + raw.to_bytes(2, "little") + bytes([0xFF, 0xFF]) + bytes([0xFF, 0xFF]) + bytes([byte7])
    return yd_line(127250, sa, data)
