"""
Erzeugt eine .pcapng-Datei mit simuliertem NMEA2000-UDP-Verkehr (Yacht Devices
RAW-Format), die sich in Wireshark oeffnen und mit tcpreplay tatsaechlich
"einspielen" laesst.

Wireshark selbst kann keine Pakete senden - nur mitschneiden/analysieren!
Zum Abspielen auf einem echten Netzwerk-Interface:

    sudo tcpreplay -i eth0 --mbps=1 n2k_test.pcapng

("--mbps=1" bremst die Wiedergabe, da die Original-Zeitabstaende sonst
sehr schnell abgespielt wuerden.)

Fuer einen lokalen Test auf dem Pi selbst ist simulate_n2k.py einfacher -
das sendet live per Socket, ganz ohne pcap/tcpreplay.
"""
import argparse
import math
import random
import sys

sys.path.insert(0, ".")
import n2k_encode as enc

from scapy.all import IP, UDP, Ether, wrpcap


def build_packets(src_ip, dst_ip, sport, dport, duration_s, broadcast):
    packets = []
    t = 0.0
    dt = 0.2  # Basis-Zeitraster; 127489/128259/etc. seltener eingestreut
    dst = dst_ip
    tank_cycle = 0
    seq489 = 0
    next_engine_dyn = 0.0
    next_speed = 0.0
    next_battery = 0.0
    next_tanks = 0.0
    next_heading_true = 0.0

    def add(lines, ts):
        nonlocal packets
        if isinstance(lines, str):
            lines = [lines]
        for line in lines:
            pkt = Ether() / IP(src=src_ip, dst=dst) / UDP(sport=sport, dport=dport) / line.encode("ascii")
            pkt.time = ts
            packets.append(pkt)

    while t < duration_s:
        rpm = max(0, 2500 + 1200 * math.sin(t / 15) + random.uniform(-15, 15))
        rudder = 15 * math.sin(t / 8)
        heading = (t / 240 * 360 + 10 * math.sin(t / 30)) % 360
        add(enc.enc_127488(rpm), t)
        add(enc.enc_127245(rudder), t)
        add(enc.enc_127250(heading, ref="magnetic"), t)

        if t >= next_heading_true:
            add(enc.enc_127250((heading + 4.5) % 360, ref="true"), t)
            next_heading_true = t + 5.0

        if t >= next_engine_dyn:
            oil = 1.5 + rpm / 5000 * 3.5 + random.uniform(-0.05, 0.05)
            coolant = 70 + min(1.0, t / 120) * 12 + random.uniform(-0.3, 0.3)
            alt_v = 14.1 + random.uniform(-0.1, 0.1)
            seq489 = (seq489 + 1) % 8
            add(enc.enc_127489(oil, coolant, alt_v, seq=seq489), t)
            next_engine_dyn = t + 1.0

        if t >= next_speed:
            speed_ms = max(0, (rpm - 800) / 4700 * 12.5) + random.uniform(-0.05, 0.05)
            add(enc.enc_128259(speed_ms), t)
            add(enc.enc_129026(speed_ms * 0.98, cog_deg=90), t)
            next_speed = t + 1.0

        if t >= next_battery:
            add(enc.enc_127508(12.6 + random.uniform(-0.08, 0.08)), t)
            next_battery = t + 1.5

        if t >= next_tanks:
            fuel_pct = max(0, 80 - t / 60 * 0.5)
            fresh_pct = max(0, 60 - t / 60 * 0.3)
            black_pct = min(100, 10 + t / 60 * 0.4)
            which = tank_cycle % 3
            if which == 0:
                add(enc.enc_127505(0, fuel_pct, instance=0, capacity_l=300), t)
            elif which == 1:
                add(enc.enc_127505(1, fresh_pct, instance=1, capacity_l=150), t)
            else:
                add(enc.enc_127505(5, black_pct, instance=2, capacity_l=100), t)
            tank_cycle += 1
            next_tanks = t + 2.5

        t += dt

    return packets


def main():
    ap = argparse.ArgumentParser(description="Erzeugt eine NMEA2000-Test-pcapng-Datei")
    ap.add_argument("--out", default="n2k_test.pcapng")
    ap.add_argument("--duration", type=float, default=90.0, help="simulierte Dauer in Sekunden")
    ap.add_argument("--src-ip", default="192.168.1.50", help="simulierte IP des N2K-Gateways")
    ap.add_argument("--dst-ip", default="192.168.1.100", help="Ziel-IP (dein Pi)")
    ap.add_argument("--port", type=int, default=1457)
    ap.add_argument("--broadcast", action="store_true", help="Ziel-IP auf 255.255.255.255 setzen")
    args = ap.parse_args()

    dst_ip = "255.255.255.255" if args.broadcast else args.dst_ip
    packets = build_packets(args.src_ip, dst_ip, sport=2000, dport=args.port,
                             duration_s=args.duration, broadcast=args.broadcast)
    wrpcap(args.out, packets)
    print(f"{len(packets)} Pakete geschrieben -> {args.out}")
    print(f"Abspielen mit:  sudo tcpreplay -i <interface> --mbps=1 {args.out}")


if __name__ == "__main__":
    main()
