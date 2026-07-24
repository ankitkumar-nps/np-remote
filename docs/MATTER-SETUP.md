# Matter firmware roadmap (native Google/Apple Home control)

Goal: flash the ESP32-C3 with a **Matter Thermostat/HVAC** device that drives the
Mitsubishi AC over IR, so it appears natively in **Google Home** and **Apple Home**
(free, for your home). This replaces the MicroPython firmware on that board.

## Realities
- **Build host must be Linux/macOS** — on Windows use **WSL2 (Ubuntu)**. esp-matter
  does not build natively on Windows.
- **One firmware per board.** A Matter-flashed C3 can't also run the MQTT web-link.
- **Remote control needs a Matter hub** (Nest Hub / HomePod / Apple TV). Phone apps
  alone = local-network control.
- **Free** for personal use via a test Vendor ID (apps show a one-time "uncertified"
  warning). Commercial/no-warning distribution needs paid CSA certification.

## Phase 1 — WSL + build tools (Windows)
```powershell
wsl --install -d Ubuntu        # then reboot, set up the Ubuntu user
```
Inside Ubuntu:
```bash
sudo apt update && sudo apt install -y git wget flex bison gperf python3 python3-pip \
  python3-venv cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

## Phase 2 — ESP-IDF (v5.2+)
```bash
mkdir -p ~/esp && cd ~/esp
git clone -b v5.2.3 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32c3
. ./export.sh          # run this in every new shell (or alias it)
```

## Phase 3 — esp-matter SDK
```bash
cd ~/esp
git clone --recursive https://github.com/espressif/esp-matter.git
cd esp-matter && ./install.sh
. ./export.sh
```

## Phase 4 — build + flash a thermostat, verify commissioning
Start from the thermostat example, confirm it pairs BEFORE adding IR:
```bash
cd ~/esp/esp-matter/examples/thermostat
idf.py set-target esp32c3
idf.py build
# flash from WSL needs USB passthrough (usbipd-win) OR flash the built .bin from
# Windows with esptool on COM20 (simplest):
#   esptool --chip esp32c3 -p COM20 write_flash 0x0 build/<merged>.bin
```
Commission it: open **Google Home** or **Apple Home** → Add device → Matter → scan the
setup QR from the serial log (or enter the code). Accept the "uncertified" prompt.

## Phase 5 — wire IR to the thermostat (I do this part)
In the thermostat's attribute-update callback (system mode, setpoints), map to our
Mitsubishi frame and transmit via ESP-IDF RMT. The frame/bit-layout is already worked
out in `firmware/arduino/np-ac-gateway` and `firmware/micropython/mitsubishi_ir.py`
(header 0x23 0xCB 0x26 0x01 0x00; power@byte5, mode@byte6, temp@byte7, fan/vane@byte9,
checksum@byte17; 38 kHz; sent twice). I'll port that into `firmware/matter/`.

## Fallback
If Matter integration doesn't behave in your Home app, the **web link stays as the
control path** (on a board running the MQTT firmware).

---
### Lower-effort alternative to reach the SAME "native in Google/Apple Home" goal
Run **Home Assistant** (Docker on Windows, or on a Pi) with our existing MQTT firmware:
HA auto-discovers the AC and exposes it to Google/Apple Home — no C++ build, keeps the
web link working too. Trade-off: needs an always-on HA instance. (Matter needs no HA
but needs the C++ build + a hub.)
