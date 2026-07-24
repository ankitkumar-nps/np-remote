# Home Assistant route — native Google Home / Apple Home control

The firmware **auto-registers** itself in Home Assistant over MQTT (discovery), so the
AC shows up as a climate card with **no manual YAML**. Home Assistant then exposes it
to **Apple Home (free)** and **Google Home**.

```
ESP32-C3 (IR)  --MQTT/TLS-->  HiveMQ Cloud  <--MQTT/TLS--  Home Assistant
                                                              |-- HomeKit Bridge --> Apple Home (free)
                                                              |-- Google Assistant --> Google Home
```

## Prerequisites
- The ESP running our MicroPython firmware, **online** (WiFi + MQTT connected).
- A HiveMQ user for HA (reuse `npac-device`, or make `npac-ha`).
- Home Assistant running somewhere always-on (a Pi you already have, or Docker).

## 1. Install Home Assistant
Easiest: **HA OS** on a spare Pi (flash with Raspberry Pi Imager → "Home Assistant").
Or Docker on any always-on box:
```bash
docker run -d --name homeassistant --restart unless-stopped \
  -v /PATH/config:/config --network host ghcr.io/home-assistant/home-assistant:stable
```
Open `http://<ha-ip>:8123`, create your admin account.

## 2. Connect HA to the same MQTT broker (HiveMQ)
Settings → Devices & Services → **Add Integration → MQTT** → configure manually:
- Broker: `55be3afce0e341a1afa417b9e12d8c9a.s1.eu.hivemq.cloud`
- Port: `8883`
- Username / Password: your HiveMQ user
- Expand **Advanced** → **Broker certificate**: `Auto` (enables TLS)

## 3. The AC appears automatically
Because `HA_DISCOVERY = True`, when the ESP connects it publishes a retained config to
`homeassistant/climate/npac1/config`. HA creates a **climate entity "NP ac"** with:
- On/off + modes: cool / heat / dry / auto / fan_only
- Target temperature 16–31 °C
- Fan: auto / low / medium / high / max / silent
- Swing (vane): auto / swing / 1–5

Test it from the HA dashboard first — changing the card should fire the IR.

## 4a. Apple Home (free, built-in)
Settings → Devices & Services → **Add Integration → HomeKit Bridge** → include the
`climate.np_ac` entity. In the iPhone **Home app**: Add Accessory → scan the HomeKit
pairing code HA shows. Done — Siri + Home app control, free.

## 4b. Google Home
Two options:
- **Home Assistant Cloud (Nabu Casa)** — paid (~$6.50/mo), one-click Google + Alexa,
  plus remote access. Easiest.
- **Manual Google Assistant integration** — free but fiddly (needs a Google Cloud
  project + service account; see HA docs "Google Assistant"). Good if you want $0.

> Apple Home is free & easy via HomeKit Bridge. Google Home is only truly turnkey with
> Nabu Casa; the free manual route works but takes setup.

## Notes
- Selecting a **mode** in HA (e.g. Cool) also powers the unit **on** (firmware maps
  mode → power-on). Set mode **off** to turn it off.
- State shown in HA reflects the last command sent (IR is one-way; no feedback).
- Keep the web link too — it still works in parallel for anyone with the URL.
