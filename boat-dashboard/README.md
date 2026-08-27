# Motor Dashboard für Raspberry Pi 5

Empfängt NMEA2000-Daten (Yacht Devices RAW-Format) per UDP auf Port 1457
und zeigt sie als Vollbild-Dashboard im Browser an:

- Motordrehzahl (0–5000 U/min) – PGN 127488
- Geschwindigkeit (0–60 km/h, bevorzugt Log/Wasser, sonst GPS/Grund) – PGN 128259 / 129026
- Öldruck (0–10 bar) – PGN 127489
- Motor-Kühlwassertemperatur (100–250 °F) – PGN 127489
- Benzin-Tankfüllstand – PGN 127505 (Fluid Type 0/6)
- Frischwasser-Tankfüllstand – PGN 127505 (Fluid Type 1)
- Schwarzwasser-Tankfüllstand – PGN 127505 (Fluid Type 5)
- Ruderlage (±40°) – PGN 127245
- Bordspannung – PGN 127508 (fällt auf Lichtmaschinenspannung aus PGN 127489 zurück)
- Kompasskurs – PGN 127250

Läuft komplett offline (kein CDN, keine externen JS-Bibliotheken) – wichtig,
da auf dem Boot in der Regel kein Internet zur Verfügung steht.

## Architektur

```
backend/    Python (aiohttp): UDP-Empfänger + Decoder + WebSocket-Server
frontend/   HTML/CSS/JS: Canvas-Gauges, verbindet sich per WebSocket
systemd/    Autostart-Units für Server + Kiosk-Browser
```

Der Server hört NMEA2000 auf UDP 1457 und liefert das Dashboard per HTTP
auf Port 8080 aus (`http://<pi-ip>:8080/`). Aktualisierungsrate zum Browser: 5 Hz.

## Installation auf dem Pi

```bash
sudo apt update
sudo apt install -y python3-venv chromium-browser

# Projekt auf den Pi kopieren, dann:
cd ~/boat-dashboard/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Test-Start:
```bash
python app.py
```
Dashboard im Browser öffnen: `http://<pi-ip>:8080/`

## Autostart einrichten

```bash
sudo cp ~/boat-dashboard/systemd/boat-dashboard.service /etc/systemd/system/
sudo cp ~/boat-dashboard/systemd/boat-dashboard-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now boat-dashboard.service
sudo systemctl enable --now boat-dashboard-kiosk.service
```

Falls der Pi ohne Desktop-Umgebung läuft (nur Framebuffer), Chromium durch
einen Kiosk-Autostart über `labwc`/`wayfire` bzw. X11-`.xinitrc` ersetzen,
je nachdem was auf dem Pi 5 als Grafikstack läuft.

## Wichtige Hinweise / Anpassungsstellen

- **Datenquelle geprüft?** Das Backend geht vom Yacht Devices RAW-Textformat
  aus (`hh:mm:ss.ddd R <CAN-ID-hex> <b0> <b1> ...`). Falls dein Gateway ein
  anderes Format sendet (z.B. CanBoat-JSON), muss nur `backend/n2k_udp.py`
  angepasst werden – die Decoder in `n2k_decode.py` bleiben gleich.
- **Byte-Offsets prüfen:** Ich habe die PGN-Layouts nach den üblichen
  NMEA2000/CanBoat-Definitionen implementiert. Manche Geräte weichen bei
  Zusatzfeldern leicht ab. Zum Debuggen `DEBUG_RAW = True` in
  `n2k_udp.py` setzen – dann werden alle empfangenen Zeilen geloggt und
  du kannst die Rohbytes mit echten Werten (z.B. bekannte Drehzahl) abgleichen.
  Als Referenz eignet sich auch das freie Tool `canboat` (Feld-Definitionen
  in `pgns.json`).
- **Bordspannungs-Zonen:** Die Grenzwerte im Volt-Gauge (`dashboard.js`,
  10–16 V, rot <11,5 V / >14,8 V) sind für Blei-Batterien ausgelegt. Bei
  deinem LiFePO4-System sollten die Zonen eher auf ~12,8–14,6 V angepasst
  werden.
- **Tankzuordnung:** Falls dein Gateway andere `Fluid Type`-Codes nutzt als
  Standard (0/6=Benzin, 1=Frischwasser, 5=Schwarzwasser), die Sets
  `FUEL_TYPES` / `FRESH_WATER_TYPES` / `BLACK_WATER_TYPES` in
  `n2k_decode.py` anpassen.
- **Mehrere Motoren:** Aktuell wird nur eine Engine-Instanz verarbeitet
  (die zuletzt empfangene). Für Zwillingsmotoren müsste `dashboard_state.py`
  Werte pro `engine_instance` getrennt halten.
- **Firewall:** Falls UDP 1457 nicht ankommt, prüfen ob `ufw`/`iptables`
  auf dem Pi eingehenden UDP-Traffic blockiert.

## Dashboard testen ohne echten NMEA2000-Bus

Im Ordner `testing/` liegen zwei Tools, die realistische, sich über die Zeit
verändernde Testdaten erzeugen (RPM-Schwankung, langsam steigende Motortemperatur,
sinkender Tankfüllstand, rotierender Kompass, gelegentliche "true"-Kursmeldungen
zum Testen des MAG/TRUE-Filters, ...).

### Variante A: Live-Sender (einfachster Weg)

```bash
cd testing
python3 simulate_n2k.py --host 127.0.0.1 --port 1457
```

Läuft das Backend bereits (`boat-dashboard.service` oder manuell), sieht man
sofort Bewegung im Dashboard. Mit `--host <Pi-IP>` lässt es sich auch von
einem anderen Rechner im selben Netz aus testen. Strg+C beendet den Sender.

### Variante B: pcap-Datei für Wireshark / tcpreplay

Wireshark selbst kann keine Pakete senden, nur mitschneiden/analysieren.
Zum "Einspielen" braucht es `tcpreplay`:

```bash
cd testing
pip install scapy
python3 generate_pcap.py --out n2k_test.pcapng --duration 90 \
  --src-ip 192.168.1.50 --dst-ip 192.168.1.100 --port 1457
```

Die Datei kann in Wireshark geöffnet/inspiziert werden. Zum tatsächlichen
Abspielen auf ein Netzwerk-Interface (z.B. wenn der Pi die Pakete per LAN
empfangen soll):

```bash
sudo apt install tcpreplay
sudo tcpreplay -i eth0 --mbps=1 n2k_test.pcapng
```

`--dst-ip` sollte die tatsächliche IP des Pi im Testnetz sein (oder
`--broadcast` verwenden, um wie ein echtes YDWG-02 per Broadcast zu senden).
Auf `lo` (localhost) funktioniert `tcpreplay` aus technischen Gründen nicht
zuverlässig - dafür Variante A nutzen.
