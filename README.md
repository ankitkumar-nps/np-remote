# np-remote

Voice + touch remote for a **Mitsubishi MSY-GN22VF** air conditioner, controllable
**in the room over Bluetooth** and **from anywhere over the internet (MQTT)**.

- **`index.html`** — the web app (BLE + Cloud, light/dark theme). Host it on GitHub Pages.
- **`firmware/micropython/`** — the ESP32-C3 firmware (BLE + WiFi + MQTT + remote updates).
- **`firmware/arduino/`** — a C++ alternative of the same firmware.
- **`docs/`** — how it works & how to set up the free MQTT broker.

## Quick start
1. **Broker:** create a free HiveMQ Cloud Serverless cluster — see
   [`docs/HIVEMQ-SETUP.md`](docs/HIVEMQ-SETUP.md).
2. **Firmware:** copy `firmware/micropython/config.example.py` → `config.py`, fill in
   WiFi + MQTT, flash the ESP32-C3 — see [`firmware/micropython/README.md`](firmware/micropython/README.md).
3. **Web app:** enable GitHub Pages (below), open the page, tap **Cloud**,
   enter the broker details (or tap **BLE** when in the room). The app shows a
   **Getting Started** panel on first visit and a **?** button for help anytime.

## Host the web app on GitHub Pages
1. Push this repo to GitHub (branch `main`).
2. On GitHub: **Settings → Pages**.
3. Under **Build and deployment → Source**, choose **Deploy from a branch**.
4. Set **Branch = `main`** and **Folder = `/ (root)`**, click **Save**.
5. Wait ~1 minute, then refresh — GitHub shows your live URL:
   `https://<your-username>.github.io/np-remote/`
   (for this repo: `https://ankitkumar-nps.github.io/np-remote/`).
6. Open that URL on any phone/PC. First visit shows the **Getting Started** panel:
   - **BLE** (top-right) → in-room control (Chrome/Edge).
   - **Cloud** → tap, enter HiveMQ host / user / password / device id → control from anywhere.
7. Share the URL with other users — they each tap **Cloud**, enter the same broker
   details once (saved on their device), and control the same AC live.

> Pages serves over HTTPS, which is exactly why the app uses `wss://…:8884` for MQTT.
> No build step is needed — it's a single static `index.html`.

## How control works
See [`docs/CONTROL-FLOW.md`](docs/CONTROL-FLOW.md) — the app publishes short commands
(`on`, `temp:24`, `cool`, …) to `npac/<id>/cmd`; the device drives the AC over IR and
reports state on `npac/<id>/state`. Multiple users stay in sync live.

## Notes
- The AC link is an **IR blaster** (one-way), so reported state reflects the last
  command sent, not a reading from the AC.
- Web Bluetooth needs Chrome/Edge; the Cloud path works in any browser.
