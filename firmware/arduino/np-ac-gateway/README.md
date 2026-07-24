# NP ac — Mitsubishi Remote Gateway (ESP32-C3)

Reconstructed from the original board's flash dump, with **WiFi + MQTT** added so the
web app can control the AC from anywhere (not just Bluetooth range).

- **BLE** stays exactly as before → the existing web app keeps working in-room.
- **MQTT over TLS → HiveMQ Cloud (free)** → remote control for any number of users.
- **IR** on pin D0 → drives the Mitsubishi MSY-GN22VF, same commands as before.

---

## 1. One-time: create a free MQTT broker (HiveMQ Cloud Serverless)

1. Go to **hivemq.com → Start Free → Serverless** and sign in.
2. Create a cluster. Copy the **Cluster URL** (e.g. `abc123.s1.eu.hivemq.cloud`).
3. Open **Access Management → add credentials**:
   - a device user, e.g. `npac-device` / *(strong password)* — used by the ESP32.
   - (recommended) a second user `npac-web` for the web app, so the public app
     doesn't carry the device password.
4. Ports you'll use: **8883** = MQTT+TLS (ESP32), **8884** = MQTT over WSS (web app).

## 2. Edit the config block in `np-ac-gateway.ino`

```c
#define IR_PIN     2                 // GPIO of the IR LED ("D0" on XIAO C3 = GPIO2)
WIFI_APS[] = { {"ghost","nowpurchase@123"}, {"Me3tings4ever","<password>"} };
#define MQTT_HOST  "abc123.s1.eu.hivemq.cloud"
#define MQTT_USER  "npac-device"
#define MQTT_PASS  "<the password you set>"
#define DEVICE_ID  "npac1"          // change if you deploy more than one unit
```

## 3. Install libraries

Arduino IDE → Library Manager, install:
- **IRremoteESP8266** (David Conran)
- **PubSubClient** (Nick O'Leary)

Board: install **esp32 by Espressif** (you already have 3.3.6). Select an
**ESP32C3** board (e.g. "ESP32C3 Dev Module" or "XIAO_ESP32C3"), USB CDC On Boot: **Enabled**.

## 4. Build & flash (port COM20)

**Backup first** (already done — keep this file safe):
`C:\Users\NowPurchase\np-remote-firmware\np-ac-C3-full-4MB.bin`

To restore the ORIGINAL firmware at any time:
```
python -m esptool --port COM20 write_flash 0x0 np-ac-C3-full-4MB.bin
```

Flash the new firmware with Arduino IDE (Upload), or arduino-cli:
```
arduino-cli compile --fqbn esp32:esp32:esp32c3 np-ac-gateway
arduino-cli upload  --fqbn esp32:esp32:esp32c3 -p COM20 np-ac-gateway
```

Open Serial Monitor @115200 — you should see WiFi connect, `MQTT: connected`,
and `IR>> ...` lines when commands arrive.

## 5. MQTT topics

| Topic | Dir | Payload |
|---|---|---|
| `npac/npac1/cmd`    | app → board | a command token, e.g. `on`, `temp:24`, `cool`, `f3`, `vane:swing` |
| `npac/npac1/state`  | board → app | JSON `{"power":true,"temp":24,"mode":"COOL","fan":"AUTO","vane":"AUTO","last":"…"}` (retained) |
| `npac/npac1/status` | board → app | `online` / `offline` (LWT, retained) |

## 6. Command tokens (same as the web app)

`on` `off` · `t+` `t-` `temp:NN` · `cool` `heat` `dry` `auto` `fanonly` ·
`fa` `f1` `f2` `f3` `fmax` `fs` · `vane:auto` `vane:swing` `vane:1..5` ·
`s`/`status` (report only) · `resend`.

## 7. Test from your PC (optional, before touching the web app)

```
# subscribe to state
mosquitto_sub -h abc123.s1.eu.hivemq.cloud -p 8883 --capath /etc/ssl/certs \
  -u npac-device -P '<pass>' -t 'npac/npac1/#' -v
# send a command
mosquitto_pub -h abc123.s1.eu.hivemq.cloud -p 8883 --capath /etc/ssl/certs \
  -u npac-device -P '<pass>' -t 'npac/npac1/cmd' -m 'on'
```

---

## Notes / gotchas
- **IR is one-way.** The `state` JSON reflects what we *told* the AC, not a reading
  from it. That's a limitation of an IR blaster (no feedback path).
- If the AC ignores commands: wrong **IR_PIN**, or the MSY-GN22VF wants a slightly
  different Mitsubishi variant — try `ac.setModel()` / the `IRac` helper, or capture
  the real remote with an IR receiver + the `IRrecvDumpV3` example to confirm bytes.
- The web app is served over **HTTPS (GitHub Pages)**, so in the browser you MUST use
  **`wss://…:8884/mqtt`** (secure WebSocket). Plain `ws://` or `mqtt://` will be blocked.
- Don't hardcode the device MQTT password in the public web app — use the separate
  `npac-web` user, ideally restricted to the `npac/#` topics in HiveMQ.
