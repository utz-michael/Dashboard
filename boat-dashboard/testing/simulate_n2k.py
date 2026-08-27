"""
Sendet einen kontinuierlichen, realistisch schwankenden NMEA2000-Testdatenstrom
im Yacht Devices RAW-Format per UDP - zum direkten Testen des Dashboards,
ganz ohne Wireshark/tcpreplay noetig.

Verwendung:
    python3 simulate_n2k.py                       # an 127.0.0.1:1457 (Dashboard laeuft lokal)
    python3 simulate_n2k.py --host 192.168.1.50    # an anderen Rechner/Pi im Netz
    python3 simulate_n2k.py --host 255.255.255.255 --broadcast   # wie ein echtes YDWG-02

Strg+C zum Beenden.
"""
import argparse
import math
import random
import socket
import time

import n2k_encode as enc


def build_socket(broadcast: bool):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if broadcast:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return s


def send_lines(sock, addr, lines):
    if isinstance(lines, str):
        lines = [lines]
    for line in lines:
        sock.sendto(line.encode("ascii"), addr)


def main():
    ap = argparse.ArgumentParser(description="NMEA2000 UDP-Testdatenstrom-Simulator")
    ap.add_argument("--host", default="127.0.0.1", help="Ziel-IP (Standard: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=1457, help="Ziel-Port (Standard: 1457)")
    ap.add_argument("--broadcast", action="store_true", help="UDP-Broadcast erlauben (z.B. bei --host 255.255.255.255)")
    ap.add_argument("--duration", type=float, default=None, help="Laufzeit in Sekunden (Standard: unbegrenzt)")
    args = ap.parse_args()

    sock = build_socket(args.broadcast)
    addr = (args.host, args.port)

    t0 = time.time()
    next_send = {"rapid": 0, "engine_dyn": 0, "speed": 0, "tanks": 0, "battery": 0, "heading_true": 0}
    tank_cycle = 0
    seq489 = 0

    print(f"Sende Testdaten an {args.host}:{args.port} (Strg+C zum Beenden)")
    try:
        while True:
            now = time.time()
            t = now - t0
            if args.duration and t > args.duration:
                break

            # --- schnelle PGNs: RPM, Ruder, Kompass (alle ~200ms) ---
            if now >= next_send["rapid"]:
                rpm = 2500 + 1200 * math.sin(t / 15) + random.uniform(-15, 15)
                rpm = max(0, rpm)
                rudder = 15 * math.sin(t / 8)
                heading = (t / 240 * 360 + 10 * math.sin(t / 30)) % 360

                send_lines(sock, addr, enc.enc_127488(rpm))
                send_lines(sock, addr, enc.enc_127245(rudder))
                send_lines(sock, addr, enc.enc_127250(heading, ref="magnetic"))
                next_send["rapid"] = now + 0.2

            # --- gelegentlich eine "true"-Kursmeldung, um den MAG/TRUE-Filter zu testen ---
            if now >= next_send["heading_true"]:
                heading = (t / 240 * 360 + 10 * math.sin(t / 30) + 4.5) % 360  # + Missweisung
                send_lines(sock, addr, enc.enc_127250(heading, ref="true"))
                next_send["heading_true"] = now + 5.0

            # --- Motor-Dynamik: Oeldruck, Kuehlwasser, Lichtmaschine (~1s, Fast Packet) ---
            if now >= next_send["engine_dyn"]:
                rpm_now = 2500 + 1200 * math.sin(t / 15)
                oil = 1.5 + max(0, rpm_now) / 5000 * 3.5 + random.uniform(-0.05, 0.05)
                coolant = 70 + min(1.0, t / 120) * 12 + random.uniform(-0.3, 0.3)
                alt_v = 14.1 + random.uniform(-0.1, 0.1)
                seq489 = (seq489 + 1) % 8
                send_lines(sock, addr, enc.enc_127489(oil, coolant, alt_v, seq=seq489))
                next_send["engine_dyn"] = now + 1.0

            # --- Geschwindigkeit ueber Wasser + Grund (~1s) ---
            if now >= next_send["speed"]:
                rpm_now = 2500 + 1200 * math.sin(t / 15)
                speed_ms = max(0, (rpm_now - 800) / 4700 * 12.5) + random.uniform(-0.05, 0.05)
                send_lines(sock, addr, enc.enc_128259(speed_ms))
                send_lines(sock, addr, enc.enc_129026(speed_ms * 0.98, cog_deg=90))
                next_send["speed"] = now + 1.0

            # --- Bordspannung (~1.5s) ---
            if now >= next_send["battery"]:
                batt_v = 12.6 + random.uniform(-0.08, 0.08)
                send_lines(sock, addr, enc.enc_127508(batt_v))
                next_send["battery"] = now + 1.5

            # --- Tankfuellstaende, reihum (~2.5s je Tank) ---
            if now >= next_send["tanks"]:
                fuel_pct = max(0, 80 - t / 60 * 0.5)
                fresh_pct = max(0, 60 - t / 60 * 0.3)
                black_pct = min(100, 10 + t / 60 * 0.4)
                which = tank_cycle % 3
                if which == 0:
                    send_lines(sock, addr, enc.enc_127505(0, fuel_pct, instance=0, capacity_l=300))
                elif which == 1:
                    send_lines(sock, addr, enc.enc_127505(1, fresh_pct, instance=1, capacity_l=150))
                else:
                    send_lines(sock, addr, enc.enc_127505(5, black_pct, instance=2, capacity_l=100))
                tank_cycle += 1
                next_send["tanks"] = now + 2.5

            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\nBeendet.")


if __name__ == "__main__":
    main()
