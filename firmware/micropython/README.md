# NP ac — MicroPython Gateway (ESP32-C3)

Reconstructed from the original board's flash dump, rewritten in **MicroPython**
so it's easy to read and modify later — including **remote code updates over MQTT**
(no reflashing, no SSH, works through any router).

| File | Purpose |
|---|---|
| `config.py` | all credentials & options — the only file you normally edit |
| `mitsubishi_ir.py` | builds & transmits the Mitsubishi IR frame (RMT, 38 kHz) |
| `ble_nus.py` | BLE "NP ac" Nordic-UART service (in-room, works with web app) |
| `main.py` | WiFi + MQTT + command parser + `/sys` remote management |
| `boot.py` | minimal startup |

---

## SAFETY — the original firmware is backed up
Full image: `..\np-ac-C3-full-4MB.bin`. To restore the ORIGINAL at any time:
```
python -m esptool --port COM20 write_flash 0x0 ..\np-ac-C3-full-4MB.bin
```
Nothing is lost by flashing MicroPython — it's fully reversible.

## 1. Flash the MicroPython runtime (one time)
Download the latest **ESP32-C3** build from micropython.org/download/ESP32_GENERIC_C3
(use v1.22+ so `RMT(tx_carrier=...)` and `aioble` are present).
```
python -m esptool --port COM20 erase_flash
python -m esptool --port COM20 --baud 921600 write_flash 0x0 ESP32_GENERIC_C3-*.bin
```

## 2. Install libraries + upload our code
```
pip install mpremote
mpremote connect COM20 mip install umqtt.robust aioble
mpremote connect COM20 fs cp config.py mitsubishi_ir.py ble_nus.py main.py boot.py :
mpremote connect COM20 reset
```
Watch the console:
```
mpremote connect COM20 repl        # Ctrl-] to exit
```
You should see WiFi connect, `MQTT connected`, `BLE advertising as NP ac`, and
`IR>> ...` when commands arrive.

## 3. Edit config first
In `config.py` set `MQTT_HOST/USER/PASS` (from your HiveMQ Serverless cluster),
confirm `IR_PIN`, and set `BLE_ENABLE=False` if the C3 runs low on memory.

## MQTT topics
| Topic | Dir | Payload |
|---|---|---|
| `npac/npac1/cmd`      | app → board | a command, e.g. `on`, `temp:24`, `cool`, `f3`, `vane:swing` |
| `npac/npac1/state`    | board → app | JSON state (retained) |
| `npac/npac1/status`   | board → app | `online` / `offline` (LWT) |
| `npac/npac1/sys`      | admin → board | remote management (see below) |
| `npac/npac1/sys/resp` | board → admin | replies to /sys |

## Remote management (`/sys`) — update code from anywhere
The board subscribes to `npac/npac1/sys`. Publish JSON:
```json
{"cmd":"info"}                                   // free mem, IP, state
{"cmd":"get","path":"main.py"}                   // read a file back
{"cmd":"put","path":"main.py","data":"<code>"}   // replace a file
{"cmd":"exec","code":"print(1+1)"}               // run statements
{"cmd":"reset"}                                   // reboot (loads new code)
```
Typical remote update: `put` the new file(s) → `reset`. Replies come on
`npac/npac1/sys/resp`.

**Security:** the `/sys` channel can run code. Keep the device MQTT user private.
Give the public web app a **separate** HiveMQ user restricted to `npac/+/cmd` and
`npac/+/state` only (no `/sys`). Set `SYS_ENABLE=False` in config to disable it.

## Known-risk areas (flagged for bench testing)
- **IR fan/vane fine values** (`SILENT`, `MAX`) — the field encoding is best-effort;
  if a specific fan/vane is ignored, capture the real remote and adjust `_FAN`/`_VANE`
  in `mitsubishi_ir.py`, or use `MitsubishiIR.send_raw()` with captured pulses.
- **C3 memory** with BLE+WiFi+TLS together — if unstable, `BLE_ENABLE=False`.
- **RMT pulse count** (~291 per frame) — if `write_pulses` errors on length, we can
  split the frame; tell me and I'll patch it.
