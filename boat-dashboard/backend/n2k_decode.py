"""
Decoder fuer die benoetigten NMEA2000 PGNs.

Byte-Layouts und Skalierungsfaktoren stammen aus den ueblichen
NMEA2000/canboat PGN-Definitionen. Manche Hersteller weichen bei
selten genutzten Feldern leicht ab - falls ein Wert falsch aussieht,
zuerst mit einem Tool wie "candump"/"actisense-serial" oder den
rohen Bytes in n2k_udp.py (DEBUG_RAW=True) gegenchecken und die
Byte-Offsets hier anpassen.
"""
import math

FUEL_TYPES = {0, 6}        # 0 = Fuel, 6 = Fuel (Gasoline)
FRESH_WATER_TYPES = {1}    # 1 = (Fresh) Water
BLACK_WATER_TYPES = {5}    # 5 = Black Water

# PGNs, die als NMEA2000 "Fast Packet" (>8 Byte) uebertragen werden
FAST_PACKET_PGNS = {127489, 129029, 126996, 126998}


def _u16(d, i):
    v = int.from_bytes(d[i:i + 2], "little", signed=False)
    return None if v == 0xFFFF else v


def _s16(d, i):
    v = int.from_bytes(d[i:i + 2], "little", signed=True)
    return None if v == -32768 else v


def _u32(d, i):
    v = int.from_bytes(d[i:i + 4], "little", signed=False)
    return None if v == 0xFFFFFFFF else v


def decode_127488(d):
    """Engine Parameters, Rapid Update -> Motordrehzahl"""
    if len(d) < 3:
        return None
    raw = _u16(d, 1)
    return {"engine_instance": d[0], "rpm": raw * 0.25 if raw is not None else None}


def decode_127489(d):
    """Engine Parameters, Dynamic -> Oeldruck, Kuehlwassertemp, Lichtmaschinenspannung"""
    if len(d) < 7:
        return None
    oil_raw = _u16(d, 1)
    coolant_raw = _u16(d, 5)
    alt_v = None
    if len(d) >= 9:
        v_raw = _s16(d, 7)
        alt_v = v_raw * 0.01 if v_raw is not None else None
    return {
        "engine_instance": d[0],
        "oil_pressure_bar": oil_raw * 0.001 if oil_raw is not None else None,
        "coolant_temp_c": (coolant_raw * 0.01 - 273.15) if coolant_raw is not None else None,
        "alternator_voltage": alt_v,
    }


def decode_128259(d):
    """Speed -> Fahrt durchs Wasser (Log)"""
    if len(d) < 3:
        return None
    raw = _u16(d, 1)
    return {"speed_water_ms": raw * 0.01 if raw is not None else None}


def decode_129026(d):
    """COG & SOG, Rapid Update -> Fahrt ueber Grund (GPS)"""
    if len(d) < 6:
        return None
    cog_raw = _u16(d, 2)
    sog_raw = _u16(d, 4)
    return {
        "cog_deg": math.degrees(cog_raw * 0.0001) if cog_raw is not None else None,
        "sog_ms": sog_raw * 0.01 if sog_raw is not None else None,
    }


def decode_127505(d):
    """Fluid Level -> Tankfuellstaende (Benzin / Frischwasser / Schwarzwasser)"""
    if len(d) < 7:
        return None
    instance = d[0] & 0x0F
    fluid_type = (d[0] >> 4) & 0x0F
    level_raw = _u16(d, 1)
    cap_raw = _u32(d, 3)
    return {
        "instance": instance,
        "fluid_type": fluid_type,
        "level_pct": level_raw * 0.004 if level_raw is not None else None,
        "capacity_l": cap_raw * 0.1 if cap_raw is not None else None,
    }


def decode_127245(d):
    """Rudder -> Ruderlage"""
    if len(d) < 6:
        return None
    pos_raw = _s16(d, 4)
    return {
        "rudder_instance": d[0],
        "position_deg": math.degrees(pos_raw * 0.0001) if pos_raw is not None else None,
    }


def decode_127508(d):
    """Battery Status -> Bordspannung"""
    if len(d) < 3:
        return None
    v_raw = _s16(d, 1)
    return {"battery_instance": d[0], "voltage": v_raw * 0.01 if v_raw is not None else None}


def decode_127250(d):
    """Vessel Heading -> Kompasskurs"""
    if len(d) < 8:
        return None
    raw = _u16(d, 1)
    ref = d[7] & 0x03
    return {
        "heading_deg": math.degrees(raw * 0.0001) if raw is not None else None,
        "heading_ref": {0: "true", 1: "magnetic", 2: "error", 3: "null"}.get(ref, "unknown"),
    }


DECODERS = {
    127488: decode_127488,
    127489: decode_127489,
    128259: decode_128259,
    129026: decode_129026,
    127505: decode_127505,
    127245: decode_127245,
    127508: decode_127508,
    127250: decode_127250,
}
