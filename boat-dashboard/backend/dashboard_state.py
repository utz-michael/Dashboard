import time

from n2k_decode import FUEL_TYPES, FRESH_WATER_TYPES, BLACK_WATER_TYPES

STALE_AFTER_S = 5.0  # Werte aelter als das gelten als "keine Daten"


class DashboardState:
    def __init__(self):
        self._values = {}      # key -> value
        self._timestamps = {}  # key -> unix time

    def _set(self, key, value):
        if value is None:
            return
        self._values[key] = value
        self._timestamps[key] = time.time()

    def apply(self, pgn: int, sa: int, decoded: dict):
        if pgn == 127488:
            self._set("rpm", decoded.get("rpm"))

        elif pgn == 127489:
            self._set("oil_pressure_bar", decoded.get("oil_pressure_bar"))
            self._set("coolant_temp_c", decoded.get("coolant_temp_c"))
            self._set("alternator_voltage", decoded.get("alternator_voltage"))

        elif pgn == 128259:
            self._set("speed_water_ms", decoded.get("speed_water_ms"))

        elif pgn == 129026:
            self._set("sog_ms", decoded.get("sog_ms"))

        elif pgn == 127505:
            ftype = decoded.get("fluid_type")
            pct = decoded.get("level_pct")
            if ftype in FUEL_TYPES:
                self._set("tank_fuel_pct", pct)
            elif ftype in FRESH_WATER_TYPES:
                self._set("tank_fresh_pct", pct)
            elif ftype in BLACK_WATER_TYPES:
                self._set("tank_black_pct", pct)

        elif pgn == 127245:
            self._set("rudder_deg", decoded.get("position_deg"))

        elif pgn == 127508:
            self._set("battery_voltage", decoded.get("voltage"))

        elif pgn == 127250:
            # Nur magnetischen Kurs uebernehmen (true-Meldungen ignorieren,
            # damit die Anzeige nicht zwischen MAG/TRUE hin- und herspringt).
            if decoded.get("heading_ref") == "magnetic":
                self._set("heading_deg", decoded.get("heading_deg"))
                self._set("heading_ref", decoded.get("heading_ref"))

    def _fresh(self, key):
        ts = self._timestamps.get(key)
        if ts is None or (time.time() - ts) > STALE_AFTER_S:
            return None
        return self._values.get(key)

    def snapshot(self) -> dict:
        # Geschwindigkeit: bevorzugt Log (Wasser), sonst GPS (Grund)
        speed_ms = self._fresh("speed_water_ms")
        speed_source = "log"
        if speed_ms is None:
            speed_ms = self._fresh("sog_ms")
            speed_source = "gps"
        speed_kmh = round(speed_ms * 3.6, 1) if speed_ms is not None else None

        coolant_c = self._fresh("coolant_temp_c")
        coolant_f = round(coolant_c * 9 / 5 + 32, 1) if coolant_c is not None else None

        return {
            "rpm": self._fresh("rpm"),
            "speed_kmh": speed_kmh,
            "speed_source": speed_source,
            "oil_pressure_bar": self._fresh("oil_pressure_bar"),
            "coolant_temp_f": coolant_f,
            "tank_fuel_pct": self._fresh("tank_fuel_pct"),
            "tank_fresh_pct": self._fresh("tank_fresh_pct"),
            "tank_black_pct": self._fresh("tank_black_pct"),
            "rudder_deg": self._fresh("rudder_deg"),
            "battery_voltage": self._fresh("battery_voltage") or self._fresh("alternator_voltage"),
            "heading_deg": self._fresh("heading_deg"),
            "heading_ref": self._fresh("heading_ref"),
            "server_time": time.time(),
        }
